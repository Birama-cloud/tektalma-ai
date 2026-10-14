"""Affiche l'API de la démo Oolel-Voices. Lancer :  python -m scripts.check_oolel"""
import os

from gradio_client import Client

from config import settings  # noqa: F401  (charge .env)

SPACE = "soynade-research/Oolel-Voices-Demo"
token = os.getenv("HF_TOKEN") or None
try:
    client = Client(SPACE, hf_token=token)
except TypeError:  # versions récentes de gradio_client
    client = Client(SPACE, token=token)
client.view_api()
