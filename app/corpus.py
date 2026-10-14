"""Lecture des fiches officielles (data/raw) et découpage par rubrique."""
import hashlib
from pathlib import Path

import yaml

from config import settings

SECTION_RULES = [
    ("perte", ("perte", "vol")),
    ("renouvellement", ("renouvel",)),
    ("pieces", ("pièce", "piece", "document", "fournir", "présenter")),
    ("cout", ("coût", "cout", "prix", "frais")),
    ("delai", ("délai", "delai", "traitement")),
    ("validite", ("validité", "validite", "durée")),
    ("ou", ("où", "adresser", "déposer")),
    ("qui", ("qui peut",)),
]


def section_key(heading: str) -> str:
    h = heading.lower()
    for key, words in SECTION_RULES:
        if any(w in h for w in words):
            return key
    return "general"


def parse_fiche(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    _, header, body = text.split("---", 2)
    return yaml.safe_load(header) or {}, body.strip()


def split_sections(body: str):
    sections, heading, lines = [], "Informations", []
    for line in body.splitlines():
        if line.startswith("## "):
            if "".join(lines).strip():
                sections.append((heading, "\n".join(lines).strip()))
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    if "".join(lines).strip():
        sections.append((heading, "\n".join(lines).strip()))
    return sections


def _clean(value):
    return "" if value is None else value if isinstance(value, (int, float)) else str(value)


def load_fiches():
    """Charge toutes les fiches actives (hors dossier _modele)."""
    fiches = []
    for path in sorted(settings.RAW_DIR.rglob("*.md")):
        if "_modele" in path.parts:
            continue
        meta, body = parse_fiche(path)
        if str(meta.get("status", "active")).lower() != "active":
            continue  # désactiver une fiche = status: inactive puis reconstruire l'index
        meta = {k: _clean(v) for k, v in meta.items()}
        meta["fiche"] = path.stem
        meta["country"] = "SN"
        sections = split_sections(body)
        full_text = "\n\n".join(f"{h} :\n{t}" for h, t in sections)
        fiches.append({
            "doc_id": hashlib.sha1(meta["url"].encode()).hexdigest()[:12],
            "meta": meta,
            "sections": sections,
            "full_text": full_text,
        })
    return fiches


def build_chunks(fiches):
    """Un chunk = une rubrique, préfixée par le titre de la démarche."""
    chunks = []
    for f in fiches:
        for i, (heading, text) in enumerate(f["sections"]):
            key = section_key(heading)
            chunks.append({
                "id": f"{f['doc_id']}__{i:02d}_{key}",
                "doc_id": f["doc_id"],
                "text": f"{f['meta']['title']} › {heading}\n{text}",
                "metadata": {**f["meta"], "doc_id": f["doc_id"],
                             "section": key, "heading": heading},
            })
    return chunks
