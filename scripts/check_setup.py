"""Vérifie que l'environnement TEKTALMA AI est prêt.

Lancer depuis la racine du projet :  python -m scripts.check_setup
"""
from config import settings


def check_gemini() -> bool:
    print("\n[1/3] Gemini")
    if not settings.GEMINI_API_KEY or "colle_ta_cle" in settings.GEMINI_API_KEY:
        print("  ❌ GEMINI_API_KEY manquante dans .env")
        return False
    try:
        from google import genai

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        resp = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents="Réponds uniquement par : OK TEKTALMA",
        )
        print(f"  ✅ Modèle {settings.GEMINI_MODEL} répond : {resp.text.strip()}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ Erreur Gemini : {e}")
        print("  → Si le modèle est introuvable, change GEMINI_MODEL dans .env")
        return False


def check_embeddings() -> bool:
    print("\n[2/3] Embeddings (1er lancement : téléchargement ~1 Go)")
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        passages = [
            "passage: En cas de perte ou de vol de la carte nationale d'identité, "
            "la déclaration auprès de la police ou de la gendarmerie est indispensable.",
            "passage: Tout citoyen sénégalais peut, dès la naissance, demander un passeport ordinaire.",
        ]
        questions = [
            "query: J'ai perdu ma carte d'identité, je dois faire quoi ?",
            "query: Carte nationale bi, dama ko ñàkk, lan la ma wara def ?",
        ]
        p = model.encode(passages, normalize_embeddings=True)
        q = model.encode(questions, normalize_embeddings=True)
        scores = q @ p.T
        for question, row in zip(questions, scores):
            print(f"  {question[7:]}")
            print(f"     CNI perdue : {row[0]:.3f} | passeport : {row[1]:.3f}")
        print("  ✅ Embeddings OK (la 1re colonne doit être la plus haute)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ Erreur embeddings : {e}")
        return False


def check_chroma() -> bool:
    print("\n[3/3] ChromaDB")
    try:
        import chromadb

        chromadb.PersistentClient(path=str(settings.VECTORSTORE_DIR))
        print(f"  ✅ ChromaDB {chromadb.__version__} OK ({settings.VECTORSTORE_DIR})")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ Erreur ChromaDB : {e}")
        return False


if __name__ == "__main__":
    results = [check_gemini(), check_embeddings(), check_chroma()]
    print("\n" + ("🎉 Tout est prêt !" if all(results) else "⚠️  Corrige les erreurs ci-dessus."))
