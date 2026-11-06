"""Loader for the global English verb-conjugation pool.

Reads the committed ``conjugations.json`` (generated offline by the
self-contained rule engine in ``tools/generate_conjugations_en.py``). Person
slots: [I, you, he/she/it, we, they] — five, since "you" has one form for one
person and for several. See ``languages/conjugation_loader.py`` for the shared
implementation.

``conjugation_variants.json`` holds the other forms British usage accepts for a
stored one ("learnt" also "learned"), which the practice check consults.
"""

import json
from functools import cache
from pathlib import Path

from languages.conjugation_loader import ConjugationPool

_DIR = Path(__file__).resolve().parent

pool = ConjugationPool(_DIR / "conjugations.json")

verb_exists = pool.verb_exists
get_verb_forms = pool.get_verb_forms
search_verbs = pool.search_verbs


@cache
def _variants() -> dict[str, dict[str, dict[str, list[str]]]]:
    with (_DIR / "conjugation_variants.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def get_form_variants(infinitive: str, tense_key: str, form: str) -> list[str]:
    """Other accepted forms for one stored form of a verb (often none)."""
    return _variants().get(infinitive, {}).get(tense_key, {}).get(form, [])
