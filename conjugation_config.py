"""Configuration for the verb-conjugation practice section, per language.

``CONJ_LANGS`` holds one entry per supported conjugation language (Spanish and
German today). Each entry defines the fixed, usefulness-ranked tense list (a
checklist the user ticks), the six person/pronoun slots, which slot (if any) is
optional/user-toggleable (Spanish vosotros; German has none), and the model
verbs used by the practice "Hint" excerpt. The ``key`` of each tense matches
the keys in that language's ``languages/<code>/conjugations.json``.

Tense fields: ``label_native`` (label in the conjugated language) /
``label_en``, and ``hint_native`` / ``hint_en`` (the one-line pattern blurb;
the native variant is shown when the UI language equals the conjugated
language).
"""

# Default number of questions per conjugation practice session (adjustable).
CONJ_QUESTIONS_DEFAULT = 10

CONJ_LANGS = {
    "es": {
        # Tenses offered, ranked by usefulness. ``default_on`` seeds which
        # checkboxes start ticked on the settings page.
        "tenses": [
            {
                "key": "indicativo/presente",
                "label_native": "Presente",
                "label_en": "Present",
                "default_on": True,
                "hint_en": "Drop -ar/-er/-ir and add the present endings; -er and -ir differ only in nosotros/vosotros.",
                "hint_native": "Quita -ar/-er/-ir y añade las terminaciones del presente; -er e -ir solo difieren en nosotros/vosotros.",
            },
            {
                "key": "indicativo/pretérito-perfecto-simple",
                "label_native": "Pretérito indefinido",
                "label_en": "Preterite (simple past)",
                "default_on": False,
                "hint_en": "A finished past action. -ar takes -é, -aste, -ó…; -er/-ir share -í, -iste, -ió…",
                "hint_native": "Una acción terminada en el pasado. -ar usa -é, -aste, -ó…; -er/-ir comparten -í, -iste, -ió…",
            },
            {
                "key": "indicativo/pretérito-imperfecto",
                "label_native": "Pretérito imperfecto",
                "label_en": "Imperfect",
                "default_on": False,
                "hint_en": "Ongoing/repeated past ('used to'). -ar takes -aba…; -er/-ir take -ía…",
                "hint_native": "Pasado continuo o habitual ('solía'). -ar usa -aba…; -er/-ir usan -ía…",
            },
            {
                "key": "indicativo/futuro",
                "label_native": "Futuro",
                "label_en": "Future",
                "default_on": False,
                "hint_en": "Add -é, -ás, -á, -emos, -éis, -án onto the whole infinitive — same for every group.",
                "hint_native": "Añade -é, -ás, -á, -emos, -éis, -án al infinitivo completo — igual para todos los grupos.",
            },
            {
                "key": "condicional/presente",
                "label_native": "Condicional",
                "label_en": "Conditional",
                "default_on": False,
                "hint_en": "Add -ía, -ías, -ía, -íamos, -íais, -ían onto the whole infinitive — same for every group.",
                "hint_native": "Añade -ía, -ías, -ía, -íamos, -íais, -ían al infinitivo completo — igual para todos los grupos.",
            },
            {
                "key": "indicativo/pretérito-perfecto-compuesto",
                "label_native": "Pretérito perfecto",
                "label_en": "Present perfect",
                "default_on": False,
                "hint_en": "Present of haber (he, has, ha, hemos, habéis, han) + the past participle (-ado/-ido).",
                "hint_native": "Presente de haber (he, has, ha, hemos, habéis, han) + el participio (-ado/-ido).",
            },
            {
                "key": "subjuntivo/presente",
                "label_native": "Presente de subjuntivo",
                "label_en": "Present subjunctive",
                "default_on": False,
                "hint_en": "Take the yo present, drop the -o, and swap the vowel: -ar → -e endings, -er/-ir → -a endings.",
                "hint_native": "Parte del yo del presente, quita la -o y cambia la vocal: -ar → terminaciones en -e, -er/-ir → en -a.",
            },
            {
                "key": "subjuntivo/pretérito-imperfecto-1",
                "label_native": "Imperfecto de subjuntivo",
                "label_en": "Imperfect subjunctive",
                "default_on": False,
                "hint_en": "From the ellos preterite stem, add -ra, -ras, -ra, -ramos, -rais, -ran.",
                "hint_native": "Desde la raíz del pretérito de ellos, añade -ra, -ras, -ra, -ramos, -rais, -ran.",
            },
            {
                "key": "indicativo/pretérito-pluscuamperfecto",
                "label_native": "Pretérito pluscuamperfecto",
                "label_en": "Past perfect",
                "default_on": False,
                "hint_en": "Imperfect of haber (había, habías…) + the past participle (-ado/-ido).",
                "hint_native": "Imperfecto de haber (había, habías…) + el participio (-ado/-ido).",
            },
            {
                "key": "imperativo/afirmativo",
                "label_native": "Imperativo afirmativo",
                "label_en": "Imperative (affirmative)",
                "default_on": False,
                "hint_en": "Commands; there is no yo form. tú usually equals the él present (¡habla!, ¡come!).",
                "hint_native": "Órdenes; no hay forma de yo. El tú suele coincidir con el él del presente (¡habla!, ¡come!).",
            },
        ],
        # The six person slots, in the order stored in conjugations.json.
        # ``optional`` flags the slot controlled by the include-toggle.
        "persons": [
            {"index": 0, "key": "yo", "label": "yo", "optional": False},
            {"index": 1, "key": "tu", "label": "tú", "optional": False},
            {"index": 2, "key": "el", "label": "él/ella/usted", "optional": False},
            {"index": 3, "key": "nosotros", "label": "nosotros", "optional": False},
            {"index": 4, "key": "vosotros", "label": "vosotros", "optional": True},
            {
                "index": 5,
                "key": "ellos",
                "label": "ellos/ellas/ustedes",
                "optional": False,
            },
        ],
        # The person index the optional-person toggle controls (vosotros).
        "optional_person_index": 4,
        # Model verbs (one per -ar/-er/-ir group) used to illustrate a tense's
        # regular pattern in the practice "Hint" excerpt. All in the global pool.
        "hint_model_verbs": ["hablar", "comer", "vivir"],
    },
    "de": {
        "tenses": [
            {
                "key": "indikativ/praesens",
                "label_native": "Präsens",
                "label_en": "Present",
                "default_on": True,
                "hint_en": "Drop -en/-n and add -e, -st, -t, -en, -t, -en; many strong verbs change their vowel in du/er (fahren → du fährst).",
                "hint_native": "Streiche -en/-n und hänge -e, -st, -t, -en, -t, -en an; viele starke Verben ändern in du/er den Vokal (fahren → du fährst).",
            },
            {
                "key": "indikativ/praeteritum",
                "label_native": "Präteritum",
                "label_en": "Simple past",
                "default_on": False,
                "hint_en": "Weak verbs insert -te- (machte, machtest…); strong verbs change the stem vowel and take no -te (fuhr, fuhrst…).",
                "hint_native": "Schwache Verben schieben -te- ein (machte, machtest…); starke Verben ändern den Stammvokal ohne -te (fuhr, fuhrst…).",
            },
            {
                "key": "indikativ/perfekt",
                "label_native": "Perfekt",
                "label_en": "Present perfect",
                "default_on": False,
                "hint_en": "Present of haben or sein + Partizip II (ge-…-t for weak verbs, ge-…-en for strong ones).",
                "hint_native": "Präsens von haben oder sein + Partizip II (ge-…-t bei schwachen, ge-…-en bei starken Verben).",
            },
            {
                "key": "indikativ/plusquamperfekt",
                "label_native": "Plusquamperfekt",
                "label_en": "Past perfect",
                "default_on": False,
                "hint_en": "Präteritum of haben/sein (hatte, war…) + Partizip II.",
                "hint_native": "Präteritum von haben/sein (hatte, war…) + Partizip II.",
            },
            {
                "key": "indikativ/futur-1",
                "label_native": "Futur I",
                "label_en": "Future",
                "default_on": False,
                "hint_en": "Present of werden (werde, wirst, wird…) + the infinitive.",
                "hint_native": "Präsens von werden (werde, wirst, wird…) + Infinitiv.",
            },
            {
                "key": "konjunktiv-2",
                "label_native": "Konjunktiv II",
                "label_en": "Conditional",
                "default_on": False,
                "hint_en": "würde + infinitive for most verbs; sein, haben, werden, the modals and wissen use their own forms (wäre, hätte, könnte…).",
                "hint_native": "Meist würde + Infinitiv; sein, haben, werden, die Modalverben und wissen haben eigene Formen (wäre, hätte, könnte…).",
            },
            {
                "key": "imperativ",
                "label_native": "Imperativ",
                "label_en": "Imperative",
                "default_on": False,
                "hint_en": "du: bare stem (mach!); ihr: present form (macht!); Sie: infinitive + Sie (machen Sie!). No ich/er/wir forms.",
                "hint_native": "du: bloßer Stamm (mach!); ihr: Präsensform (macht!); Sie: Infinitiv + Sie (machen Sie!). Keine ich/er/wir-Formen.",
            },
        ],
        "persons": [
            {"index": 0, "key": "ich", "label": "ich", "optional": False},
            {"index": 1, "key": "du", "label": "du", "optional": False},
            {"index": 2, "key": "er", "label": "er/sie/es", "optional": False},
            {"index": 3, "key": "wir", "label": "wir", "optional": False},
            {"index": 4, "key": "ihr", "label": "ihr", "optional": False},
            {"index": 5, "key": "sie", "label": "sie/Sie", "optional": False},
        ],
        # German has no optional person slot (all six are standard).
        "optional_person_index": None,
        # One weak verb, one weak verb with linking -e-, one strong verb.
        "hint_model_verbs": ["machen", "arbeiten", "fahren"],
    },
}


def conj_tenses(lang: str) -> list[dict]:
    return CONJ_LANGS[lang]["tenses"]


def conj_tense_keys(lang: str) -> set[str]:
    return {t["key"] for t in CONJ_LANGS[lang]["tenses"]}


def conj_persons(lang: str) -> list[dict]:
    return CONJ_LANGS[lang]["persons"]


def conj_optional_person_index(lang: str) -> int | None:
    """Index of the user-toggleable person slot (vosotros), or None."""
    return CONJ_LANGS[lang]["optional_person_index"]


def conj_hint_model_verbs(lang: str) -> list[str]:
    return CONJ_LANGS[lang]["hint_model_verbs"]


def tense_label(lang: str, key: str, ui_lang: str = "en") -> str:
    """Display label for a tense key (native when the UI is in that language)."""
    for t in CONJ_LANGS[lang]["tenses"]:
        if t["key"] == key:
            return t["label_native"] if ui_lang == lang else t["label_en"]
    return key


def tense_hint(lang: str, key: str, ui_lang: str = "en") -> str:
    """One-line pattern explanation for a tense key."""
    for t in CONJ_LANGS[lang]["tenses"]:
        if t["key"] == key:
            return t["hint_native"] if ui_lang == lang else t["hint_en"]
    return ""


def person_label(lang: str, index: int) -> str:
    """Pronoun label for a person slot index."""
    for p in CONJ_LANGS[lang]["persons"]:
        if p["index"] == index:
            return p["label"]
    return ""
