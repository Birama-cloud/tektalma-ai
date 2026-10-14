"""Recherche hybride : sémantique (ChromaDB) + mots-clés (BM25), fusion RRF."""
import json
import re

import chromadb
from rank_bm25 import BM25Okapi

from app.indexer import build_index
from config import settings

STOPWORDS = {
    "les", "des", "une", "est", "pour", "que", "qui", "dans", "par", "sur", "aux",
    "avec", "mon", "mes", "son", "ses", "faire", "comment", "quoi", "quel",
    "quels", "quelle", "quelles", "faut", "dois", "doit", "vous", "nous", "the",
    "and", "how",
}
RRF_K = 60
CATEGORY_BONUS = 0.01
ACTION_BONUS = 0.01


def tokenize(text: str):
    return [t for t in re.findall(r"\w+", text.lower())
            if len(t) > 2 and t not in STOPWORDS]


class Retriever:
    def __init__(self, embedder):
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=str(settings.VECTORSTORE_DIR))
        self._load()

    def _load(self):
        try:
            self.col = self.client.get_collection(settings.COLLECTION_NAME)
            ready = self.col.count() > 0 and settings.CHUNKS_FILE.exists()
        except Exception:  # noqa: BLE001
            ready = False
        if not ready:  # 1er lancement : construction automatique
            build_index(self.embedder)
            self.col = self.client.get_collection(settings.COLLECTION_NAME)
        self.chunks = json.loads(settings.CHUNKS_FILE.read_text(encoding="utf-8"))
        fiches = json.loads(settings.FICHES_FILE.read_text(encoding="utf-8"))
        self.fiches = {f["doc_id"]: f for f in fiches}
        self.chunk_by_id = {c["id"]: c for c in self.chunks}
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])

    def search(self, query: str, category: str | None = None, action: str | None = None,
               top_docs: int = settings.TOP_DOCS):
        # 1) Recherche sémantique
        n = min(settings.DENSE_K, self.col.count())
        res = self.col.query(query_embeddings=[self.embedder.embed_query(query)], n_results=n)
        dense_ids = res["ids"][0]
        similarity = {cid: 1 - d for cid, d in zip(dense_ids, res["distances"][0])}

        # 2) Recherche mots-clés
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        bm25_ids = [self.chunks[i]["id"] for i in ranked[: settings.BM25_K] if scores[i] > 0]

        # 3) Fusion RRF + bonus si la catégorie / l'action détectées correspondent
        fused = {}
        for ids in (dense_ids, bm25_ids):
            for rank, cid in enumerate(ids):
                fused[cid] = fused.get(cid, 0) + 1 / (RRF_K + rank + 1)
        for cid in fused:
            meta = self.chunk_by_id[cid]["metadata"]
            if category and meta.get("category") == category:
                fused[cid] += CATEGORY_BONUS
            if action and action != "general" and action in (meta.get("action"), meta.get("section")):
                fused[cid] += ACTION_BONUS

        # 4) Regroupement par fiche (small-to-big : on renvoie la fiche entière)
        docs = {}
        for cid, score in fused.items():
            doc_id = self.chunk_by_id[cid]["doc_id"]
            d = docs.setdefault(doc_id, {"score": 0.0, "similarity": 0.0, "sections": []})
            d["score"] = max(d["score"], score)
            d["similarity"] = max(d["similarity"], similarity.get(cid, 0.0))
            d["sections"].append(self.chunk_by_id[cid]["metadata"]["heading"])

        best = sorted(docs.items(), key=lambda kv: kv[1]["score"], reverse=True)[:top_docs]
        return [{
            "doc_id": doc_id,
            "meta": self.fiches[doc_id]["meta"],
            "full_text": self.fiches[doc_id]["full_text"],
            "similarity": round(info["similarity"], 3),
            "score": round(info["score"], 4),
            "sections": info["sections"],
        } for doc_id, info in best]
