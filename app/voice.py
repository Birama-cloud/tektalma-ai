"""Voix : transcription (Gemini) et synthèse vocale.

Ordre de synthèse :
- français / anglais : gTTS (rapide), sinon Gemini TTS ;
- wolof : Oolel-Voices ou Gemini TTS (réglage WOLOF_TTS dans .env), l'autre en secours.
"""
import io
import re
import wave
from functools import lru_cache

from google.genai import types

from config import settings

TRANSCRIBE_PROMPT = (
    "Transcris fidèlement cet enregistrement audio. La personne parle {hint}, "
    "parfois en mélangeant wolof et français (c'est courant au Sénégal). "
    "Écris le wolof avec l'orthographe wolof usuelle et garde les mots français en français. "
    "Contexte : questions sur les démarches administratives au Sénégal. Vocabulaire fréquent : "
    "carte nationale d'identité, carte d'identité, passeport, extrait de naissance, acte de naissance, "
    "certificat de résidence, certificat de nationalité, quittance, timbre, commissariat, gendarmerie, "
    "mairie, préfecture, état civil, consulat, dossier, kayit, ñàkk (perdre), jël (prendre), "
    "defar (faire), laaj (demander), fan (où), ñaata (combien), njëg (prix), lan (quoi), naka (comment), "
    "sama (mon), dama (je), bëgg (vouloir), war (devoir). "
    "Réponds uniquement avec la transcription, sans commentaire."
)
HINTS = {"wo": "surtout wolof", "fr": "surtout français", "en": "surtout anglais"}


def transcribe(llm, audio_bytes: bytes, mime_type: str = "audio/wav", lang_hint: str | None = None) -> str:
    prompt = TRANSCRIBE_PROMPT.format(hint=HINTS.get(lang_hint, "wolof, français ou anglais"))
    part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    return llm.generate([part, prompt], temperature=0.0)


def speakable(text: str) -> str:
    text = re.sub(r"\[S\d+\]", "", text)
    text = re.sub(r"[*#_`>|]", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()[:1200]


def _wav(samples: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples)
    return buf.getvalue()


def _gemini_tts(llm, text: str):
    data, mime = llm.synthesize(text, timeout_s=settings.TIMEOUT_TTS_S)
    if "wav" in mime:
        return data, "audio/wav"
    rate = int(m.group(1)) if (m := re.search(r"rate=(\d+)", mime)) else 24000
    return _wav(data, rate), "audio/wav"   # PCM 16 bits brut -> WAV


def _gtts(text: str, lang: str):
    from gtts import gTTS

    buf = io.BytesIO()
    gTTS(text, lang=lang).write_to_fp(buf)
    return buf.getvalue(), "audio/mp3"


# ---------------------------------------------------------------- Oolel-Voices
@lru_cache(maxsize=1)
def _oolel_client():
    from gradio_client import Client

    try:
        return Client(settings.OOLEL_SPACE, hf_token=settings.HF_TOKEN, verbose=False)
    except TypeError:  # versions récentes de gradio_client
        return Client(settings.OOLEL_SPACE, token=settings.HF_TOKEN, verbose=False)


def _segments(text: str, limit: int = 450):
    """Découpe en morceaux de moins de 500 caractères (limite de la démo), sur les phrases."""
    parts, current = [], ""
    for sentence in re.split(r"(?<=[.!?;:])\s+", text):
        if current and len(current) + len(sentence) + 1 > limit:
            parts.append(current)
            current = ""
        current = f"{current} {sentence}".strip()[:limit]
    return parts + ([current] if current else [])


def _join_wavs(files) -> bytes:
    frames, params = [], None
    for path in files:
        with wave.open(str(path), "rb") as w:
            if params is None:
                params = w.getparams()
            elif w.getparams()[:3] != params[:3]:
                continue
            frames.append(w.readframes(w.getnframes()))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)
    return buf.getvalue()


def _oolel(text: str):
    from gradio_client import handle_file

    client = _oolel_client()
    jobs = [client.submit(text_input=chunk,
                          audio_prompt_path_input=handle_file(settings.OOLEL_VOICE_URL),
                          exaggeration_input=0.3, temperature_input=0.2,   # réglages par défaut de la démo
                          seed_num_input=0, cfgw_input=0.5,
                          api_name="/generate_tts_audio") for chunk in _segments(text)]
    files = [job.result(timeout=settings.OOLEL_TIMEOUT) for job in jobs]
    if len(files) == 1:
        data = open(files[0], "rb").read()
        return data, "audio/mp3" if str(files[0]).endswith(".mp3") else "audio/wav"
    return _join_wavs(files), "audio/wav"


# ---------------------------------------------------------------- choix de la voix
WOLOF_ENGINES = ("oolel", "gemini")


def _audio_key(text: str, lang: str) -> str:
    import hashlib

    engine = settings.WOLOF_TTS if lang == "wo" else "gtts"
    return hashlib.sha1(f"{lang}|{engine}|{settings.GEMINI_TTS_VOICE}|{text}".encode()).hexdigest()


def speak(llm, text: str, lang: str):
    """Renvoie (audio, mime) ou (None, None) si aucune voix n'est disponible.

    Français / anglais : gTTS d'abord (1 à 2 s), Gemini en secours.
    Wolof : voix choisie dans .env (gemini ou oolel), l'autre en secours.
    Les voix déjà générées sont conservées sur le disque (réponse instantanée).
    """
    from app.cache import get_cache

    clean = speakable(text)
    if not clean:
        return None, None
    key = _audio_key(clean, lang)
    cache = get_cache()
    if hit := cache.get_audio(key):
        return hit
    if lang == "wo":
        runners = {"oolel": lambda: _oolel(clean), "gemini": lambda: _gemini_tts(llm, clean)}
        first = settings.WOLOF_TTS if settings.WOLOF_TTS in runners else "gemini"
        engines = [runners[first]] + [runners[e] for e in WOLOF_ENGINES if e != first]
    else:
        engines = [lambda: _gtts(clean, lang if lang in ("fr", "en") else "fr"),
                   lambda: _gemini_tts(llm, clean)]
    for engine in engines:
        try:
            data, mime = engine()
        except Exception:  # noqa: BLE001  (quota, réseau, modèle absent…)
            continue
        cache.put_audio(key, data, mime)
        return data, mime
    return None, None
