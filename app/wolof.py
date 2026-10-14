"""Traduction français -> wolof guidée par un guide de style et des exemples validés par l'équipe."""
import json

import yaml

from app.guards import allowed_numbers, is_supported
from app.understanding import parse_json
from config import settings

EXAMPLES_FILE = settings.DATA_DIR / "wolof_exemples.yaml"

STYLE = """Tu es traducteur professionnel français -> wolof pour un service public sénégalais.
Règles :
- Wolof courant de Dakar, naturel, comme un agent d'accueil qui parle poliment à un citoyen. Phrases courtes et simples.
- Orthographe wolof standard : é, ë, ñ, ŋ, à, ó ; voyelles longues et consonnes doublées (aa, ee, oo, kk, ll...).
- GARDE EN FRANÇAIS les termes administratifs et noms propres : carte nationale d'identité, passeport, extrait de naissance,
  certificat de résidence, certificat de nationalité, quittance, timbre, commissariat, brigade de gendarmerie, préfecture,
  sous-préfecture, mairie, centre d'état civil, consulat, ambassade, DAF, DPETV, FCFA, noms de villes et de pays.
- Garde EXACTEMENT les chiffres, montants et marqueurs [S1], [S2].
- Garde la mise en forme (listes, retours à la ligne).
- N'ajoute et ne retire aucune information.
Suis le style des EXEMPLES validés par des locuteurs."""


def _examples() -> str:
    try:
        pairs = yaml.safe_load(EXAMPLES_FILE.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError):
        return ""
    return "\n".join(f"FR : {p['fr']}\nWO : {p['wo']}" for p in pairs if p.get("fr") and p.get("wo"))


def _system():
    ex = _examples()
    return STYLE + (f"\n\nEXEMPLES :\n{ex}" if ex else "")


def style_guide() -> str:
    """Guide de style + exemples validés, réutilisé par la génération bilingue."""
    return _system()


def to_wolof(llm, text_fr: str) -> str | None:
    """Traduit un texte ; None si la traduction change ou invente un chiffre."""
    out = llm.generate(f"Traduis en wolof. Réponds uniquement par la traduction.\n\n{text_fr}",
                       system=_system(), temperature=0.2)
    return out if out and is_supported(out, allowed_numbers(text_fr)) else None


def fiche_to_wolof(llm, fiche: dict) -> dict:
    """Traduit les valeurs d'une fiche (JSON) ; garde le français pour toute valeur douteuse."""
    raw = llm.generate(
        "Traduis en wolof toutes les VALEURS texte de ce JSON (pas les clés). "
        "Réponds uniquement avec le JSON, mêmes clés, même structure.\n\n"
        + json.dumps(fiche, ensure_ascii=False),
        system=_system(), json_mode=True, temperature=0.2)
    try:
        wo = parse_json(raw)
    except ValueError:
        return fiche
    result = {}
    for key, value in fiche.items():
        new = wo.get(key)
        if isinstance(value, list) and isinstance(new, list) and len(new) == len(value):
            result[key] = [n if isinstance(n, str) and is_supported(n, allowed_numbers(v)) else v
                           for v, n in zip(value, new)]
        elif isinstance(value, str) and isinstance(new, str) and is_supported(new, allowed_numbers(value)):
            result[key] = new
        else:
            result[key] = value
    return result
