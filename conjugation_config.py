"""Configuration for the Spanish verb-conjugation practice section.

Defines the fixed, usefulness-ranked tense list (a checklist the user ticks), the
six Spanish person/pronoun slots (vosotros is user-toggleable), and the default
session size. The ``key`` of each tense matches the keys in
``languages/es/conjugations.json`` (and the ``CANONICAL_PRONOUNS`` slot order in
``tools/generate_conjugations.py``).
"""

# Default number of questions per conjugation practice session (adjustable).
CONJ_QUESTIONS_DEFAULT = 10

# Tenses offered, ranked by usefulness. ``key`` matches the conjugations.json
# keys; ``default_on`` seeds which checkboxes start ticked on the settings page.
CONJ_TENSES = [
    {
        "key": "indicativo/presente",
        "label_es": "Presente",
        "label_en": "Present",
        "default_on": True,
    },
    {
        "key": "indicativo/pretérito-perfecto-simple",
        "label_es": "Pretérito indefinido",
        "label_en": "Preterite (simple past)",
        "default_on": False,
    },
    {
        "key": "indicativo/pretérito-imperfecto",
        "label_es": "Pretérito imperfecto",
        "label_en": "Imperfect",
        "default_on": False,
    },
    {
        "key": "indicativo/futuro",
        "label_es": "Futuro",
        "label_en": "Future",
        "default_on": False,
    },
    {
        "key": "condicional/presente",
        "label_es": "Condicional",
        "label_en": "Conditional",
        "default_on": False,
    },
    {
        "key": "indicativo/pretérito-perfecto-compuesto",
        "label_es": "Pretérito perfecto",
        "label_en": "Present perfect",
        "default_on": False,
    },
    {
        "key": "subjuntivo/presente",
        "label_es": "Presente de subjuntivo",
        "label_en": "Present subjunctive",
        "default_on": False,
    },
    {
        "key": "subjuntivo/pretérito-imperfecto-1",
        "label_es": "Imperfecto de subjuntivo",
        "label_en": "Imperfect subjunctive",
        "default_on": False,
    },
    {
        "key": "indicativo/pretérito-pluscuamperfecto",
        "label_es": "Pretérito pluscuamperfecto",
        "label_en": "Past perfect",
        "default_on": False,
    },
    {
        "key": "imperativo/afirmativo",
        "label_es": "Imperativo afirmativo",
        "label_en": "Imperative (affirmative)",
        "default_on": False,
    },
]

CONJ_TENSE_KEYS = {t["key"] for t in CONJ_TENSES}

# The six person slots, in the order stored in conjugations.json. ``optional``
# flags vosotros, which the user can include or exclude. ``label`` is the Spanish
# pronoun shown in the prompt.
CONJ_PERSONS = [
    {"index": 0, "key": "yo", "label": "yo", "optional": False},
    {"index": 1, "key": "tu", "label": "tú", "optional": False},
    {"index": 2, "key": "el", "label": "él/ella/usted", "optional": False},
    {"index": 3, "key": "nosotros", "label": "nosotros", "optional": False},
    {"index": 4, "key": "vosotros", "label": "vosotros", "optional": True},
    {"index": 5, "key": "ellos", "label": "ellos/ellas/ustedes", "optional": False},
]

# The person index that the vosotros toggle controls.
VOSOTROS_INDEX = 4


def tense_label(key: str, ui_lang: str = "en") -> str:
    """Return the display label for a tense key (Spanish or English)."""
    for t in CONJ_TENSES:
        if t["key"] == key:
            return t["label_es"] if ui_lang == "es" else t["label_en"]
    return key


def person_label(index: int) -> str:
    """Return the Spanish pronoun label for a person slot index."""
    for p in CONJ_PERSONS:
        if p["index"] == index:
            return p["label"]
    return ""
