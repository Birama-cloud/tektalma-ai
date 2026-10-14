"""Modèle d'embeddings local (famille E5 : préfixes query:/passage:)."""
from config import settings


class Embedder:
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_passages(self, texts):
        return self.model.encode(
            [f"passage: {t}" for t in texts], normalize_embeddings=True, batch_size=16
        ).tolist()

    def embed_query(self, text):
        return self.model.encode(f"query: {text}", normalize_embeddings=True).tolist()
