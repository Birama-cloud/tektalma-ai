"""Garde-fous après génération : citations valides et chiffres vérifiés."""
import re

CITE_RE = re.compile(r"\[S(\d+)\]")
NUM_RE = re.compile(r"\d[\d\u202f\u00a0 .,]*\d|\d")
LIST_PREFIX_RE = re.compile(r"^\s*(\d+[.)]|[-*•])\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _norm(num: str) -> str:
    return re.sub(r"[\s\u202f\u00a0.,]", "", num)


def clean_citations(answer: str, n_sources: int):
    """Supprime les [Sx] qui ne correspondent à aucune source fournie."""
    used = set()

    def repl(m):
        n = int(m.group(1))
        if 1 <= n <= n_sources:
            used.add(n)
            return m.group(0)
        return ""

    cleaned = CITE_RE.sub(repl, answer)
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)
    return cleaned, sorted(used)


def check_numbers(answer: str, context: str):
    """Retire toute phrase contenant un chiffre absent des sources."""
    allowed = {_norm(n) for n in NUM_RE.findall(context)}
    removed, kept_lines = [], []
    for line in answer.splitlines():
        prefix = LIST_PREFIX_RE.match(line)
        body = line[prefix.end():] if prefix else line
        kept = []
        for sentence in SENTENCE_SPLIT_RE.split(body):
            nums = [_norm(n) for n in NUM_RE.findall(CITE_RE.sub("", sentence))]
            if any(n and n not in allowed for n in nums):
                removed.append(sentence)
            else:
                kept.append(sentence)
        if kept and " ".join(kept).strip():
            kept_lines.append((prefix.group(0) if prefix else "") + " ".join(kept))
        elif not body.strip():
            kept_lines.append(line)
    return "\n".join(kept_lines).strip(), removed


def allowed_numbers(context: str) -> set:
    return {_norm(n) for n in NUM_RE.findall(context)}


def is_supported(text: str, allowed: set) -> bool:
    """Vrai si tous les chiffres du texte figurent dans les sources."""
    return all(_norm(n) in allowed for n in NUM_RE.findall(CITE_RE.sub("", text)) if _norm(n))


# ---------------------------------------------------------------- cohérence de langue
WOLOF_MARKERS = re.compile(
    r"[ñëŋÑËŊ]|\b(ngir|nga|ngaa|nekk|dafa|dafay|mooy|dinga|damay|waaye|nañu|lañu|yépp|"
    r"jërëjëf|salaam|aleekum|bu|bi|yi|gi|ci sa|war na|mën na|amul|nekkul)\b",
    re.IGNORECASE)
_WO_STRONG = re.compile(r"[ñëŋÑËŊ]|\b(ngir|dafay|mooy|dinga|damay|nañu|lañu|yépp|jërëjëf|aleekum)\b",
                        re.IGNORECASE)


def looks_wolof(text: str) -> bool:
    """Vrai si la phrase contient un marqueur wolof fort, ou au moins 2 marqueurs faibles."""
    clean = CITE_RE.sub("", text)
    return bool(_WO_STRONG.search(clean)) or len(WOLOF_MARKERS.findall(clean)) >= 2


def keep_language(text: str, lang: str) -> str:
    """Pour une réponse fr/en : retire toute phrase écrite en wolof."""
    if lang == "wo" or not text:
        return text
    lines = []
    for line in text.splitlines():
        prefix = LIST_PREFIX_RE.match(line)
        body = line[prefix.end():] if prefix else line
        kept = [s for s in SENTENCE_SPLIT_RE.split(body) if not looks_wolof(s)]
        if " ".join(kept).strip():
            lines.append((prefix.group(0) if prefix else "") + " ".join(kept))
        elif not body.strip():
            lines.append(line)
    return "\n".join(lines).strip()
