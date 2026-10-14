"""Compare le niveau de réflexion de Gemini sur 3 tâches.  Lancer :  python -m scripts.test_thinking

Pour chaque tâche : réglage par défaut, MINIMAL, LOW, et budget 0.
Un seul essai par variante, sans réessai : on voit les vrais temps et les vraies erreurs.
"""
import time

from google.genai import types

from app import voice
from app.llm.client import LLMClient
from app.understanding import SYSTEM as UNDERSTAND_SYSTEM
from config import settings

MODEL = settings.GEMINI_MODEL
FICHE = open(settings.RAW_DIR / "identite" / "cni_demande.md", encoding="utf-8").read().split("---", 2)[2]
VARIANTS = {
    "défaut Google": None,
    "MINIMAL": types.ThinkingConfig(thinking_level="MINIMAL"),
    "LOW": types.ThinkingConfig(thinking_level="LOW"),
    "budget 0": types.ThinkingConfig(thinking_budget=0),
}


def run(client, label, contents, system=None, json_mode=False):
    print(f"\n--- {label}  [{MODEL}]")
    for name, thinking in VARIANTS.items():
        cfg = types.GenerateContentConfig(
            system_instruction=system, temperature=0.1, thinking_config=thinking,
            response_mime_type="application/json" if json_mode else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        t0 = time.perf_counter()
        try:
            out = client.models.generate_content(model=MODEL, contents=contents, config=cfg).text or ""
            status = "✅ " + out.replace("\n", " ")[:70]
        except Exception as e:  # noqa: BLE001
            status = f"❌ {getattr(e, 'code', '')} {str(e)[:80]}"
        print(f"  {name:14s} {time.perf_counter() - t0:6.1f} s   {status}")


if __name__ == "__main__":
    llm = LLMClient()
    c = llm.client
    audio, _ = voice._gemini_tts(llm, "Carte nationale bi, dama ko ñàkk, lan la ma wara def ?")
    run(c, "1. TRANSCRIPTION (vocal wolof)",
        [types.Part.from_bytes(data=audio, mime_type="audio/wav"),
         "Transcris fidèlement cet audio (wolof). Réponds uniquement avec la transcription."])
    run(c, "2. COMPRÉHENSION",
        "HISTORIQUE :\n(aucun)\n\nDERNIER MESSAGE : Carte nationale bi, dama ko ñàkk, lan la ma wara def ?",
        system=UNDERSTAND_SYSTEM, json_mode=True)
    run(c, "3. RÉDACTION",
        f"SOURCES :\n[S1] {FICHE}\n\nQUESTION : Que faire en cas de perte de la carte d'identité ? "
        "Réponds en 120 mots maximum, en citant [S1].")
    print("\nEnvoie-moi cette sortie : on choisira le niveau le plus rapide qui garde des réponses correctes.")
