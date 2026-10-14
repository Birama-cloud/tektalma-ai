"""Gestion du cache de TEKTALMA.

    python -m scripts.cache_tool stats   -> ce que contient le cache
    python -m scripts.cache_tool warm    -> précharge les questions de data/faq.yaml (+ leurs voix)
    python -m scripts.cache_tool clear   -> vide entièrement le cache

Le préchargement consomme environ 2 à 3 appels Gemini par question : lancez-le
quand votre quota est disponible, de préférence la veille d'une démo.
"""
import sys
import time

import yaml

from app import voice
from app.cache import get_cache
from config import settings


def stats():
    rows, n_audio = get_cache().stats()
    if not rows:
        print("Cache vide.")
    for level, lang, n, hits in rows:
        name = "questions écrites" if level == "q" else "questions reformulées"
        print(f"  {name:22s} [{lang}] : {n:3d} réponses · {hits or 0} réutilisations")
    print(f"  voix enregistrées      : {n_audio}")
    print(f"  empreinte du corpus    : {get_cache().version}  (durée de vie {settings.CACHE_TTL_DAYS} jours)")


def warm():
    from app.pipeline import Tektalma

    questions = yaml.safe_load(settings.FAQ_FILE.read_text(encoding="utf-8")) or []
    engine = Tektalma()
    for i, q in enumerate(questions, 1):
        t0 = time.time()
        ans = engine.ask(q)
        status = "déjà en cache" if ans.debug.get("cache") else ans.kind
        if ans.kind == "answer":
            voice.speak(engine.llm, ans.text, ans.language)
        print(f"[{i}/{len(questions)}] {time.time() - t0:5.1f} s  {status:14s} [{ans.language}] {q}")
        if ans.kind == "error":
            print("   ⚠️ Gemini indisponible : relancez plus tard, les réponses déjà obtenues sont gardées.")
            break
        if not ans.debug.get("cache"):
            time.sleep(2)   # ménage le quota gratuit
    print()
    stats()


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if action == "warm":
        warm()
    elif action == "clear":
        get_cache().clear()
        print("Cache vidé.")
    else:
        stats()
