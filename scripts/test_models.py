"""Compare la disponibilité des modèles Gemini.  Lancer :  python -m scripts.test_models

À lancer 2 ou 3 fois à quelques minutes d'intervalle : la charge des serveurs varie.
Le meilleur candidat répond ✅ rapidement à chaque fois -> GEMINI_MODEL dans .env.
"""
import time

from google import genai

from config import settings

MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
          "gemini-3.5-flash", "gemini-3.5-flash-lite"]

if __name__ == "__main__":
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    for model in MODELS:
        t0 = time.time()
        try:
            client.models.generate_content(model=model, contents="Réponds uniquement : OK")
            result = "✅ OK"
        except Exception as e:  # noqa: BLE001
            result = f"❌ {getattr(e, 'code', type(e).__name__)}"
        print(f"{model:24s} {time.time() - t0:5.1f} s  {result}")
