# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "verbecc",
# ]
# ///
"""
Generate the global Italian verb-conjugation pool used by the Conjugation quiz.

For each verb in POPULAR_VERBS (a frequency-ranked list of common Italian verbs)
this conjugates it with the `verbecc` library and writes the bare conjugated
forms for the curated set of useful tenses to languages/it/conjugations.json.

verbecc is deterministic and template-based for known verbs (the ML model is only
a fallback for verbs it has never seen), so the output is accurate. verbecc is a
GENERATION-ONLY dependency — it is intentionally NOT in pyproject.toml. The web app
reads the committed JSON and never imports verbecc.

The JSON shape is:

    {
      "parlare": {
        "indicativo/presente": ["parlo", "parli", "parla", "parliamo", "parlate", "parlano"],
        ...
      },
      ...
    }

Each tense maps to a 6-element list aligned to the canonical persons
[io, tu, lui/lei, noi, voi, loro]. A slot is null when the tense has no entry
for that person (e.g. imperativo affermativo has no "io" form — verbecc emits a
literal "-" there, which is converted to null).

Italian extraction quirks vs the Spanish generator:
- congiuntivo forms come prefixed with "che " ("che io parli") — stripped;
- the imperative's io slot is a "-" placeholder — mapped to null;
- composite tenses ("ho parlato", "sono andato") are kept as full multi-word
  strings; verbecc picks the correct avere/essere auxiliary per verb.

Usage:
    uv run tools/generate_conjugations_it.py            # generate everything
    uv run tools/generate_conjugations_it.py --limit 20 # quick test on first 20 verbs
"""

import argparse
import json
import sys
from pathlib import Path

from verbecc import CompleteConjugator

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "languages" / "it" / "conjugations.json"

# Curated tenses we generate, keyed as "<mood>/<tense>" exactly as verbecc emits
# them. Order here is irrelevant (the app's conjugation_config defines display
# order); this is just the set we extract.
TENSES = [
    "indicativo/presente",
    "indicativo/passato-prossimo",
    "indicativo/imperfetto",
    "indicativo/futuro",
    "condizionale/presente",
    "congiuntivo/presente",
    "congiuntivo/imperfetto",
    "indicativo/trapassato-prossimo",
    "indicativo/passato-remoto",
    "imperativo/affermativo",
]

# Canonical pronoun for each of the 6 person slots. verbecc emits lui and lei
# separately with identical forms, so we read "lui" for the third-singular slot;
# same idea for loro.
CANONICAL_PRONOUNS = ["io", "tu", "lui", "noi", "voi", "loro"]

# Frequency-ranked list of common Italian verbs (infinitives). Verbs not found
# in verbecc's database (or defective there) are skipped and reported at the end.
POPULAR_VERBS = [
    "essere",
    "avere",
    "fare",
    "dire",
    "potere",
    "andare",
    "vedere",
    "dare",
    "sapere",
    "volere",
    "dovere",
    "stare",
    "venire",
    "parlare",
    "trovare",
    "sentire",
    "lasciare",
    "prendere",
    "guardare",
    "mettere",
    "pensare",
    "passare",
    "credere",
    "portare",
    "arrivare",
    "capire",
    "conoscere",
    "sembrare",
    "tenere",
    "chiamare",
    "cercare",
    "entrare",
    "vivere",
    "ricordare",
    "uscire",
    "aspettare",
    "chiedere",
    "restare",
    "piacere",
    "finire",
    "tornare",
    "morire",
    "amare",
    "cominciare",
    "aprire",
    "chiudere",
    "giocare",
    "leggere",
    "scrivere",
    "mangiare",
    "bere",
    "dormire",
    "correre",
    "camminare",
    "comprare",
    "vendere",
    "pagare",
    "costare",
    "lavorare",
    "studiare",
    "imparare",
    "insegnare",
    "ascoltare",
    "rispondere",
    "domandare",
    "raccontare",
    "spiegare",
    "mostrare",
    "aiutare",
    "servire",
    "usare",
    "provare",
    "sperare",
    "decidere",
    "perdere",
    "vincere",
    "seguire",
    "salire",
    "scendere",
    "cadere",
    "crescere",
    "nascere",
    "diventare",
    "cambiare",
    "succedere",
    "significare",
    "incontrare",
    "invitare",
    "visitare",
    "viaggiare",
    "partire",
    "rimanere",
    "muovere",
    "fermare",
    "continuare",
    "smettere",
    "iniziare",
    "terminare",
    "ripetere",
    "dimenticare",
    "riuscire",
    "guidare",
    "volare",
    "nuotare",
    "ballare",
    "cantare",
    "suonare",
    "ridere",
    "piangere",
    "sorridere",
    "sognare",
    "svegliare",
    "alzare",
    "lavare",
    "pulire",
    "cucinare",
    "tagliare",
    "rompere",
    "costruire",
    "riparare",
    "disegnare",
    "contare",
    "pesare",
    "aggiungere",
    "togliere",
    "telefonare",
    "salutare",
    "ringraziare",
    "scusare",
    "regalare",
    "ricevere",
    "mandare",
    "inviare",
    "spedire",
    "offrire",
    "accettare",
    "rifiutare",
    "preferire",
    "scegliere",
    "desiderare",
    "odiare",
    "temere",
    "preoccupare",
    "festeggiare",
    "organizzare",
    "preparare",
    "ordinare",
    "prenotare",
    "affittare",
    "abitare",
    "vestire",
    "indossare",
    "spendere",
    "guadagnare",
    "risparmiare",
    "aumentare",
    "diminuire",
    "accendere",
    "spegnere",
    "spingere",
    "appartenere",
    "dipendere",
    "sviluppare",
    "creare",
    "produrre",
    "tradurre",
    "bastare",
    "mancare",
    "raggiungere",
    "superare",
    "salvare",
    "colpire",
    "buttare",
    "lanciare",
    "toccare",
    "osservare",
    "notare",
    "scoprire",
    "coprire",
    "nascondere",
    "dimostrare",
    "permettere",
    "promettere",
    "ammettere",
    "esistere",
    "apparire",
    "sparire",
    "ottenere",
    "mantenere",
    "sostenere",
    "contenere",
    "attendere",
    "intendere",
    "comprendere",
    "rendere",
    "difendere",
    "dividere",
    "condividere",
    "unire",
    "discutere",
    "esprimere",
    "descrivere",
    "indicare",
    "presentare",
    "rappresentare",
    "considerare",
    "immaginare",
    "giudicare",
    "valutare",
    "confrontare",
    "verificare",
    "controllare",
    "causare",
    "evitare",
    "impedire",
    "proteggere",
    "combattere",
    "vietare",
    "proibire",
    "obbligare",
    "costringere",
    "convincere",
    "consigliare",
    "suggerire",
    "proporre",
    "avvertire",
    "avvisare",
    "informare",
    "comunicare",
    "dichiarare",
    "annunciare",
    "affermare",
    "negare",
    "confermare",
    "dubitare",
    "giurare",
    "mentire",
    "tradire",
    "meritare",
    "punire",
    "correggere",
    "migliorare",
    "peggiorare",
    "girare",
    "attraversare",
    "fuggire",
    "scappare",
    "saltare",
    "stringere",
    "tirare",
    "spostare",
    "piovere",
    "nevicare",
]


# Verbs whose composite tenses take essere. verbecc's Italian data gets most of
# these right on its own (andare, venire, morire, …) but wrongly builds a few
# with avere ("ho piaciuto", "ho riuscito"), so the composite tenses of every
# verb listed here are rebuilt from the participle with the essere auxiliary.
# Dual-auxiliary verbs (correre, volare, cambiare, cominciare, finire, piovere…)
# are intentionally NOT listed — their avere citation form is kept.
ESSERE_VERBS = {
    "essere",
    "stare",
    "andare",
    "venire",
    "arrivare",
    "partire",
    "tornare",
    "restare",
    "rimanere",
    "entrare",
    "uscire",
    "cadere",
    "nascere",
    "morire",
    "diventare",
    "crescere",
    "succedere",
    "sparire",
    "apparire",
    "riuscire",
    "piacere",
    "bastare",
    "costare",
    "sembrare",
    "esistere",
    "scappare",
    "fuggire",
    "salire",
    "scendere",
}

ESSERE_PRESENTE = ["sono", "sei", "è", "siamo", "siete", "sono"]
ESSERE_IMPERFETTO = ["ero", "eri", "era", "eravamo", "eravate", "erano"]

# Composite tenses rebuilt for ESSERE_VERBS: tense key -> auxiliary paradigm.
COMPOSITE_TENSES = {
    "indicativo/passato-prossimo": ESSERE_PRESENTE,
    "indicativo/trapassato-prossimo": ESSERE_IMPERFETTO,
}


def force_essere_aux(tense_map: dict[str, list]) -> None:
    """Rebuild an essere-verb's composite tenses from its participle, in place.

    The masculine-singular participle is taken from the last word of whatever
    verbecc produced ("ho piaciuto" → "piaciuto"); plural slots pluralize the
    final -o to -i (sono piaciuto / siamo piaciuti).
    """
    for tense_key, aux in COMPOSITE_TENSES.items():
        forms = tense_map.get(tense_key)
        if not forms or forms[0] is None:
            continue
        participle = forms[0].split()[-1]
        plural = participle[:-1] + "i" if participle.endswith("o") else participle
        tense_map[tense_key] = [
            f"{aux[i]} {participle if i < 3 else plural}" for i in range(6)
        ]


def is_corrupted(tense_map: dict[str, list]) -> bool:
    """Detect verbecc's defective-verb corruption.

    In the Italian present indicative the io and tu forms are always distinct
    (parlo/parli, credo/credi, capisco/capisci); a defective verb collapses
    them to the same truncated stem or leaves them missing.
    """
    pres = tense_map.get("indicativo/presente")
    if not pres:
        return True
    if pres[0] is None or pres[1] is None:
        return True
    return pres[0] == pres[1]


def clean_form(pronoun: str, form: str) -> str | None:
    """Strip verbecc's pronoun scaffolding from one conjugated form.

    Handles the congiuntivo's "che " lead-in ("che io parli" → "parli"), the
    plain pronoun prefix ("io parlo" → "parlo"), the imperative's "-"
    placeholder (→ None), and slash-joined alternatives ("faccio/fo" →
    "faccio"). Bare forms (imperatives like "parla") pass through.
    """
    if form == "-":
        return None
    if form.startswith("che "):
        form = form[len("che ") :]
    prefix = pronoun + " "
    if form.startswith(prefix):
        form = form[len(prefix) :]
    return form.split("/")[0]


def pick_variant(variants: list[str]) -> str | None:
    """Pick one form when verbecc emits several entries for a pronoun.

    essere-auxiliary composite tenses come as one entry per gender, feminine
    first ("sono andata", "sono andato"); the pool stores the masculine
    citation form — the variant whose participle ends in -o (singular) or
    -i (plural).
    """
    if not variants:
        return None
    if len(variants) > 1:
        for suffix in ("o", "i"):
            for v in variants:
                if v.split()[-1].endswith(suffix):
                    return v
    return variants[0]


def extract_forms(conj_json: dict, tense_key: str) -> list[str | None]:
    """Return the 6 bare conjugated forms for a tense, aligned to CANONICAL_PRONOUNS."""
    mood, tense = tense_key.split("/", 1)
    entries = conj_json.get("moods", {}).get(mood, {}).get(tense)
    if not entries:
        return [None] * len(CANONICAL_PRONOUNS)

    by_pronoun: dict[str, list[str]] = {}
    for entry in entries:
        pr = entry.get("pr")
        forms = entry.get("c") or []
        if not pr or not forms:
            continue
        cleaned = clean_form(pr, forms[0])
        if cleaned is not None:
            by_pronoun.setdefault(pr, []).append(cleaned)

    return [pick_variant(by_pronoun.get(pr, [])) for pr in CANONICAL_PRONOUNS]


# Spot checks against known-good paradigms; a wrong extraction rule or a
# verbecc regression fails loudly instead of silently committing bad data.
EXPECTED = {
    ("essere", "indicativo/presente"): ["sono", "sei", "è", "siamo", "siete", "sono"],
    ("avere", "indicativo/presente"): ["ho", "hai", "ha", "abbiamo", "avete", "hanno"],
    ("fare", "indicativo/presente", 0): "faccio",
    ("dire", "indicativo/presente", 1): "dici",
    ("uscire", "indicativo/presente", 0): "esco",
    ("bere", "indicativo/presente", 0): "bevo",
    ("tradurre", "indicativo/presente", 0): "traduco",
    ("capire", "indicativo/presente", 0): "capisco",
    ("finire", "indicativo/presente", 1): "finisci",
    ("parlare", "indicativo/passato-prossimo", 0): "ho parlato",
    ("parlare", "indicativo/passato-prossimo", 3): "abbiamo parlato",
    ("andare", "indicativo/passato-prossimo"): [
        "sono andato",
        "sei andato",
        "è andato",
        "siamo andati",
        "siete andati",
        "sono andati",
    ],
    ("venire", "indicativo/passato-prossimo", 0): "sono venuto",
    ("piacere", "indicativo/passato-prossimo", 2): "è piaciuto",
    ("riuscire", "indicativo/passato-prossimo", 0): "sono riuscito",
    ("nascere", "indicativo/passato-prossimo", 0): "sono nato",
    ("essere", "indicativo/trapassato-prossimo", 0): "ero stato",
    ("parlare", "indicativo/imperfetto", 0): "parlavo",
    ("parlare", "indicativo/futuro", 0): "parlerò",
    ("parlare", "condizionale/presente", 0): "parlerei",
    ("essere", "congiuntivo/presente", 0): "sia",
    ("parlare", "congiuntivo/imperfetto", 0): "parlassi",
    ("parlare", "indicativo/trapassato-prossimo", 0): "avevo parlato",
    ("essere", "indicativo/passato-remoto", 0): "fui",
    ("parlare", "imperativo/affermativo", 0): None,
    ("parlare", "imperativo/affermativo", 1): "parla",
    ("parlare", "imperativo/affermativo", 2): "parli",
    ("parlare", "imperativo/affermativo", 4): "parlate",
    ("essere", "imperativo/affermativo", 1): "sii",
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="only process the first N verbs"
    )
    args = parser.parse_args()

    conjugator = CompleteConjugator("it")

    verbs = POPULAR_VERBS
    if args.limit is not None:
        verbs = verbs[: args.limit]

    def conjugate_verb(verb: str) -> dict[str, list]:
        conj = json.loads(conjugator.conjugate(verb).to_json())
        tense_map: dict[str, list] = {}
        for tense_key in TENSES:
            forms = extract_forms(conj, tense_key)
            if any(f is not None for f in forms):
                tense_map[tense_key] = forms
        return tense_map

    result: dict[str, dict[str, list]] = {}
    missing: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()

    for verb in verbs:
        if verb in seen:
            continue
        seen.add(verb)
        try:
            tense_map = conjugate_verb(verb)
        except Exception as exc:  # noqa: BLE001 — verbecc raises VerbNotFoundError etc.
            missing.append(f"{verb} ({type(exc).__name__})")
            continue
        if is_corrupted(tense_map):
            dropped.append(verb)
            continue
        if verb in ESSERE_VERBS:
            force_essere_aux(tense_map)
        if tense_map:
            result[verb] = tense_map

    if args.limit is None:
        run_self_checks(result)

    # Preserve POPULAR_VERBS (frequency) order so the app can rank autocomplete
    # suggestions by commonness (e.g. "pa" -> "parlare" before rarer pa* verbs).
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=0, sort_keys=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(result)} verbs to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"File size: {size_kb:.0f} KiB")
    if missing:
        print(f"\nSkipped {len(missing)} verb(s) not found in verbecc:")
        for m in missing:
            print(f"  - {m}")
    if dropped:
        print(f"\nDropped {len(dropped)} defective verb(s) (verbecc returns a")
        print("broken/missing present paradigm, so excluded):")
        for v in dropped:
            print(f"  - {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
