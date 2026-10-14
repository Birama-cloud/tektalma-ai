"""Vérifie les fiches copiées à la main dans data/raw/.

Lancer depuis la racine du projet :  python -m scripts.validate_raw
"""
from urllib.parse import urlparse

import yaml

from config import settings

REQUIRED = [
    "title", "organisme", "url", "source_type", "reliability", "language",
    "category", "subcategory", "action", "collected_at", "status",
]
ALLOWED_DOMAINS = ("e-senegal.sn", "senegalservices.sn", "gouv.sn", "apix.sn", "daf.sn")
CATEGORIES = {"identite", "passeport", "etat_civil", "education",
              "entrepreneuriat", "fiscalite", "justice", "autres"}
ACTIONS = {"premiere_demande", "renouvellement", "perte", "modification", "general"}
PLACEHOLDERS = ("Copier ici", "Texte exact", "SUPPRIMER")


def read_fiche(path):
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise ValueError("pas d'en-tête '---' au début du fichier")
    _, header, body = text.split("---", 2)
    return yaml.safe_load(header) or {}, body.strip()


def check(path):
    errors = []
    try:
        meta, body = read_fiche(path)
    except Exception as e:  # noqa: BLE001
        return [f"lecture impossible : {e}"]

    for field in REQUIRED:
        if meta.get(field) in (None, ""):
            errors.append(f"champ manquant : {field}")

    domain = urlparse(str(meta.get("url", ""))).netloc.lower()
    if domain and not any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS):
        errors.append(f"domaine non officiel ou non validé : {domain}")
    if meta.get("category") and meta["category"] not in CATEGORIES:
        errors.append(f"catégorie inconnue : {meta['category']}")
    if meta.get("action") and meta["action"] not in ACTIONS:
        errors.append(f"action inconnue : {meta['action']}")
    if "## " not in body:
        errors.append("aucune rubrique '## ' dans le texte")
    if len(body) < 200:
        errors.append(f"texte trop court ({len(body)} caractères)")
    for p in PLACEHOLDERS:
        if p in body:
            errors.append(f"texte du modèle encore présent : '{p}'")
    return errors


if __name__ == "__main__":
    files = sorted(
        f for f in settings.RAW_DIR.rglob("*.md") if "_modele" not in f.parts
    )
    if not files:
        print("Aucune fiche trouvée dans data/raw/ (hors _modele).")
    ok = 0
    for f in files:
        errs = check(f)
        rel = f.relative_to(settings.RAW_DIR)
        if errs:
            print(f"❌ {rel}")
            for e in errs:
                print(f"     - {e}")
        else:
            ok += 1
            print(f"✅ {rel}")
    print(f"\n{ok}/{len(files)} fiche(s) valide(s).")
