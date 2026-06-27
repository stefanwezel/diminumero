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
        "hint_en": "Drop -ar/-er/-ir and add the present endings; -er and -ir differ only in nosotros/vosotros.",
        "hint_es": "Quita -ar/-er/-ir y añade las terminaciones del presente; -er e -ir solo difieren en nosotros/vosotros.",
    },
    {
        "key": "indicativo/pretérito-perfecto-simple",
        "label_es": "Pretérito indefinido",
        "label_en": "Preterite (simple past)",
        "default_on": False,
        "hint_en": "A finished past action. -ar takes -é, -aste, -ó…; -er/-ir share -í, -iste, -ió…",
        "hint_es": "Una acción terminada en el pasado. -ar usa -é, -aste, -ó…; -er/-ir comparten -í, -iste, -ió…",
    },
    {
        "key": "indicativo/pretérito-imperfecto",
        "label_es": "Pretérito imperfecto",
        "label_en": "Imperfect",
        "default_on": False,
        "hint_en": "Ongoing/repeated past ('used to'). -ar takes -aba…; -er/-ir take -ía…",
        "hint_es": "Pasado continuo o habitual ('solía'). -ar usa -aba…; -er/-ir usan -ía…",
    },
    {
        "key": "indicativo/futuro",
        "label_es": "Futuro",
        "label_en": "Future",
        "default_on": False,
        "hint_en": "Add -é, -ás, -á, -emos, -éis, -án onto the whole infinitive — same for every group.",
        "hint_es": "Añade -é, -ás, -á, -emos, -éis, -án al infinitivo completo — igual para todos los grupos.",
    },
    {
        "key": "condicional/presente",
        "label_es": "Condicional",
        "label_en": "Conditional",
        "default_on": False,
        "hint_en": "Add -ía, -ías, -ía, -íamos, -íais, -ían onto the whole infinitive — same for every group.",
        "hint_es": "Añade -ía, -ías, -ía, -íamos, -íais, -ían al infinitivo completo — igual para todos los grupos.",
    },
    {
        "key": "indicativo/pretérito-perfecto-compuesto",
        "label_es": "Pretérito perfecto",
        "label_en": "Present perfect",
        "default_on": False,
        "hint_en": "Present of haber (he, has, ha, hemos, habéis, han) + the past participle (-ado/-ido).",
        "hint_es": "Presente de haber (he, has, ha, hemos, habéis, han) + el participio (-ado/-ido).",
    },
    {
        "key": "subjuntivo/presente",
        "label_es": "Presente de subjuntivo",
        "label_en": "Present subjunctive",
        "default_on": False,
        "hint_en": "Take the yo present, drop the -o, and swap the vowel: -ar → -e endings, -er/-ir → -a endings.",
        "hint_es": "Parte del yo del presente, quita la -o y cambia la vocal: -ar → terminaciones en -e, -er/-ir → en -a.",
    },
    {
        "key": "subjuntivo/pretérito-imperfecto-1",
        "label_es": "Imperfecto de subjuntivo",
        "label_en": "Imperfect subjunctive",
        "default_on": False,
        "hint_en": "From the ellos preterite stem, add -ra, -ras, -ra, -ramos, -rais, -ran.",
        "hint_es": "Desde la raíz del pretérito de ellos, añade -ra, -ras, -ra, -ramos, -rais, -ran.",
    },
    {
        "key": "indicativo/pretérito-pluscuamperfecto",
        "label_es": "Pretérito pluscuamperfecto",
        "label_en": "Past perfect",
        "default_on": False,
        "hint_en": "Imperfect of haber (había, habías…) + the past participle (-ado/-ido).",
        "hint_es": "Imperfecto de haber (había, habías…) + el participio (-ado/-ido).",
    },
    {
        "key": "imperativo/afirmativo",
        "label_es": "Imperativo afirmativo",
        "label_en": "Imperative (affirmative)",
        "default_on": False,
        "hint_en": "Commands; there is no yo form. tú usually equals the él present (¡habla!, ¡come!).",
        "hint_es": "Órdenes; no hay forma de yo. El tú suele coincidir con el él del presente (¡habla!, ¡come!).",
    },
]

CONJ_TENSE_KEYS = {t["key"] for t in CONJ_TENSES}

# Model verbs (one per -ar/-er/-ir group) used to illustrate a tense's regular
# pattern in the practice "Hint" excerpt. All three are in the global pool.
CONJ_HINT_MODEL_VERBS = ["hablar", "comer", "vivir"]

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


def tense_hint(key: str, ui_lang: str = "en") -> str:
    """Return the one-line pattern explanation for a tense key (Spanish or English)."""
    for t in CONJ_TENSES:
        if t["key"] == key:
            return t["hint_es"] if ui_lang == "es" else t["hint_en"]
    return ""


def person_label(index: int) -> str:
    """Return the Spanish pronoun label for a person slot index."""
    for p in CONJ_PERSONS:
        if p["index"] == index:
            return p["label"]
    return ""
