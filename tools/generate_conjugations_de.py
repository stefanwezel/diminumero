# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Generate the global German verb-conjugation pool used by the Conjugation quiz.

Unlike the Spanish generator (which drives the `verbecc` library), German isn't
covered by verbecc, so this script is a small self-contained conjugation engine:
regular ("weak") verbs are built by rule, and every strong / mixed / modal verb
in the pool carries an explicit entry in IRREGULAR (stem changes, Präteritum
stem, Partizip II, auxiliary). Separable verbs are listed in SEPARABLE and are
conjugated from their base verb ("aufstehen" → "stehe auf" / "aufgestanden").

The JSON shape matches the Spanish pool:

    {
      "machen": {
        "indikativ/praesens": ["mache", "machst", "macht", "machen", "macht", "machen"],
        ...
      },
      ...
    }

Each tense maps to a 6-element list aligned to the canonical persons
[ich, du, er/sie/es, wir, ihr, sie/Sie]. A slot is null when the tense has no
form for that person (e.g. Imperativ only has du/ihr/Sie forms; modals have no
imperative at all).

Composite tenses are stored as full multi-word strings ("habe gemacht",
"werde aufstehen") — answer checking is word-based, so that Just Works.
Konjunktiv II follows the textbook convention: sein/haben/werden, the modals
and wissen use their real one-word forms (wäre, hätte, könnte …); every other
verb uses "würde + Infinitiv".

Usage:
    uv run tools/generate_conjugations_de.py            # generate everything
    uv run tools/generate_conjugations_de.py --limit 20 # quick test on first 20 verbs
"""

import argparse
import json
import sys
from pathlib import Path

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "languages" / "de" / "conjugations.json"
)

TENSES = [
    "indikativ/praesens",
    "indikativ/praeteritum",
    "indikativ/perfekt",
    "indikativ/plusquamperfekt",
    "indikativ/futur-1",
    "konjunktiv-2",
    "imperativ",
]

CANONICAL_PRONOUNS = ["ich", "du", "er/sie/es", "wir", "ihr", "sie/Sie"]

VOWELS = "aeiouäöü"

# Frequency-ranked pool. Order is preserved in the JSON so autocomplete ranks
# common verbs first. Every strong/mixed/modal verb here must have an entry in
# IRREGULAR (or FULL_OVERRIDES); everything else is conjugated as a weak verb.
POPULAR_VERBS = [
    "sein",
    "haben",
    "werden",
    "können",
    "müssen",
    "sagen",
    "machen",
    "geben",
    "kommen",
    "sollen",
    "wollen",
    "gehen",
    "wissen",
    "sehen",
    "lassen",
    "stehen",
    "finden",
    "bleiben",
    "liegen",
    "heißen",
    "denken",
    "nehmen",
    "tun",
    "dürfen",
    "glauben",
    "halten",
    "nennen",
    "mögen",
    "zeigen",
    "sprechen",
    "bringen",
    "leben",
    "fahren",
    "meinen",
    "fragen",
    "kennen",
    "stellen",
    "spielen",
    "arbeiten",
    "brauchen",
    "folgen",
    "lernen",
    "verstehen",
    "setzen",
    "bekommen",
    "beginnen",
    "erzählen",
    "versuchen",
    "schreiben",
    "laufen",
    "erklären",
    "sitzen",
    "ziehen",
    "scheinen",
    "fallen",
    "gehören",
    "erhalten",
    "treffen",
    "suchen",
    "legen",
    "gewinnen",
    "schließen",
    "erreichen",
    "tragen",
    "schaffen",
    "lesen",
    "verlieren",
    "erkennen",
    "entwickeln",
    "reden",
    "aussehen",
    "erscheinen",
    "anfangen",
    "erwarten",
    "wohnen",
    "warten",
    "helfen",
    "fühlen",
    "bieten",
    "interessieren",
    "erinnern",
    "anbieten",
    "studieren",
    "verbinden",
    "fehlen",
    "bedeuten",
    "vergleichen",
    "hören",
    "essen",
    "trinken",
    "schlafen",
    "kaufen",
    "verkaufen",
    "bezahlen",
    "zahlen",
    "kosten",
    "öffnen",
    "schicken",
    "antworten",
    "verlassen",
    "entscheiden",
    "hoffen",
    "danken",
    "gefallen",
    "passieren",
    "brechen",
    "tanzen",
    "singen",
    "springen",
    "waschen",
    "putzen",
    "kochen",
    "backen",
    "schneiden",
    "schmecken",
    "riechen",
    "fliegen",
    "reisen",
    "besuchen",
    "wandern",
    "schwimmen",
    "steigen",
    "sterben",
    "wachsen",
    "feiern",
    "lachen",
    "weinen",
    "lächeln",
    "grüßen",
    "wünschen",
    "träumen",
    "vergessen",
    "wiederholen",
    "üben",
    "prüfen",
    "zählen",
    "rechnen",
    "ändern",
    "wechseln",
    "bauen",
    "reparieren",
    "zerstören",
    "malen",
    "zeichnen",
    "drücken",
    "drehen",
    "werfen",
    "fangen",
    "heben",
    "packen",
    "sammeln",
    "teilen",
    "holen",
    "empfehlen",
    "bitten",
    "binden",
    "messen",
    "wiegen",
    "treiben",
    "rufen",
    "benutzen",
    "verwenden",
    "verdienen",
    "bewegen",
    "begegnen",
    "gelingen",
    "geschehen",
    "klingen",
    "regnen",
    "schneien",
    "schauen",
    "erlauben",
    "vermissen",
    "verpassen",
    "verschwinden",
    "genießen",
    "rennen",
    "senden",
    "bestehen",
    "entstehen",
    "aufstehen",
    "anrufen",
    "einkaufen",
    "einladen",
    "mitkommen",
    "ankommen",
    "abfahren",
    "abholen",
    "aufhören",
    "aufmachen",
    "zumachen",
    "anziehen",
    "ausziehen",
    "umziehen",
    "fernsehen",
    "teilnehmen",
    "stattfinden",
    "vorstellen",
    "zuhören",
    "aufräumen",
    "ausgeben",
    "ausgehen",
    "zurückkommen",
    "mitnehmen",
    "mitbringen",
    "aussteigen",
    "einsteigen",
    "umsteigen",
    "vorbereiten",
    "aufwachen",
    "einschlafen",
    "ansehen",
    "ausprobieren",
    "kennenlernen",
]

# Separable verbs: verb → (prefix, base). The base must itself be conjugatable
# (weak by rule, or present in IRREGULAR). Finite forms put the prefix last
# ("stehe auf"); Partizip II is prefix + base participle ("aufgestanden");
# Futur/Konjunktiv II keep the whole infinitive ("werde aufstehen").
SEPARABLE = {
    "aussehen": ("aus", "sehen"),
    "anfangen": ("an", "fangen"),
    "anbieten": ("an", "bieten"),
    "aufstehen": ("auf", "stehen"),
    "anrufen": ("an", "rufen"),
    "einkaufen": ("ein", "kaufen"),
    "einladen": ("ein", "laden"),
    "mitkommen": ("mit", "kommen"),
    "ankommen": ("an", "kommen"),
    "abfahren": ("ab", "fahren"),
    "abholen": ("ab", "holen"),
    "aufhören": ("auf", "hören"),
    "aufmachen": ("auf", "machen"),
    "zumachen": ("zu", "machen"),
    "anziehen": ("an", "ziehen"),
    "ausziehen": ("aus", "ziehen"),
    "umziehen": ("um", "ziehen"),
    "fernsehen": ("fern", "sehen"),
    "teilnehmen": ("teil", "nehmen"),
    "stattfinden": ("statt", "finden"),
    "vorstellen": ("vor", "stellen"),
    "zuhören": ("zu", "hören"),
    "aufräumen": ("auf", "räumen"),
    "ausgeben": ("aus", "geben"),
    "ausgehen": ("aus", "gehen"),
    "zurückkommen": ("zurück", "kommen"),
    "mitnehmen": ("mit", "nehmen"),
    "mitbringen": ("mit", "bringen"),
    "aussteigen": ("aus", "steigen"),
    "einsteigen": ("ein", "steigen"),
    "umsteigen": ("um", "steigen"),
    "vorbereiten": ("vor", "bereiten"),
    "aufwachen": ("auf", "wachen"),
    "einschlafen": ("ein", "schlafen"),
    "ansehen": ("an", "sehen"),
    "ausprobieren": ("aus", "probieren"),
    "kennenlernen": ("kennen", "lernen"),
}

# Strong and mixed verbs (including bases that only appear inside separable
# verbs, e.g. "laden"). Fields:
#   p23    — stem used for du/er in Präsens (None = no change)
#   pret   — Präteritum stem (ich/er form; a trailing "e" marks a mixed verb
#            that takes weak endings, e.g. "dachte")
#   p2     — Partizip II (full word, already ge-/prefix-resolved)
#   imp    — Imperativ du form when it differs from the bare stem (e→i/ie verbs)
IRREGULAR = {
    "geben": {"p23": "gib", "pret": "gab", "p2": "gegeben", "imp": "gib"},
    "kommen": {"pret": "kam", "p2": "gekommen"},
    "gehen": {"pret": "ging", "p2": "gegangen"},
    "sehen": {"p23": "sieh", "pret": "sah", "p2": "gesehen", "imp": "sieh"},
    "lassen": {"p23": "läss", "pret": "ließ", "p2": "gelassen"},
    "stehen": {"pret": "stand", "p2": "gestanden"},
    "finden": {"pret": "fand", "p2": "gefunden"},
    "bleiben": {"pret": "blieb", "p2": "geblieben"},
    "liegen": {"pret": "lag", "p2": "gelegen"},
    "heißen": {"pret": "hieß", "p2": "geheißen"},
    "denken": {"pret": "dachte", "p2": "gedacht"},
    "nehmen": {"p23": "nimm", "pret": "nahm", "p2": "genommen", "imp": "nimm"},
    "tun": {"pret": "tat", "p2": "getan"},
    "halten": {"p23": "hält", "pret": "hielt", "p2": "gehalten"},
    "nennen": {"pret": "nannte", "p2": "genannt"},
    "sprechen": {
        "p23": "sprich",
        "pret": "sprach",
        "p2": "gesprochen",
        "imp": "sprich",
    },
    "bringen": {"pret": "brachte", "p2": "gebracht"},
    "fahren": {"p23": "fähr", "pret": "fuhr", "p2": "gefahren"},
    "kennen": {"pret": "kannte", "p2": "gekannt"},
    "verstehen": {"pret": "verstand", "p2": "verstanden"},
    "bekommen": {"pret": "bekam", "p2": "bekommen"},
    "beginnen": {"pret": "begann", "p2": "begonnen"},
    "schreiben": {"pret": "schrieb", "p2": "geschrieben"},
    "laufen": {"p23": "läuf", "pret": "lief", "p2": "gelaufen"},
    "sitzen": {"pret": "saß", "p2": "gesessen"},
    "ziehen": {"pret": "zog", "p2": "gezogen"},
    "scheinen": {"pret": "schien", "p2": "geschienen"},
    "fallen": {"p23": "fäll", "pret": "fiel", "p2": "gefallen"},
    "erhalten": {"p23": "erhält", "pret": "erhielt", "p2": "erhalten"},
    "treffen": {"p23": "triff", "pret": "traf", "p2": "getroffen", "imp": "triff"},
    "gewinnen": {"pret": "gewann", "p2": "gewonnen"},
    "schließen": {"pret": "schloss", "p2": "geschlossen"},
    "tragen": {"p23": "träg", "pret": "trug", "p2": "getragen"},
    "lesen": {"p23": "lies", "pret": "las", "p2": "gelesen", "imp": "lies"},
    "verlieren": {"pret": "verlor", "p2": "verloren"},
    "erkennen": {"pret": "erkannte", "p2": "erkannt"},
    "erscheinen": {"pret": "erschien", "p2": "erschienen"},
    "helfen": {"p23": "hilf", "pret": "half", "p2": "geholfen", "imp": "hilf"},
    "bieten": {"pret": "bot", "p2": "geboten"},
    "verbinden": {"pret": "verband", "p2": "verbunden"},
    "vergleichen": {"pret": "verglich", "p2": "verglichen"},
    "essen": {"p23": "iss", "pret": "aß", "p2": "gegessen", "imp": "iss"},
    "trinken": {"pret": "trank", "p2": "getrunken"},
    "schlafen": {"p23": "schläf", "pret": "schlief", "p2": "geschlafen"},
    "verlassen": {"p23": "verläss", "pret": "verließ", "p2": "verlassen"},
    "entscheiden": {"pret": "entschied", "p2": "entschieden"},
    "gefallen": {"p23": "gefäll", "pret": "gefiel", "p2": "gefallen"},
    "brechen": {"p23": "brich", "pret": "brach", "p2": "gebrochen", "imp": "brich"},
    "singen": {"pret": "sang", "p2": "gesungen"},
    "springen": {"pret": "sprang", "p2": "gesprungen"},
    "waschen": {"p23": "wäsch", "pret": "wusch", "p2": "gewaschen"},
    "backen": {"pret": "backte", "p2": "gebacken"},
    "schneiden": {"pret": "schnitt", "p2": "geschnitten"},
    "riechen": {"pret": "roch", "p2": "gerochen"},
    "fliegen": {"pret": "flog", "p2": "geflogen"},
    "schwimmen": {"pret": "schwamm", "p2": "geschwommen"},
    "steigen": {"pret": "stieg", "p2": "gestiegen"},
    "sterben": {"p23": "stirb", "pret": "starb", "p2": "gestorben", "imp": "stirb"},
    "wachsen": {"p23": "wächs", "pret": "wuchs", "p2": "gewachsen"},
    "vergessen": {
        "p23": "vergiss",
        "pret": "vergaß",
        "p2": "vergessen",
        "imp": "vergiss",
    },
    "werfen": {"p23": "wirf", "pret": "warf", "p2": "geworfen", "imp": "wirf"},
    "fangen": {"p23": "fäng", "pret": "fing", "p2": "gefangen"},
    "heben": {"pret": "hob", "p2": "gehoben"},
    "empfehlen": {
        "p23": "empfiehl",
        "pret": "empfahl",
        "p2": "empfohlen",
        "imp": "empfiehl",
    },
    "bitten": {"pret": "bat", "p2": "gebeten"},
    "binden": {"pret": "band", "p2": "gebunden"},
    "messen": {"p23": "miss", "pret": "maß", "p2": "gemessen", "imp": "miss"},
    "wiegen": {"pret": "wog", "p2": "gewogen"},
    "treiben": {"pret": "trieb", "p2": "getrieben"},
    "rufen": {"pret": "rief", "p2": "gerufen"},
    "gelingen": {"pret": "gelang", "p2": "gelungen"},
    "geschehen": {"p23": "geschieh", "pret": "geschah", "p2": "geschehen"},
    "klingen": {"pret": "klang", "p2": "geklungen"},
    "verschwinden": {"pret": "verschwand", "p2": "verschwunden"},
    "genießen": {"pret": "genoss", "p2": "genossen"},
    "rennen": {"pret": "rannte", "p2": "gerannt"},
    "senden": {"pret": "sandte", "p2": "gesandt"},
    "bestehen": {"pret": "bestand", "p2": "bestanden"},
    "entstehen": {"pret": "entstand", "p2": "entstanden"},
    "laden": {"p23": "läd", "pret": "lud", "p2": "geladen"},
}

# Verbs whose Perfekt/Plusquamperfekt take "sein". Checked on the full verb
# (a separable verb can differ from its base: stehen→haben, aufstehen→sein).
SEIN_VERBS = {
    "sein",
    "werden",
    "bleiben",
    "gehen",
    "kommen",
    "fahren",
    "laufen",
    "fliegen",
    "fallen",
    "steigen",
    "sterben",
    "wachsen",
    "passieren",
    "geschehen",
    "gelingen",
    "erscheinen",
    "entstehen",
    "folgen",
    "reisen",
    "wandern",
    "schwimmen",
    "springen",
    "rennen",
    "begegnen",
    "verschwinden",
    "aufstehen",
    "einschlafen",
    "aufwachen",
    "ankommen",
    "abfahren",
    "mitkommen",
    "zurückkommen",
    "ausgehen",
    "aussteigen",
    "einsteigen",
    "umsteigen",
    "umziehen",
}

# Fully suppletive/heavily irregular verbs: explicit six-form paradigms.
# Missing tenses fall back to the engine (e.g. modal Präteritum builds fine
# from the mixed "pret" stem).
FULL_OVERRIDES = {
    "sein": {
        "praesens": ["bin", "bist", "ist", "sind", "seid", "sind"],
        "praeteritum": ["war", "warst", "war", "waren", "wart", "waren"],
        "k2": ["wäre", "wärst", "wäre", "wären", "wärt", "wären"],
        "imperativ": [None, "sei", None, None, "seid", "seien Sie"],
        "p2": "gewesen",
    },
    "haben": {
        "praesens": ["habe", "hast", "hat", "haben", "habt", "haben"],
        "praeteritum": ["hatte", "hattest", "hatte", "hatten", "hattet", "hatten"],
        "k2": ["hätte", "hättest", "hätte", "hätten", "hättet", "hätten"],
        "imperativ": [None, "hab", None, None, "habt", "haben Sie"],
        "p2": "gehabt",
    },
    "werden": {
        "praesens": ["werde", "wirst", "wird", "werden", "werdet", "werden"],
        "praeteritum": ["wurde", "wurdest", "wurde", "wurden", "wurdet", "wurden"],
        "k2": ["würde", "würdest", "würde", "würden", "würdet", "würden"],
        "imperativ": [None, "werde", None, None, "werdet", "werden Sie"],
        "p2": "geworden",
    },
    "können": {
        "praesens": ["kann", "kannst", "kann", "können", "könnt", "können"],
        "pret_stem": "konnte",
        "k2_stem": "könnte",
        "p2": "gekonnt",
        "no_imperative": True,
    },
    "müssen": {
        "praesens": ["muss", "musst", "muss", "müssen", "müsst", "müssen"],
        "pret_stem": "musste",
        "k2_stem": "müsste",
        "p2": "gemusst",
        "no_imperative": True,
    },
    "dürfen": {
        "praesens": ["darf", "darfst", "darf", "dürfen", "dürft", "dürfen"],
        "pret_stem": "durfte",
        "k2_stem": "dürfte",
        "p2": "gedurft",
        "no_imperative": True,
    },
    "sollen": {
        "praesens": ["soll", "sollst", "soll", "sollen", "sollt", "sollen"],
        "pret_stem": "sollte",
        "k2_stem": "sollte",
        "p2": "gesollt",
        "no_imperative": True,
    },
    "wollen": {
        "praesens": ["will", "willst", "will", "wollen", "wollt", "wollen"],
        "pret_stem": "wollte",
        "k2_stem": "wollte",
        "p2": "gewollt",
        "no_imperative": True,
    },
    "mögen": {
        "praesens": ["mag", "magst", "mag", "mögen", "mögt", "mögen"],
        "pret_stem": "mochte",
        "k2_stem": "möchte",
        "p2": "gemocht",
        "no_imperative": True,
    },
    "wissen": {
        "praesens": ["weiß", "weißt", "weiß", "wissen", "wisst", "wissen"],
        "pret_stem": "wusste",
        "k2_stem": "wüsste",
        "p2": "gewusst",
        "no_imperative": True,
    },
}

# Weak verbs starting with one of these never take the ge- prefix in the
# Partizip II (besuchen → besucht). "wieder" covers the inseparable
# "wiederholen"; separable wieder- verbs would need a SEPARABLE entry instead.
INSEPARABLE_PREFIXES = (
    "be",
    "ge",
    "er",
    "ver",
    "zer",
    "ent",
    "emp",
    "miss",
    "wieder",
    "über",
)

HABEN_PRAESENS = ["habe", "hast", "hat", "haben", "habt", "haben"]
SEIN_PRAESENS = ["bin", "bist", "ist", "sind", "seid", "sind"]
HABEN_PRAETERITUM = ["hatte", "hattest", "hatte", "hatten", "hattet", "hatten"]
SEIN_PRAETERITUM = ["war", "warst", "war", "waren", "wart", "waren"]
WERDEN_PRAESENS = ["werde", "wirst", "wird", "werden", "werdet", "werden"]
WUERDE = ["würde", "würdest", "würde", "würden", "würdet", "würden"]


def stem_of(infinitive: str) -> str:
    if infinitive.endswith("en"):
        return infinitive[:-2]
    if infinitive.endswith("n"):
        return infinitive[:-1]
    raise ValueError(f"not a German infinitive: {infinitive}")


def needs_e_insertion(stem: str) -> bool:
    """True for stems that need a linking -e- (arbeit-est, öffn-et, rechn-est).

    Stems in -t/-d always take it. Stems in -m/-n take it only after another
    consonant that isn't l, r, m, n or a plain (vowel-lengthening) h — but a
    'ch' before the m/n does count (rechnen, zeichnen).
    """
    if stem.endswith(("t", "d")):
        return True
    if len(stem) >= 2 and stem[-1] in "mn":
        prev = stem[-2]
        if prev in VOWELS or prev in "lrmn":
            return False
        if prev == "h":
            return len(stem) >= 3 and stem[-3] == "c"
        return True
    return False


def is_s_final(stem: str) -> bool:
    """Stems whose du form contracts -st to -t (reisen → du reist)."""
    return stem.endswith(("s", "ß", "x", "z"))


def praesens(infinitive: str) -> list[str]:
    over = FULL_OVERRIDES.get(infinitive)
    if over and "praesens" in over:
        return list(over["praesens"])
    stem = stem_of(infinitive)
    e = "e" if needs_e_insertion(stem) else ""

    # ich: -eln verbs contract (sammeln → sammle); -ern keep the e (wandere).
    # No linking -e here — the stem's own -e ending suffices (finde, regne).
    if infinitive.endswith("eln"):
        ich = stem[:-2] + "le"
    else:
        ich = stem + "e"

    p23 = IRREGULAR.get(infinitive, {}).get("p23")
    if p23:
        # A changed stem never takes the linking -e (halten → du hältst, er hält).
        du = p23 + ("t" if is_s_final(p23) else "st")
        er = p23 if p23.endswith("t") else p23 + "t"
    else:
        du = stem + e + ("t" if is_s_final(stem) and not e else "st")
        er = stem + e + "t"
    ihr = stem + e + "t"
    # wir / sie/Sie are always the infinitive (machen, wandern, sammeln).
    return [ich, du, er, infinitive, ihr, infinitive]


def _finite_past(stem: str) -> list[str]:
    """Conjugate a Präteritum (or one-word Konjunktiv II) stem.

    Stems ending in -e are weak/mixed (machte, dachte, hätte): endings
    -, -st, -, -n, -t, -n. Anything else is a strong ablaut stem (fuhr, sah):
    endings -, -st, -, -en, -t, -en, with a linking -e- after -t/-d/-s/-ß/-z
    (fandest, lasest).
    """
    if stem.endswith("e"):
        return [stem, stem + "st", stem, stem + "n", stem + "t", stem + "n"]
    link = "e" if stem.endswith(("t", "d", "s", "ß", "z")) else ""
    return [
        stem,
        stem + link + "st",
        stem,
        stem + "en",
        stem + ("et" if stem.endswith(("t", "d")) else "t"),
        stem + "en",
    ]


def praeteritum_stem(infinitive: str) -> str:
    over = FULL_OVERRIDES.get(infinitive)
    if over and "pret_stem" in over:
        return over["pret_stem"]
    irr = IRREGULAR.get(infinitive)
    if irr:
        return irr["pret"]
    stem = stem_of(infinitive)
    return stem + ("ete" if needs_e_insertion(stem) else "te")


def praeteritum(infinitive: str) -> list[str]:
    over = FULL_OVERRIDES.get(infinitive)
    if over and "praeteritum" in over:
        return list(over["praeteritum"])
    return _finite_past(praeteritum_stem(infinitive))


def partizip_2(infinitive: str) -> str:
    over = FULL_OVERRIDES.get(infinitive)
    if over and "p2" in over:
        return over["p2"]
    irr = IRREGULAR.get(infinitive)
    if irr:
        return irr["p2"]
    stem = stem_of(infinitive)
    body = stem + ("et" if needs_e_insertion(stem) else "t")
    if infinitive.endswith("ieren") or infinitive.startswith(INSEPARABLE_PREFIXES):
        return body
    return "ge" + body


def aux_of(infinitive: str) -> list[str]:
    return SEIN_PRAESENS if infinitive in SEIN_VERBS else HABEN_PRAESENS


def aux_praeteritum_of(infinitive: str) -> list[str]:
    return SEIN_PRAETERITUM if infinitive in SEIN_VERBS else HABEN_PRAETERITUM


def konjunktiv_2(infinitive: str) -> list[str]:
    over = FULL_OVERRIDES.get(infinitive)
    if over and "k2" in over:
        return list(over["k2"])
    if over and "k2_stem" in over:
        return _finite_past(over["k2_stem"])
    return [f"{w} {infinitive}" for w in WUERDE]


def imperativ(infinitive: str) -> list[str | None]:
    over = FULL_OVERRIDES.get(infinitive)
    if over:
        if over.get("no_imperative"):
            return [None] * 6
        if "imperativ" in over:
            return list(over["imperativ"])
    stem = stem_of(infinitive)
    irr = IRREGULAR.get(infinitive, {})
    if "imp" in irr:
        du = irr["imp"]
    elif infinitive.endswith(("eln", "ern")):
        # sammle!, wandere! — same contraction as the ich form.
        du = praesens(infinitive)[0]
    elif needs_e_insertion(stem):
        du = stem + "e"
    else:
        du = stem
    ihr = praesens(infinitive)[4]
    sie = f"{infinitive} Sie"
    return [None, du, None, None, ihr, sie]


def conjugate(infinitive: str) -> dict[str, list]:
    """Full tense→forms map for one verb (separable-aware)."""
    sep = SEPARABLE.get(infinitive)
    if sep:
        prefix, base = sep
        base_forms = conjugate(base)

        def split_finite(forms: list) -> list:
            return [None if f is None else f"{f} {prefix}" for f in forms]

        p2 = prefix + partizip_2(base)
        base_imp = base_forms["imperativ"]
        return {
            "indikativ/praesens": split_finite(base_forms["indikativ/praesens"]),
            "indikativ/praeteritum": split_finite(base_forms["indikativ/praeteritum"]),
            "indikativ/perfekt": [f"{a} {p2}" for a in aux_of(infinitive)],
            "indikativ/plusquamperfekt": [
                f"{a} {p2}" for a in aux_praeteritum_of(infinitive)
            ],
            "indikativ/futur-1": [f"{w} {infinitive}" for w in WERDEN_PRAESENS],
            "konjunktiv-2": [f"{w} {infinitive}" for w in WUERDE],
            "imperativ": [
                None,
                f"{base_imp[1]} {prefix}",
                None,
                None,
                f"{base_imp[4]} {prefix}",
                f"{base} Sie {prefix}",
            ],
        }

    p2 = partizip_2(infinitive)
    return {
        "indikativ/praesens": praesens(infinitive),
        "indikativ/praeteritum": praeteritum(infinitive),
        "indikativ/perfekt": [f"{a} {p2}" for a in aux_of(infinitive)],
        "indikativ/plusquamperfekt": [
            f"{a} {p2}" for a in aux_praeteritum_of(infinitive)
        ],
        "indikativ/futur-1": [f"{w} {infinitive}" for w in WERDEN_PRAESENS],
        "konjunktiv-2": konjunktiv_2(infinitive),
        "imperativ": imperativ(infinitive),
    }


# Spot checks against known-good paradigms; a wrong engine rule fails loudly
# instead of silently committing bad data.
EXPECTED = {
    ("sein", "indikativ/praesens"): ["bin", "bist", "ist", "sind", "seid", "sind"],
    ("sein", "indikativ/perfekt", 0): "bin gewesen",
    ("haben", "konjunktiv-2", 1): "hättest",
    ("werden", "indikativ/praeteritum", 2): "wurde",
    ("machen", "indikativ/praesens"): [
        "mache",
        "machst",
        "macht",
        "machen",
        "macht",
        "machen",
    ],
    ("machen", "indikativ/praeteritum", 1): "machtest",
    ("machen", "imperativ", 1): "mach",
    ("machen", "imperativ", 5): "machen Sie",
    ("arbeiten", "indikativ/praesens", 0): "arbeite",
    ("arbeiten", "indikativ/praesens", 1): "arbeitest",
    ("finden", "indikativ/praesens", 0): "finde",
    ("regnen", "indikativ/praesens", 0): "regne",
    ("arbeiten", "indikativ/praeteritum", 0): "arbeitete",
    ("arbeiten", "indikativ/perfekt", 2): "hat gearbeitet",
    ("arbeiten", "imperativ", 1): "arbeite",
    ("öffnen", "indikativ/praesens", 2): "öffnet",
    ("rechnen", "indikativ/praesens", 1): "rechnest",
    ("wohnen", "indikativ/praesens", 1): "wohnst",
    ("fahren", "indikativ/praesens", 1): "fährst",
    ("fahren", "indikativ/praesens", 2): "fährt",
    ("fahren", "indikativ/perfekt", 0): "bin gefahren",
    ("fahren", "imperativ", 1): "fahr",
    ("halten", "indikativ/praesens", 1): "hältst",
    ("halten", "indikativ/praesens", 2): "hält",
    ("geben", "indikativ/praesens", 1): "gibst",
    ("geben", "imperativ", 1): "gib",
    ("lesen", "indikativ/praesens", 1): "liest",
    ("lesen", "indikativ/praeteritum", 1): "lasest",
    ("essen", "indikativ/praesens", 1): "isst",
    ("finden", "indikativ/praeteritum", 1): "fandest",
    ("finden", "indikativ/praeteritum", 4): "fandet",
    ("sitzen", "indikativ/praesens", 1): "sitzt",
    ("heißen", "indikativ/praesens", 1): "heißt",
    ("tanzen", "indikativ/praesens", 1): "tanzt",
    ("sammeln", "indikativ/praesens", 0): "sammle",
    ("sammeln", "indikativ/praesens", 3): "sammeln",
    ("sammeln", "imperativ", 1): "sammle",
    ("wandern", "indikativ/praesens", 0): "wandere",
    ("wandern", "indikativ/perfekt", 0): "bin gewandert",
    ("studieren", "indikativ/perfekt", 0): "habe studiert",
    ("besuchen", "indikativ/perfekt", 0): "habe besucht",
    ("wiederholen", "indikativ/perfekt", 0): "habe wiederholt",
    ("können", "indikativ/praesens", 0): "kann",
    ("können", "indikativ/praeteritum", 1): "konntest",
    ("können", "konjunktiv-2", 0): "könnte",
    ("wissen", "indikativ/praesens", 2): "weiß",
    ("wissen", "konjunktiv-2", 0): "wüsste",
    ("glauben", "konjunktiv-2", 0): "würde glauben",
    ("aufstehen", "indikativ/praesens", 0): "stehe auf",
    ("aufstehen", "indikativ/praeteritum", 0): "stand auf",
    ("aufstehen", "indikativ/perfekt", 0): "bin aufgestanden",
    ("aufstehen", "indikativ/futur-1", 0): "werde aufstehen",
    ("aufstehen", "imperativ", 1): "steh auf",
    ("aufstehen", "imperativ", 5): "stehen Sie auf",
    ("einladen", "indikativ/praesens", 2): "lädt ein",
    ("einladen", "indikativ/perfekt", 2): "hat eingeladen",
    ("fernsehen", "indikativ/praesens", 1): "siehst fern",
    ("vorbereiten", "indikativ/perfekt", 0): "habe vorbereitet",
    ("kennenlernen", "indikativ/perfekt", 0): "habe kennengelernt",
    ("teilnehmen", "imperativ", 1): "nimm teil",
    ("ausprobieren", "indikativ/perfekt", 0): "habe ausprobiert",
    ("vergessen", "indikativ/praesens", 1): "vergisst",
    ("nehmen", "indikativ/praesens", 2): "nimmt",
    ("waschen", "indikativ/praesens", 1): "wäschst",
    ("umziehen", "indikativ/perfekt", 0): "bin umgezogen",
}


def run_self_checks(pool: dict[str, dict[str, list]]) -> None:
    failures = []
    for key, expected in EXPECTED.items():
        verb, tense = key[0], key[1]
        forms = pool.get(verb, {}).get(tense)
        if forms is None:
            failures.append(f"{verb} {tense}: missing")
            continue
        if len(key) == 3:
            actual = forms[key[2]]
            if actual != expected:
                failures.append(f"{verb} {tense}[{key[2]}]: {actual!r} != {expected!r}")
        elif forms != expected:
            failures.append(f"{verb} {tense}: {forms!r} != {expected!r}")
    if failures:
        print("Self-checks FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        sys.exit(1)
    print(f"Self-checks passed ({len(EXPECTED)} known forms verified).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="only generate the first N verbs")
    args = parser.parse_args()

    verbs = POPULAR_VERBS[: args.limit] if args.limit else POPULAR_VERBS
    # Sanity: no duplicates, every separable base resolvable.
    dupes = {v for v in verbs if verbs.count(v) > 1}
    if dupes:
        print(f"Duplicate verbs in POPULAR_VERBS: {sorted(dupes)}", file=sys.stderr)
        sys.exit(1)

    pool = {verb: conjugate(verb) for verb in verbs}
    if not args.limit:
        run_self_checks(pool)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(pool, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"Wrote {len(pool)} verbs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
