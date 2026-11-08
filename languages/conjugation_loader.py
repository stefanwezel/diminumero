"""Shared loader for a language's committed verb-conjugation pool.

Each conjugation language has a ``languages/<code>/conjugations.json``
(generated offline — see ``tools/generate_conjugations*.py``) and a thin
``languages/<code>/conjugations.py`` module that instantiates
:class:`ConjugationPool` and re-exports its methods, so callers can keep using
the module-level function API (``verb_exists``, ``get_verb_forms``,
``search_verbs``).

JSON shape::

    { "comer": { "indicativo/presente": ["como", "comes", ...], ... }, ... }

Each tense maps to a list with one element per person slot of the language (see
``conjugation_config.CONJ_LANGS``; six, or five for English); a slot may be null
when the tense has no form for that person (e.g. imperatives lack a first-person
singular).

A language may also ship a variants file, the other forms accepted for a stored
one (see ``languages/en/conjugation_variants.json``)::

    { "learn": { "past-simple": { "learnt": ["learned"] }, ... }, ... }
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

    def __init__(
        self,
        data_path: Path,
        variants_path: Path | None = None,
        base_form_tense: str | None = None,
    ):
        """``base_form_tense`` names the tense with a cell spelled like the
        infinitive, so another spelling of that cell is another spelling of the
        verb ("realise" also "realize"). Only meaningful with a variants file.
        """
        self._data_path = data_path
        self._variants_path = variants_path
        self._base_form_tense = base_form_tense

    @cached_property
    def _data(self) -> dict[str, dict[str, list]]:
        with self._data_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def _variants(self) -> dict[str, dict[str, dict[str, list[str]]]]:
        if self._variants_path is None:
            return {}
        with self._variants_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @cached_property
    def _infinitive_spellings(self) -> dict[str, str]:
        """Other spelling of an infinitive -> the one the pool stores it under."""
        return {
            other: verb
            for verb, tenses in self._variants.items()
            for other in tenses.get(self._base_form_tense, {}).get(verb, [])
        }

    @cached_property
    def global_verbs(self) -> list[str]:
        """Sorted infinitive list (for stable display/listing)."""
        return sorted(self._data.keys())

    @cached_property
    def _folded_index(self) -> list[tuple[str, str]]:
        """List of (folded_infinitive, infinitive) in the JSON's frequency order.

        The JSON preserves the generator's frequency ranking, so prefix-search
        results come back most-common-first (e.g. "co" surfaces "comer" early).
        A verb's other spellings sit right after it, so they rank the same.
        """
        others: dict[str, list[str]] = {}
        for other, verb in self._infinitive_spellings.items():
            others.setdefault(verb, []).append(other)
        return [
            (_fold(spelling), verb)
            for verb in self._data
            for spelling in (verb, *others.get(verb, []))
        ]

    def canonical_infinitive(self, infinitive: str) -> str:
        """The stored spelling of an infinitive; anything else comes back as is."""
        return self._infinitive_spellings.get(infinitive, infinitive)

    def get_form_variants(
        self, infinitive: str, tense_key: str, form: str
    ) -> list[str]:
        """Other accepted forms for one stored form of a verb (often none)."""
        return self._variants.get(infinitive, {}).get(tense_key, {}).get(form, [])

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

    def top_verbs(self, limit: int, exclude: set[str] | None = None) -> list[str]:
        """The ``limit`` most frequent infinitives (the JSON is frequency-ordered)."""
        exclude = exclude or set()
        return [verb for verb in self._data if verb not in exclude][:limit]

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
        # Two spellings of one verb can both match ("reali" hits realise and realize).
        return list(dict.fromkeys(matches))[:limit]
