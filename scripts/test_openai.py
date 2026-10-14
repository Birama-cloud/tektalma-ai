"""Vérifie la clé OpenAI et compare Gemini / OpenAI.  Lancer :  python -m scripts.test_openai

1. Liste les modèles OpenAI disponibles pour ta clé (pour choisir OPENAI_MODEL).
2. Pose les mêmes demandes aux deux fournisseurs et affiche les réponses côte à côte,
   pour que l'équipe juge la qualité, surtout en wolof.
"""
import time

from app.llm.client import LLMClient
from app.understanding import SYSTEM as UNDERSTAND_SYSTEM
from config import settings

FICHE = (settings.RAW_DIR / "identite" / "cni_demande.md").read_text(encoding="utf-8").split("---", 2)[2]
TESTS = [
    ("Compréhension d'une question en wolof (JSON)",
     "HISTORIQUE :\n(aucun)\n\nDERNIER MESSAGE : Carte nationale bi, dama ko ñàkk, lan la ma wara def ?",
     UNDERSTAND_SYSTEM, True),
    ("Réponse en français à partir de la fiche officielle",
     f"SOURCES :\n[S1] {FICHE}\n\nQUESTION : Comment obtenir la carte nationale d'identité ? "
     "Réponds en français, 80 mots maximum, uniquement à partir de la source, en citant [S1].", None, False),
    ("Réponse en wolof à partir de la fiche officielle",
     f"SOURCES :\n[S1] {FICHE}\n\nQUESTION : Carte nationale bi, nan la ma mën a def ngir jël ko ? "
     "Réponds en wolof courant de Dakar, 80 mots maximum, uniquement à partir de la source, en citant [S1]. "
     "Garde en français les termes administratifs.", None, False),
]


def timed(fn):
    t0 = time.perf_counter()
    try:
        out = fn()
    except Exception as e:  # noqa: BLE001
        out = f"❌ {type(e).__name__}: {str(e)[:150]}"
    return time.perf_counter() - t0, out


if __name__ == "__main__":
    llm = LLMClient()
    if not llm.openai:
        raise SystemExit("❌ OPENAI_API_KEY absente de .env")

    print("Modèles OpenAI disponibles pour ta clé (extrait) :")
    names = sorted(m.id for m in llm.openai.models.list())
    for name in [n for n in names if n.startswith(("gpt-", "o")) or "transcribe" in n or "whisper" in n][:40]:
        print("  ", name)
    for label, value in (("OPENAI_MODEL", settings.OPENAI_MODEL),
                         ("OPENAI_TRANSCRIBE_MODEL", settings.OPENAI_TRANSCRIBE_MODEL)):
        print(f"{'✅' if value in names else '❌ introuvable :'} {label} = {value}")

    openai_client, llm.openai = llm.openai, None      # Gemini seul, sans bascule, pour comparer
    for title, prompt, system, json_mode in TESTS:
        print(f"\n=== {title}")
        s, out = timed(lambda: llm.generate(prompt, system=system, json_mode=json_mode))
        print(f"--- Gemini ({settings.GEMINI_MODEL}) · {s:.1f} s\n{out}")
        llm.openai = openai_client
        s, out = timed(lambda: llm.openai_generate(prompt, system=system, json_mode=json_mode))
        llm.openai = None
        print(f"--- OpenAI ({settings.OPENAI_MODEL}) · {s:.1f} s\n{out}")
    print("\nFais lire les réponses wolof à un locuteur : c'est ce qui décide de la place d'OpenAI.")
