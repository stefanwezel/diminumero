"""Loader for the global Spanish verb-conjugation pool.

Reads the committed ``conjugations.json`` (generated offline by
``tools/generate_conjugations.py`` via the ``verbecc`` library) and exposes
lightweight lookup helpers. The data is loaded once and cached at module level.

JSON shape::

    { "comer": { "indicativo/presente": ["como","comes","come","comemos","coméis","comen"], ... }, ... }

Each tense maps to a 6-element list aligned to the person slots
[yo, tú, él/ella/usted, nosotros, vosotros, ellos/ellas/ustedes]; a slot may be
null when the tense has no form for that person (e.g. imperativo lacks "yo").
"""

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "conjugations.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, list]]:
    with _DATA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _global_verbs() -> list[str]:
    """Sorted infinitive list (for stable display/listing)."""
    return sorted(_load().keys())


def _fold(text: str) -> str:
    """Lowercase + strip accents for forgiving prefix search."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _folded_index() -> list[tuple[str, str]]:
    """List of (folded_infinitive, infinitive) in the JSON's frequency order.

    The JSON preserves the generator's frequency ranking, so prefix-search
    results come back most-common-first (e.g. "co" surfaces "comer" early).
    """
    return [(_fold(v), v) for v in _load().keys()]


# Lazy module attribute (PEP 562): `conjugations.GLOBAL_VERBS` returns the sorted
# infinitive list without forcing the JSON load at import time.
def __getattr__(name: str):
    if name == "GLOBAL_VERBS":
        return _global_verbs()
    raise AttributeError(name)


def verb_exists(infinitive: str) -> bool:
    """True if the infinitive is in the global pool (exact, case-insensitive)."""
    if not infinitive:
        return False
    key = infinitive.strip().lower()
    return key in _load()


def get_verb_forms(infinitive: str) -> dict[str, list] | None:
    """Return the tense->forms map for a verb, or None if not in the pool."""
    if not infinitive:
        return None
    return _load().get(infinitive.strip().lower())


def search_verbs(prefix: str, limit: int = 8, exclude: set[str] | None = None) -> list[str]:
    """Return up to ``limit`` pool infinitives starting with ``prefix``.

    Matching is accent- and case-insensitive. Exact-prefix matches are ranked
    before the alphabetical remainder. ``exclude`` (a set of infinitives) is
    filtered out — used to hide verbs the user has already added.
    """
    folded_prefix = _fold(prefix)
    if not folded_prefix:
        return []
    exclude = exclude or set()
    matches = [
        verb
        for folded, verb in _folded_index()
        if folded.startswith(folded_prefix) and verb not in exclude
    ]
    return matches[:limit]
