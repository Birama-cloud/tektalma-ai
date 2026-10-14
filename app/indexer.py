"""Construction de l'index : fiches -> chunks -> embeddings -> ChromaDB."""
import json

import chromadb

from app.corpus import build_chunks, load_fiches
from config import settings


def build_index(embedder) -> int:
    fiches = load_fiches()
    chunks = build_chunks(fiches)
    if not chunks:
        raise RuntimeError("Aucune fiche active dans data/raw/")

    settings.FICHES_FILE.write_text(
        json.dumps(fiches, ensure_ascii=False, indent=1), encoding="utf-8")
    settings.CHUNKS_FILE.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")

    client = chromadb.PersistentClient(path=str(settings.VECTORSTORE_DIR))
    try:  # reconstruction complète = aucun doublon possible
        client.delete_collection(settings.COLLECTION_NAME)
    except Exception:  # noqa: BLE001
        pass
    col = client.create_collection(
        settings.COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
        embeddings=embedder.embed_passages([c["text"] for c in chunks]),
    )
    return len(chunks)
