"""Compare les 2 voix wolof sur la même phrase.

Lancer :  python -m scripts.test_voices
Écouter ensuite les fichiers dans data/voice_tests/ et choisir WOLOF_TTS dans .env.
"""
import time

from app import voice
from app.llm.client import LLMClient
from config import settings

PHRASE = ("Ngir am carte nationale d'identité, dem ci commissariat bi nekk ci sa gox. "
          "Kayit yi nga war a waajal : extrait de naissance ak certificat de résidence.")

if __name__ == "__main__":
    out_dir = settings.DATA_DIR / "voice_tests"
    out_dir.mkdir(exist_ok=True)
    llm = LLMClient()
    engines = {
        "gemini": lambda: voice._gemini_tts(llm, PHRASE),
        "oolel": lambda: voice._oolel(PHRASE),
    }
    for name, run in engines.items():
        t0 = time.time()
        try:
            data, mime = run()
            ext = "mp3" if "mp3" in mime else "wav"
            path = out_dir / f"{name}.{ext}"
            path.write_bytes(data)
            print(f"✅ {name:7s} {time.time() - t0:5.1f} s  ->  {path}")
        except Exception as e:  # noqa: BLE001
            print(f"❌ {name:7s} {time.time() - t0:5.1f} s  ->  {type(e).__name__}: {str(e)[:150]}")
