"""Construit (ou reconstruit) l'index. Lancer :  python -m scripts.build_index"""
import time

from app.embeddings import Embedder
from app.indexer import build_index

if __name__ == "__main__":
    t0 = time.time()
    n = build_index(Embedder())
    print(f"✅ Index construit : {n} chunks en {time.time() - t0:.1f} s")
