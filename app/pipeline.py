"""Orchestration : comprendre -> chercher -> générer -> vérifier.

Nombre d'appels à Gemini par question :
- écrite en français / anglais : 2 (compréhension, rédaction)
- vocale : 2 aussi (la transcription est faite pendant la compréhension)
- en wolof : 2 (la traduction est faite pendant la rédaction)
- question déjà posée : 0 ou 1 grâce au cache
"""
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from app.cache import get_cache, guess_lang
from app.embeddings import Embedder
from app.generation import generate_answer, generate_bilingual
from app.guards import allowed_numbers, check_numbers, clean_citations, is_supported, keep_language
from app.llm.client import LLMClient, LLMUnavailable
from app.messages import msg
from app.retrieval import Retriever
from app.understanding import understand
from config import settings



@dataclass
class Answer:
    text: str
    kind: str                     # answer | clarification | out_of_domain | no_info | sources | error
    language: str = "fr"
    sources: list = field(default_factory=list)
    debug: dict = field(default_factory=dict)
    docs: list = field(default_factory=list)      # fiches utilisées (pour la fiche récapitulative)
    question_fr: str = ""
    question: str = ""            # question telle que comprise (transcription si vocal)


def source_card(n, doc):
    m = doc["meta"]
    return {"n": n, "title": m["title"], "organisme": m["organisme"], "url": m["url"],
            "collected_at": str(m.get("collected_at", "")), "updated_at": str(m.get("updated_at", ""))}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


class Tektalma:
    def __init__(self, retriever=None, llm=None, cache=None):
        self.llm = llm or LLMClient()
        self.retriever = retriever or Retriever(Embedder())
        self.cache = cache or get_cache()     # créé après l'index : empreinte du corpus à jour
        self.cache.refresh()

    # ------------------------------------------------------------------ cache
    def _embed(self, text):
        return self.retriever.embedder.embed_query(text)

    def _cache_get(self, level, text, lang):
        data, match = self.cache.lookup(level, text, lang, self._embed)
        if not data:
            return None
        return Answer(**{**data, "debug": {"cache": match}})

    def _cache_put(self, level, text, lang, ans):
        if ans.kind == "answer":
            self.cache.store(level, text, lang, {**asdict(ans), "debug": {}}, self._embed)

    def _failure(self, err, lang):
        return Answer(msg("quota" if getattr(err, "quota", False) else "error", lang), "error", lang)

    # ------------------------------------------------------------------ question
    def ask(self, question: str | None = None, history=None, force_lang: str | None = None,
            audio: bytes | None = None, mime_type: str = "audio/wav") -> Answer:
        history = history or []

        # Cache niveau 1 : même question (ou très proche), début de conversation -> 0 appel
        qlang = force_lang or guess_lang(question or "")
        if question and not history and (hit := self._cache_get("q", question, qlang)):
            hit.question = question
            return hit

        try:
            u = understand(self.llm, question, history, settings.MAX_HISTORY, force_lang,
                           audio=audio, mime_type=mime_type)
        except LLMUnavailable as e:
            return self._failure(e, force_lang or "fr")
        heard = u.get("transcription") or question or ""
        lang = force_lang or u["language"]
        debug = {"understanding": u}
        if audio and not heard:
            return Answer(msg("not_heard", lang), "clarification", lang, debug=debug)

        ans = self._answer(u, heard, history, lang, debug)
        ans.question = heard
        if heard and not history and not ans.debug.get("cache"):
            key_lang = force_lang or guess_lang(heard)
            if force_lang or ans.language == key_lang:     # jamais de réponse dans une autre langue
                self._cache_put("q", heard, key_lang, ans)
        return ans

    def _answer(self, u, question, history, lang, debug) -> Answer:
        if u.get("is_source_question"):
            last = next((m.get("sources") for m in reversed(history)
                         if m["role"] == "assistant" and m.get("sources")), None)
            if not last:
                return Answer(msg("no_sources_yet", lang), "sources", lang, debug=debug)
            lines = [msg("sources_intro", lang)] + [
                f"- [S{s['n']}] {s['title']} — {s['organisme']}" for s in last]
            return Answer("\n".join(lines), "sources", lang, last, debug)

        if not u.get("in_domain", True):
            return Answer(msg("out_of_domain", lang), "out_of_domain", lang, debug=debug)

        if u.get("needs_clarification") and u.get("clarification_question"):
            return Answer(u["clarification_question"], "clarification", lang, debug=debug)

        # Domaine détecté mais absent du corpus (ex : entreprise) -> on ne force pas de réponse
        covered = {f["meta"]["category"] for f in self.retriever.fiches.values()}
        if u.get("category") and u["category"] not in covered and u["category"] != "autres":
            return Answer(msg("no_info", lang), "no_info", lang, debug=debug)

        query = u["standalone_question_fr"]

        # Cache niveau 2 : même question reformulée (ou très proche), même langue -> pas de rédaction
        if hit := self._cache_get("s", query, lang):
            return hit

        docs = self.retriever.search(query, category=u.get("category"), action=u.get("action"))
        debug["retrieved"] = [(d["meta"]["fiche"], d["similarity"]) for d in docs]
        best_sim = max((d["similarity"] for d in docs), default=0.0)
        if best_sim < settings.MIN_SIMILARITY:
            return Answer(msg("no_info", lang), "no_info", lang, debug=debug)

        try:
            if lang == "wo":   # un seul appel : français vérifiable + traduction wolof
                raw_fr, raw_wo, context = generate_bilingual(self.llm, docs, query, question)
            else:
                (raw_fr, context), raw_wo = generate_answer(self.llm, docs, query, question, lang), ""
        except LLMUnavailable as e:
            return self._failure(e, lang)
        except ValueError:     # JSON illisible : on repasse par la rédaction simple
            try:
                (raw_fr, context), raw_wo = generate_answer(self.llm, docs, query, question, "fr"), ""
            except LLMUnavailable as e:
                return self._failure(e, lang)

        gen_lang = "fr" if lang == "wo" else lang
        text, used = clean_citations(raw_fr, len(docs))
        text, removed = check_numbers(text, context)
        text = keep_language(text, gen_lang)
        debug["removed_sentences"] = removed
        if not text:
            return Answer(msg("no_info", lang), "no_info", lang, debug=debug)

        if lang == "wo":
            debug["answer_fr"] = text
            wolof, _ = clean_citations(raw_wo, len(docs))
            if wolof.strip() and is_supported(wolof, allowed_numbers(text)):
                text = wolof
            else:
                lang = "fr"   # traduction absente ou chiffres modifiés : version française vérifiée

        cited = used or list(range(1, len(docs) + 1))
        sources = [source_card(n, docs[n - 1]) for n in cited]
        cards_docs = [{"meta": d["meta"], "full_text": d["full_text"]} for d in docs]
        ans = Answer(text, "answer", lang, sources, debug, cards_docs, query)
        self._cache_put("s", query, lang, ans)
        return ans
