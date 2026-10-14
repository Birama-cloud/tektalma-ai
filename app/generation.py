"""Génération de la réponse à partir des fiches récupérées uniquement."""

LANG_NAMES = {"fr": "français", "wo": "wolof", "en": "anglais"}

SYSTEM = """Tu es TEKTALMA AI, assistant des démarches administratives au Sénégal.
Tu réponds UNIQUEMENT à partir des SOURCES fournies.

Règles absolues :
1. N'invente JAMAIS de frais, délais, documents, adresses, numéros de téléphone, liens ou procédures.
   Si une information demandée n'est pas dans les sources, dis clairement que la source officielle ne la précise pas.
2. Après chaque information, indique sa source avec [S1], [S2]... Uniquement les numéros des sources fournies.
3. Réponds ENTIÈREMENT en {lang}, du début à la fin. N'ajoute AUCUN mot, formule de politesse ou phrase
   dans une autre langue. Les noms officiels des documents et des administrations restent tels qu'écrits dans les sources.
4. La réponse sera aussi lue à voix haute : phrases courtes et simples, pas de tableau, 5 éléments maximum par liste, 130 mots maximum.
5. Si utile, organise ainsi : documents à préparer, où aller, coût, délai. N'inclus que les rubriques présentes dans les sources.
6. Si les sources ne répondent pas à la question, dis-le et oriente vers l'administration indiquée dans la source.
7. Ne demande aucune donnée personnelle (numéro de carte, adresse...).
"""


def build_context(docs) -> str:
    parts = []
    for i, d in enumerate(docs, start=1):
        m = d["meta"]
        parts.append(f"[S{i}] {m['title']} — {m['organisme']}\n{d['full_text']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(llm, docs, question_fr: str, original: str, lang: str) -> tuple[str, str]:
    context = build_context(docs)
    prompt = (f"SOURCES :\n{context}\n\n"
              f"QUESTION ORIGINALE : {original}\n"
              f"QUESTION REFORMULÉE : {question_fr}")
    system = SYSTEM.format(lang=LANG_NAMES.get(lang, "français"))
    from config import settings

    return llm.generate(prompt, system=system, temperature=0.1,
                        timeout_s=settings.TIMEOUT_ANSWER_S), context


BILINGUAL_RULES = """

FORMAT DE SORTIE : réponds UNIQUEMENT avec ce JSON :
{{"fr": "la réponse complète en français, avec les [S1]", "wo": "exactement la même réponse, traduite en wolof"}}
La règle « une seule langue » s'applique à chaque champ séparément : "fr" entièrement en français,
"wo" entièrement en wolof (termes administratifs gardés en français). La réponse "fr" suit toutes les règles ci-dessus. La traduction "wo" garde les mêmes chiffres, les mêmes [S1],
la même mise en forme, et suit ce guide :
{guide}"""


def generate_bilingual(llm, docs, question_fr: str, original: str) -> tuple[str, str, str]:
    """Un seul appel : réponse vérifiable en français + sa traduction wolof. Renvoie (fr, wo, contexte)."""
    from app.understanding import parse_json
    from app.wolof import style_guide
    from config import settings

    context = build_context(docs)
    prompt = (f"SOURCES :\n{context}\n\n"
              f"QUESTION ORIGINALE : {original}\n"
              f"QUESTION REFORMULÉE : {question_fr}")
    system = SYSTEM.format(lang="français") + BILINGUAL_RULES.format(guide=style_guide())
    data = parse_json(llm.generate(prompt, system=system, json_mode=True,
                                   timeout_s=settings.TIMEOUT_ANSWER_S))
    return str(data.get("fr") or ""), str(data.get("wo") or ""), context
