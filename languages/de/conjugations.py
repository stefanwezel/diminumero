"""Loader for the global German verb-conjugation pool.

Reads the committed ``conjugations.json`` (generated offline by the
self-contained rule engine in ``tools/generate_conjugations_de.py``). Person
slots: [ich, du, er/sie/es, wir, ihr, sie/Sie]. See
``languages/conjugation_loader.py`` for the shared implementation.
"""

from pathlib import Path

from languages.conjugation_loader import ConjugationPool

pool = ConjugationPool(Path(__file__).resolve().parent / "conjugations.json")

verb_exists = pool.verb_exists
get_verb_forms = pool.get_verb_forms
search_verbs = pool.search_verbs
