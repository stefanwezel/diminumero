"""Loader for the global English verb-conjugation pool.

Reads the committed ``conjugations.json`` (generated offline by the
self-contained rule engine in ``tools/generate_conjugations_en.py``). Person
slots: [I, you, he/she/it, we, they] — five, since "you" has one form for one
person and for several. See ``languages/conjugation_loader.py`` for the shared
implementation.

``conjugation_variants.json`` holds the other forms British usage accepts for a
stored one ("learnt" also "learned"), which the practice check consults.
"""

from pathlib import Path

from languages.conjugation_loader import ConjugationPool

_DIR = Path(__file__).resolve().parent

pool = ConjugationPool(
    _DIR / "conjugations.json",
    variants_path=_DIR / "conjugation_variants.json",
    base_form_tense="present-simple",
)

verb_exists = pool.verb_exists
get_verb_forms = pool.get_verb_forms
search_verbs = pool.search_verbs
get_form_variants = pool.get_form_variants
canonical_infinitive = pool.canonical_infinitive
