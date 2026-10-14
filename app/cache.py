"""Cache persistant de TEKTALMA (SQLite, dans data/cache/).

Deux niveaux de réponses :
- "q" : la question telle qu'écrite (début de conversation)  -> 0 appel à Gemini ;
- "s" : la question reformulée en français par la compréhension -> pas de rédaction.

Une question similaire peut réutiliser une réponse, avec trois garde-fous :
même langue, mêmes mots-clés de démarche (carte ≠ passeport, perte ≠ coût…)
et similarité sémantique très élevée.

Le cache est lié à une empreinte du corpus (fiches officielles + exemples wolof) :
si une fiche change et que l'index est reconstruit, les anciennes réponses sont ignorées.
Les voix générées sont aussi conservées.
"""
import hashlib
import json
import re
import sqlite3
import threading
import time
import unicodedata

import numpy as np

from config import settings

# Mots-clés de démarche -> concept. Deux questions ne partagent une réponse
# que si elles ont EXACTEMENT les mêmes concepts.
DOMAIN_TERMS = {
    "cni": ["carte", "cni", "identite", "nationale"],
    "passeport": ["passeport", "passport"],
    "naissance": ["naissance", "birth", "naitre"],
    "extrait": ["extrait", "extract", "acte", "copie", "litterale"],
    "nationalite": ["nationalite", "nationality"],
    "mariage": ["mariage", "marriage"],
    "deces": ["deces", "death"],
    "perte": ["perdu", "perdue", "perte", "vol", "vole", "volee", "nakk", "lost", "stolen", "lose"],
    "renouvellement": ["renouveler", "renouvellement", "renew", "renewal", "expire", "expiree",
                       "perime", "perimee"],
    "cout": ["prix", "cout", "coute", "combien", "tarif", "frais", "naata", "njeg", "jar",
             "cost", "price", "fee"],
    "delai": ["delai", "temps", "duree", "jours", "time", "long"],
    "pieces": ["document", "documents", "piece", "pieces", "papiers", "dossier", "kayit", "fournir"],
    "lieu": ["fan", "where", "adresser", "lieu", "bureau"],
    "etranger": ["etranger", "diaspora", "france", "abroad", "consulat", "ambassade", "bitim"],
    "declaration": ["declarer", "declaration", "declare", "register"],
    "transcription": ["transcription", "transcrire"],
}
_WORD_TO_CONCEPT = {w: c for c, words in DOMAIN_TERMS.items() for w in words}
_EN_WORDS = {"the", "how", "what", "where", "my", "is", "do", "does", "can", "i", "get", "much", "lost"}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def concepts(text: str) -> str:
    return ",".join(sorted({_WORD_TO_CONCEPT[w] for w in norm(text).split() if w in _WORD_TO_CONCEPT}))


def guess_lang(text: str) -> str:
    """Langue probable d'une question écrite, sans appel au LLM."""
    from app.guards import looks_wolof

    if looks_wolof(text or ""):
        return "wo"
    return "en" if len(set(norm(text).split()) & _EN_WORDS) >= 2 else "fr"


def corpus_version() -> str:
    h = hashlib.sha1()
    for path in (settings.FICHES_FILE, settings.DATA_DIR / "wolof_exemples.yaml"):
        if path.exists():
            h.update(path.read_bytes())
    return h.hexdigest()[:12]


class Cache:
    def __init__(self, path=None):
        self.path = path or settings.CACHE_DIR / "tektalma_cache.sqlite"
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS answers (
                    key TEXT PRIMARY KEY, level TEXT, lang TEXT, text TEXT, concepts TEXT,
                    vec BLOB, answer TEXT, version TEXT, created REAL, hits INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS audio (
                    key TEXT PRIMARY KEY, mime TEXT, data BLOB, created REAL);
            """)
            self.db.commit()
        self.refresh()

    # ------------------------------------------------------------------ gestion
    def refresh(self):
        """Recharge l'empreinte du corpus et purge ce qui est périmé."""
        self.version = corpus_version()
        cutoff = time.time() - settings.CACHE_TTL_DAYS * 86400
        with self.lock:
            self.db.execute("DELETE FROM answers WHERE version != ? OR created < ?", (self.version, cutoff))
            self.db.execute("DELETE FROM audio WHERE created < ?", (cutoff,))
            self.db.commit()
            rows = self.db.execute("SELECT key, level, lang, concepts, vec FROM answers").fetchall()
        self.index = [(k, lv, lg, c, np.frombuffer(v, dtype=np.float32)) for k, lv, lg, c, v in rows if v]

    def stats(self):
        with self.lock:
            n = self.db.execute("SELECT level, lang, COUNT(*), SUM(hits) FROM answers GROUP BY level, lang").fetchall()
            a = self.db.execute("SELECT COUNT(*) FROM audio").fetchone()[0]
        return n, a

    def clear(self):
        with self.lock:
            self.db.execute("DELETE FROM answers")
            self.db.execute("DELETE FROM audio")
            self.db.commit()
        self.index = []

    # ------------------------------------------------------------------ réponses
    @staticmethod
    def _key(level, lang, text):
        return hashlib.sha1(f"{level}|{lang}|{norm(text)}".encode()).hexdigest()

    def lookup(self, level, text, lang, embed):
        """Renvoie (dict de la réponse, "exact" | "similaire") ou (None, None)."""
        if not text:
            return None, None
        key = self._key(level, lang, text)
        with self.lock:
            row = self.db.execute("SELECT answer FROM answers WHERE key = ?", (key,)).fetchone()
        match = "exact" if row else None
        if not row:
            wanted = concepts(text)
            candidates = [(k, v) for k, lv, lg, c, v in self.index if lv == level and lg == lang and c == wanted]
            if wanted and candidates:          # sans mot-clé de démarche : jamais de rapprochement
                q = np.asarray(embed(text), dtype=np.float32)
                q /= np.linalg.norm(q) or 1.0
                k, v = max(candidates, key=lambda kv: float(kv[1] @ q))
                if float(v @ q) >= settings.CACHE_SIMILARITY:
                    key, match = k, "similaire"
                    with self.lock:
                        row = self.db.execute("SELECT answer FROM answers WHERE key = ?", (key,)).fetchone()
        if not row:
            return None, None
        with self.lock:
            self.db.execute("UPDATE answers SET hits = hits + 1 WHERE key = ?", (key,))
            self.db.commit()
        return json.loads(row[0]), match

    def store(self, level, text, lang, answer: dict, embed):
        if not text:
            return
        v = np.asarray(embed(text), dtype=np.float32)
        v /= np.linalg.norm(v) or 1.0
        key = self._key(level, lang, text)
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO answers (key, level, lang, text, concepts, vec, answer, version, created)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, level, lang, text, concepts(text), v.tobytes(),
                 json.dumps(answer, ensure_ascii=False), self.version, time.time()))
            self.db.commit()
        self.index = [e for e in self.index if e[0] != key] + [(key, level, lang, concepts(text), v)]

    # ------------------------------------------------------------------ voix
    def get_audio(self, key):
        with self.lock:
            row = self.db.execute("SELECT data, mime FROM audio WHERE key = ?", (key,)).fetchone()
        return (bytes(row[0]), row[1]) if row else None

    def put_audio(self, key, data: bytes, mime: str):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO audio VALUES (?, ?, ?, ?)", (key, mime, data, time.time()))
            self.db.commit()


_instance = None


def get_cache() -> Cache:
    global _instance
    if _instance is None:
        _instance = Cache()
    return _instance
