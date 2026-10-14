# 🇸🇳 TEKTALMA AI

**Assistant vocal des démarches administratives au Sénégal, en français, en wolof et en anglais.**

TEKTALMA AI répond aux questions des citoyens sur leurs démarches administratives (documents à fournir, étapes, lieux) à partir de **sources officielles uniquement**. L'utilisateur pose sa question à l'oral ou à l'écrit, dans sa langue, et reçoit une réponse accompagnée de ses sources.

> Projet réalisé lors du **hackathon GOMYCODE du 27 septembre 2026**.

---

## Le problème

Beaucoup de Sénégalais renoncent à une démarche administrative faute de comprendre les procédures : l'information est dispersée, souvent rédigée uniquement en français, et difficile à trouver pour ceux qui ne lisent pas cette langue.

## La solution

Un assistant vocal qui :

- **écoute** la question en français, en wolof ou en anglais ;
- **cherche** la réponse dans une base de fiches tirées de pages officielles ;
- **répond** dans la langue de l'utilisateur, à l'écrit et à la voix, en citant ses sources ;
- **refuse de répondre** quand il n'est pas sûr, plutôt que d'inventer.

---

## Architecture

```
Question (voix ou texte)
  → transcription (Gemini)
  → compréhension : langue, intention, reformulation en français
  → recherche hybride : ChromaDB (sémantique) + BM25 (mots-clés), fusion RRF
  → seuil de confiance : en dessous, pas de réponse inventée
  → génération de la réponse à partir des fiches (Gemini)
  → garde-fous : citations valides, chiffres présents dans les sources
  → réponse + sources → synthèse vocale
```

Les garde-fous vérifient que chaque citation renvoie à une vraie fiche et que chaque chiffre de la réponse (montant, délai) figure bien dans les sources.

---

## Installation

Prérequis : Python 3.10 ou plus récent, et une clé API Gemini.

```bash
git clone https://github.com/Birama-cloud/tektalma-ai.git
cd tektalma-ai
python -m venv .venv
.venv\Scripts\activate          # Windows (sous macOS/Linux : source .venv/bin/activate)
pip install -r requirements.txt
```

Créez un fichier `.env` à la racine du projet, avec votre clé :

```
GEMINI_API_KEY=votre_clé_ici
```

Ce fichier ne doit jamais être publié : il est exclu par le `.gitignore`.

## Lancement

```bash
python -m scripts.validate_raw      # vérifie les fiches officielles
python -m scripts.build_index       # construit l'index de recherche
streamlit run app/streamlit_app.py  # lance l'interface
```

L'index n'est pas inclus dans le dépôt : `build_index` doit être lancé une première fois après l'installation, puis à chaque modification des fiches.

## Évaluation

```bash
python -m scripts.eval_rag          # mesure la qualité des réponses et calibre le seuil de confiance
```

---

## Ajouter ou désactiver une démarche

- **Ajouter une démarche** : copier `data/raw/_modele/MODELE_fiche.md`, y coller le texte exact d'une page officielle avec son lien, puis lancer :
  ```bash
  python -m scripts.validate_raw
  python -m scripts.build_index
  ```
- **Désactiver une fiche obsolète** : mettre `status: inactive` dans son en-tête, puis reconstruire l'index.

---

## Technologies

Python · Streamlit · Gemini (Google) · ChromaDB · BM25 · RAG

## Équipe

- Birama TOGOLA
- Soukeye THIAM
- Abdoul Aziz NDIAYE
- Chérif BAKHOUM
- Ibrahima LY

## Licence

Projet open source, sous licence MIT. Voir le fichier `LICENSE`.
