"""Derive the rule-governed traditional Welsh numbers.

    uv run languages/cy/generate_numbers_traditional.py

Writes languages/cy/numbers_traditional_generated.py. **It never writes
numbers_traditional.py** — that file holds what speakers told us, and a script
must not be able to clobber it.

What this produces is marked `attested` while the rules it applies are the
documented ones (see THE CONNECTIVE below) and `reconstructed` otherwise.
Attested forms are served; reconstructed ones are withheld from learners until
a speaker confirms them (config.SERVE_RECONSTRUCTED). Either way,
tools/export_unconfirmed_forms.py turns them into a review table, because
"documented" is still not "a speaker checked this exact form".

THE RULES
---------
41-99 is not 54 independent facts, it is one rule:

    [unit 1-19] + connective + [score: deugain 40 | trigain 60 | pedwar ugain 80]

21-39 is a different rule and is kept separate:

    [unit 1-19] + "ar hugain"

Nothing outside those two ranges is generated here. 40, 60, 80, 100 are scores
in their own right and come from speakers; 50 has an idiomatic form
(`hanner cant`) that no rule predicts, so the rule's regular form is added
beside it rather than instead of it.

THE CONNECTIVE — ANSWERED
-------------------------
`TENS_CONNECTIVE` decides all 54 forms of 41-99 at once. It is `a`, with the
aspirate mutation, and the evidence that looked split never was:

* confirmed: 70 = "deg a thrigain" (t->th), 90 = "deg a phedwar ugain" (p->ph)
* the review round: Wiktionary's usage note at *deugain* states the rule for
  41-59 directly, carries "tri a deugain" as a headword with a 19th-century
  citation (*tair milldir a deugain*), and a second source gives the same
  structure for 44. Cornish splits it identically — `warn ugens` for 21-39 but
  `ha dew-ugens` for 41 — which is independent evidence the split is old.

The apparent counter-example, 45 = "pump ar ddeugain", dissolved: the aspirate
mutation only touches p, t and c, so `deugain` cannot show it. "deg a deugain"
(50) and "tri a deugain" (43) are the same rule as 70 and 90; the missing
mutation is a gap in the aspirate inventory, not a different connective.
"pump ar ddeugain" is a real but minority pattern, most likely analogy from the
heavily-used `ar hugain` run of 21-39 — recorded as such in
numbers_traditional.py rather than deleted or served.

The connective and the mutation it triggers are one choice, not two: `a` takes
the aspirate mutation (t->th, p->ph, c->ch; d is unaffected), `ar` takes the
soft one (d->dd, t->d, p->b). Flipping one without the other produces forms that
are wrong in a way that looks right. Flipping `TENS_CONNECTIVE` away from the
documented value also demotes every 41-99 form from `attested` back to
`reconstructed` — the documentation is what makes them servable, so a rule the
documentation doesn't back must go back behind the flag.

A TRAP, RECORDED SO NOBODY "FIXES" IT
-------------------------------------
Several public number lists give 34 as "pedwar deg ar hugain". That is 40 + 20
and computes to 60. This generator produces "pedwar ar ddeg ar hugain"
(14 + 20), which is the correct traditional form. Two sources sharing a
distinctive arithmetic error are one source with a copy — which is also why a
form is not "corroborated" here just because it appears in two places online.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from languages.cy.numbers_traditional import SPEAKER_FORMS  # noqa: E402
from languages.provenance import SPEAKER_SOURCES  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "numbers_traditional_generated.py"

# ===== The switch =====

TENS_CONNECTIVE = "a"

# The value the sources back. Kept separate from the switch so flipping the
# switch is still possible (to test a hypothesis, or if a later round overturns
# this one) without silently promoting undocumented forms to servable.
DOCUMENTED_CONNECTIVE = "a"

# What the two rules produce, provenance-wise.
#
# 21-39 (`ar hugain`) is documented independently of the connective question:
# speakers gave us 21 and 30, and Cornish `warn ugens` covers the same span, so
# it is attested whatever TENS_CONNECTIVE says.
TWENTIES_SOURCE = "attested"

# The feminine series. Stated directly by the review round: 2, 3 and 4 change
# with the noun's gender, and so does every compound built on them.
GENDER_SERIES_SOURCE = "attested"

# ===== Mutation =====

# After `a`. Only the first consonant changes; d is untouched, which is why
# "a deugain" looks unmutated next to "a thrigain".
ASPIRATE = {"t": "th", "p": "ph", "c": "ch"}

# After `ar`.
SOFT = {"p": "b", "t": "d", "c": "g", "b": "f", "d": "dd", "g": "", "m": "f"}


def aspirate(word):
    first = word[0]
    return ASPIRATE.get(first, first) + word[1:] if first in ASPIRATE else word


def soft(word):
    first = word[0]
    return SOFT[first] + word[1:] if first in SOFT else word


CONNECTIVES = {
    "a": {"word": "a", "mutate": aspirate},
    "ar": {"word": "ar", "mutate": soft},
}


def connective_for(unit):
    """The connective used between a unit and a score.

    Takes the unit so a per-unit rule can be tested without restructuring
    anything — the review round ruled that out (the mutation gap explains the
    one form that looked different), but the shape costs nothing to keep.
    """
    return CONNECTIVES[TENS_CONNECTIVE]


def score_compound_source():
    """Provenance for a 41-99 form built with the connective in force.

    Documented value -> `attested`, which is served. Anything else ->
    `reconstructed`, which is not: the sources back one connective, and a form
    built with a different one has nothing behind it but this script.
    """
    return "attested" if TENS_CONNECTIVE == DOCUMENTED_CONNECTIVE else "reconstructed"


# ===== The pieces =====

# Traditional units 1-19, masculine. The gendered ones are handled below.
UNITS = {
    1: "un",
    2: "dau",
    3: "tri",
    4: "pedwar",
    5: "pump",
    6: "chwech",
    7: "saith",
    8: "wyth",
    9: "naw",
    10: "deg",
    11: "un ar ddeg",
    12: "deuddeg",
    13: "tri ar ddeg",
    14: "pedwar ar ddeg",
    15: "pymtheg",
    16: "un ar bymtheg",
    17: "dau ar bymtheg",
    18: "deunaw",
    19: "pedwar ar bymtheg",
}

# Only the *unit* takes a feminine form. The score never does: 84 is
# "pedair a phedwar ugain", with `pedwar ugain` left alone.
FEMININE_UNITS = {"dau": "dwy", "tri": "tair", "pedwar": "pedair"}

SCORES = {40: "deugain", 60: "trigain", 80: "pedwar ugain"}

# Numbers that keep an idiomatic speaker form *and* take the regular one as a
# documented alternative, rather than the two counting as a disagreement.
REGULAR_VARIANT_OK = {50}


def feminine(unit_text):
    """The feminine of a unit, or None when it has none.

    Only the leading word can be gendered — "tri ar ddeg" -> "tair ar ddeg",
    while "deuddeg" and "deunaw" are fused and invariable.
    """
    head, _, tail = unit_text.partition(" ")
    if head not in FEMININE_UNITS:
        return None
    return " ".join(filter(None, [FEMININE_UNITS[head], tail]))


def score_for(number):
    """The score a number in 41-99 is built on, or None."""
    for low, score in ((41, 40), (61, 60), (81, 80)):
        if low <= number <= low + 18:
            return score
    return None


def build_twenties(number, unit_text):
    """21-39: [unit] ar hugain. `ugain` takes h-prothesis after `ar`."""
    return f"{unit_text} ar hugain"


def build_score_compound(number, unit_text, unit_value):
    """41-99: [unit] + connective + [mutated score]."""
    score = score_for(number)
    connective = connective_for(unit_value)
    return f"{unit_text} {connective['word']} {connective['mutate'](SCORES[score])}"


def generate():
    """Every rule-derived form, as {number: [entry, ...]}."""
    forms = {}

    for number in list(range(22, 40)) + list(range(41, 100)):
        if number in SCORES:
            continue
        unit_value = number - 20 if number < 40 else number - score_for(number)
        unit_text = UNITS[unit_value]
        build = build_twenties if number < 40 else build_score_compound
        source = TWENTIES_SOURCE if number < 40 else score_compound_source()

        masculine = (
            build(number, unit_text)
            if number < 40
            else build(number, unit_text, unit_value)
        )
        entries = [{"text": masculine, "gender": "m", "source": source}]

        feminine_unit = feminine(unit_text)
        if feminine_unit:
            feminine_form = (
                build(number, feminine_unit)
                if number < 40
                else build(number, feminine_unit, unit_value)
            )
            entries.append({"text": feminine_form, "gender": "f", "source": source})
        forms[number] = entries

    # The feminine series for the units themselves, which speakers gave us only
    # in the masculine. The review round states the gendered pairs explicitly
    # (tri/tair ar ddeg, pedwar/pedair ar ddeg, and so on through every compound
    # built on 2, 3 or 4), so these are attested rather than guessed.
    for number, entries in SPEAKER_FORMS.items():
        if number > 21:
            continue
        for entry in entries:
            if entry.get("gender") != "m":
                continue
            feminine_form = feminine(entry["text"])
            if feminine_form:
                forms.setdefault(number, []).append(
                    {
                        "text": feminine_form,
                        "gender": "f",
                        "source": GENDER_SERIES_SOURCE,
                    }
                )

    return dict(sorted(forms.items()))


# ===== Checks =====

# The generator has to reproduce what speakers confirmed. If it does not, the
# rule is wrong, not the expectation.
CONFIRMED_CHECKS = {
    21: "un ar hugain",
    70: "deg a thrigain",
    90: "deg a phedwar ugain",
}

# Not speaker-confirmed: these pin the shape of the rule itself, so a refactor
# that quietly changes how the 50s are built fails here. 43 and 44 are named
# verbatim by the sources behind the `attested` tier (a dictionary headword with
# a 19th-century citation, and a second modern list), which makes them the two
# strongest external checks on the whole 41-99 block.
SHAPE_CHECKS = {
    30: "deg ar hugain",
    41: "un a deugain",
    43: "tri a deugain",
    44: "pedwar a deugain",
    50: "deg a deugain",
    51: "un ar ddeg a deugain",
    99: "pedwar ar bymtheg a phedwar ugain",
}


def check():
    """Fail loudly on a rule that contradicts a confirmed form."""
    failures = []
    for number, expected in CONFIRMED_CHECKS.items():
        actual = _rule_form(number)
        if actual != expected:
            failures.append(
                f"  {number}: rule gives {actual!r}, speakers confirmed {expected!r}"
            )
    if failures:
        raise SystemExit(
            "The rule contradicts confirmed forms:\n"
            + "\n".join(failures)
            + f"\n\nTENS_CONNECTIVE is {TENS_CONNECTIVE!r}. Either the connective "
            "is wrong, or the confirmations are — do not 'fix' this by editing "
            "the expectations."
        )

    for number, expected in SHAPE_CHECKS.items():
        actual = _rule_form(number)
        if actual != expected:
            raise SystemExit(
                f"Shape check failed: {number} gives {actual!r}, expected {expected!r}"
            )


def _rule_form(number):
    """Apply the rules to one number, ignoring what is already stored."""
    if 22 <= number <= 39:
        return build_twenties(number, UNITS[number - 20])
    if number == 21:
        return build_twenties(number, UNITS[1])
    score = score_for(number)
    if score is None:
        return None
    unit_value = number - score
    return build_score_compound(number, UNITS[unit_value], unit_value)


def report_disagreements(forms):
    """Name every number where the rule and a speaker differ.

    Never resolved automatically: the speaker's form is what gets served, and
    the disagreement is a question for the next review round.
    """
    disagreements = []
    for number, entries in SPEAKER_FORMS.items():
        speaker = next(
            (e for e in entries if e.get("gender", "both") in ("m", "both")), None
        )
        # Only a person's word can disagree with the rule. An `attested` entry
        # in the hand file came from the same documentation the rule did, so
        # comparing the two would report a tautology.
        if speaker is None or speaker["source"] not in SPEAKER_SOURCES:
            continue
        rule = _rule_form(number)
        if rule is None or rule == speaker["text"]:
            continue
        marker = "variant" if number in REGULAR_VARIANT_OK else "DISAGREES"
        disagreements.append(
            f"  {number}: speaker {speaker['text']!r} ({speaker['source']}) "
            f"vs rule {rule!r}  [{marker}]"
        )
    return disagreements


HEADER = '''"""Rule-derived traditional Welsh numbers — DO NOT EDIT.

Written by languages/cy/generate_numbers_traditional.py. Every form here comes
from a rule, not from a speaker checking that form.

`attested` forms are served: the rule behind them is documented (Wiktionary's
usage note at *deugain*, a 19th-century citation, the Cornish parallel) and a
reviewer cited it. `reconstructed` forms are withheld while
config.SERVE_RECONSTRUCTED is False. Both are exported for review by
tools/export_unconfirmed_forms.py — documented is not the same as confirmed.

To correct one, add the speaker's form to numbers_traditional.py — that file
wins, and this one is regenerated around it.

TENS_CONNECTIVE at the time of writing: {connective!r} (documented: {documented!r})
"""

GENERATED = {{
'''


def write(forms):
    lines = [
        HEADER.format(connective=TENS_CONNECTIVE, documented=DOCUMENTED_CONNECTIVE)
    ]
    for number, entries in forms.items():
        lines.append(f"    {number}: [\n")
        for entry in entries:
            parts = [f'"text": "{entry["text"]}"']
            if "gender" in entry:
                parts.append(f'"gender": "{entry["gender"]}"')
            parts.append(f'"source": "{entry["source"]}"')
            lines.append("        {" + ", ".join(parts) + "},\n")
        lines.append("    ],\n")
    lines.append("}\n")
    OUTPUT_PATH.write_text("".join(lines), encoding="utf-8")


def main():
    forms = generate()
    check()
    write(forms)

    total = sum(len(entries) for entries in forms.values())
    by_source = {}
    for entries in forms.values():
        for entry in entries:
            by_source[entry["source"]] = by_source.get(entry["source"], 0) + 1
    print(
        f"TENS_CONNECTIVE = {TENS_CONNECTIVE!r} (documented: {DOCUMENTED_CONNECTIVE!r})"
    )
    print(f"wrote {total} rule-derived forms for {len(forms)} numbers")
    for source in sorted(by_source):
        served = "served" if source == "attested" else "withheld"
        print(f"  {by_source[source]:>3} {source} ({served})")
    print(f"  -> {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print("\nconfirmed forms reproduced: " + ", ".join(map(str, CONFIRMED_CHECKS)))

    disagreements = report_disagreements(forms)
    if disagreements:
        print("\nrule vs speaker:")
        print("\n".join(disagreements))
        print(
            "\nThe speaker's form is served in every case. A [DISAGREES] line is "
            "a question for the next review round, not a bug to fix here."
        )
    if score_compound_source() == "attested":
        print(
            "\nThe attested forms ARE taught. Only `reconstructed` ones wait for "
            "config.SERVE_RECONSTRUCTED."
        )
    else:
        print(
            f"\nTENS_CONNECTIVE is not the documented {DOCUMENTED_CONNECTIVE!r}, so "
            "every 41-99 form is reconstructed and none of them reaches a learner."
        )


if __name__ == "__main__":
    main()
