"""Loader for the global Italian verb-conjugation pool.

Reads the committed ``conjugations.json`` (generated offline by
``tools/generate_conjugations_it.py`` via the ``verbecc`` library). Person
slots: [io, tu, lui/lei, noi, voi, loro]. See
``languages/conjugation_loader.py`` for the shared implementation.
"""

from pathlib import Path

from languages.conjugation_loader import ConjugationPool

pool = ConjugationPool(Path(__file__).resolve().parent / "conjugations.json")

verb_exists = pool.verb_exists
get_verb_forms = pool.get_verb_forms
search_verbs = pool.search_verbs
