"""Chronomètre chaque étape d'une question.  Lancer :  python -m scripts.profile_latency

Mesure : transcription, compréhension, recherche, rédaction, traduction wolof, voix.
Compare aussi le modèle principal et le modèle « lite » pour les petites tâches.
"""
import copy
import time

from app import voice
from app.embeddings import Embedder
from app.generation import generate_answer
from app.llm.client import LLMClient
from app.retrieval import Retriever
from app.understanding import understand
from app.wolof import to_wolof
from config import settings

QUESTIONS = [
    ("fr", "J'ai perdu ma carte d'identité, je dois faire quoi ?"),
    ("wo", "Carte nationale bi, dama ko ñàkk, lan la ma wara def ?"),
]


def timed(label, fn, results):
    t0 = time.perf_counter()
    try:
        out = fn()
        ok = True
    except Exception as e:  # noqa: BLE001
        out, ok = None, False
        label += f"  ❌ {type(e).__name__}"
    results.append((label, time.perf_counter() - t0, ok))
    return out


def with_model(llm, model):
    clone = copy.copy(llm)
    clone.models = [model]
    return clone


def run(llm, retriever, lang, question):
    r = []
    print(f"\n=== [{lang}] {question}")

    # Transcription : on fabrique d'abord un vocal avec la voix Gemini, puis on le transcrit
    audio = timed("(préparation) création d'un vocal de test", lambda: voice._gemini_tts(llm, question), r)
    if audio:
        for model in dict.fromkeys([settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]):
            timed(f"1. transcription        [{model}]",
                  lambda m=model: voice.transcribe(with_model(llm, m), audio[0], "audio/wav", lang), r)

    u = None
    for model in dict.fromkeys([settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL]):
        res = timed(f"2. compréhension        [{model}]",
                    lambda m=model: understand(with_model(llm, m), question, [], settings.MAX_HISTORY), r)
        u = u or res
    query = (u or {}).get("standalone_question_fr", question)

    docs = timed("3. recherche (local)", lambda: retriever.search(query, (u or {}).get("category"),
                                                                 (u or {}).get("action")), r) or []
    gen = timed(f"4. rédaction            [{settings.GEMINI_MODEL}]",
                lambda: generate_answer(llm, docs, query, question, "fr"), r)
    answer = gen[0] if gen else "Réponse de test."

    if lang == "wo":
        wo = timed(f"5. traduction wolof     [{settings.GEMINI_MODEL}]", lambda: to_wolof(llm, answer), r)
        answer = wo or answer
    timed(f"6. voix (Gemini TTS)    [{settings.GEMINI_TTS_MODEL}]", lambda: voice._gemini_tts(llm, answer), r)

    for label, secs, ok in r:
        bar = "█" * int(secs * 2)
        print(f"  {label:48s} {secs:6.1f} s  {bar}")
    main_path = [s for label, s, ok in r if ok and not label.startswith("(")
                 and (settings.GEMINI_FALLBACK_MODEL not in label or settings.GEMINI_FALLBACK_MODEL == settings.GEMINI_MODEL)]
    print(f"  {'TOTAL parcours actuel (modèle principal)':48s} {sum(main_path):6.1f} s")


if __name__ == "__main__":
    print("Chargement des modèles (non chronométré)…")
    llm = LLMClient()
    retriever = Retriever(Embedder())
    for lang, q in QUESTIONS:
        run(llm, retriever, lang, q)
    print("\nEnvoie-moi toute cette sortie : on optimisera d'abord l'étape la plus longue.")
