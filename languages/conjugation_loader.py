"""Shared loader for a language's committed verb-conjugation pool.

Each conjugation language has a ``languages/<code>/conjugations.json``
(generated offline — see ``tools/generate_conjugations*.py``) and a thin
``languages/<code>/conjugations.py`` module that instantiates
:class:`ConjugationPool` and re-exports its methods, so callers can keep using
the module-level function API (``verb_exists``, ``get_verb_forms``,
``search_verbs``).

JSON shape::

    { "comer": { "indicativo/presente": ["como", "comes", ...], ... }, ... }

Each tense maps to a 6-element list aligned to the language's person slots
(see ``conjugation_config.CONJ_LANGS``); a slot may be null when the tense has
no form for that person (e.g. imperatives lack a first-person singular).
"""

import json
import unicodedata
from functools import cached_property
from pathlib import Path


def _fold(text: str) -> str:
    """Lowercase + strip accents for forgiving prefix search."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


class ConjugationPool:
    """Lazy, cached view over one language's conjugations.json."""

    def __init__(self, data_path: Path):
        self._data_path = data_path

    @cached_property
    def _data(self) -> dict[str, dict[str, list]]:
        with self._data_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def global_verbs(self) -> list[str]:
        """Sorted infinitive list (for stable display/listing)."""
        return sorted(self._data.keys())

    @cached_property
    def _folded_index(self) -> list[tuple[str, str]]:
        """List of (folded_infinitive, infinitive) in the JSON's frequency order.

        The JSON preserves the generator's frequency ranking, so prefix-search
        results come back most-common-first (e.g. "co" surfaces "comer" early).
        """
        return [(_fold(v), v) for v in self._data.keys()]

    def verb_exists(self, infinitive: str) -> bool:
        """True if the infinitive is in the pool (exact, case-insensitive)."""
        if not infinitive:
            return False
        return infinitive.strip().lower() in self._data

    def get_verb_forms(self, infinitive: str) -> dict[str, list] | None:
        """Return the tense->forms map for a verb, or None if not in the pool."""
        if not infinitive:
            return None
        return self._data.get(infinitive.strip().lower())

    def search_verbs(
        self, prefix: str, limit: int = 8, exclude: set[str] | None = None
    ) -> list[str]:
        """Return up to ``limit`` pool infinitives starting with ``prefix``.

        Matching is accent- and case-insensitive, in the pool's frequency
        order. ``exclude`` (a set of infinitives) is filtered out — used to
        hide verbs the user has already added.
        """
        folded_prefix = _fold(prefix)
        if not folded_prefix:
            return []
        exclude = exclude or set()
        matches = [
            verb
            for folded, verb in self._folded_index
            if folded.startswith(folded_prefix) and verb not in exclude
        ]
        return matches[:limit]
