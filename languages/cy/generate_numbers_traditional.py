"""Derive the rule-governed traditional Welsh numbers.

    uv run languages/cy/generate_numbers_traditional.py

Writes languages/cy/numbers_traditional_generated.py. **It never writes
numbers_traditional.py** — that file holds what speakers told us, and a script
must not be able to clobber it.

Everything this produces is marked `reconstructed`, which means it is withheld
from learners until a speaker confirms it (config.SERVE_RECONSTRUCTED). The
point of generating it at all is to have something concrete to *ask* about:
tools/export_unconfirmed_forms.py turns it into a review table.

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

THE UNRESOLVED CONNECTIVE
-------------------------
`TENS_CONNECTIVE` decides all 54 forms of 41-99 at once, and the evidence is
split:

* confirmed: 70 = "deg a thrigain", 90 = "deg a phedwar ugain"  -> "a"
* single:    45 = "pump ar ddeugain"                            -> "ar"

The 45 datapoint may be analogy from the 20s, which genuinely do use `ar`
("un ar hugain"). Or the two may not conflict at all: the connective could vary
by unit, which is why `connective_for()` takes the unit and not just the
constant. Do not resolve this by picking one and deleting the other — it is
question 1 in docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md.

The connective and the mutation it triggers are one choice, not two: `a` takes
the aspirate mutation (t->th, p->ph, c->ch; d is unaffected), `ar` takes the
soft one (d->dd, t->d, p->b). Flipping one without the other produces forms that
are wrong in a way that looks right.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from languages.cy.numbers_traditional import SPEAKER_FORMS  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent / "numbers_traditional_generated.py"

# ===== The switch =====

TENS_CONNECTIVE = "a"

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

    Takes the unit so a future per-unit rule (see the module docstring) can be
    tested without restructuring anything. Today it ignores it.
    """
    return CONNECTIVES[TENS_CONNECTIVE]


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

        masculine = (
            build(number, unit_text)
            if number < 40
            else build(number, unit_text, unit_value)
        )
        entries = [{"text": masculine, "gender": "m", "source": "reconstructed"}]

        feminine_unit = feminine(unit_text)
        if feminine_unit:
            feminine_form = (
                build(number, feminine_unit)
                if number < 40
                else build(number, feminine_unit, unit_value)
            )
            entries.append(
                {"text": feminine_form, "gender": "f", "source": "reconstructed"}
            )
        forms[number] = entries

    # The feminine series for the units themselves, which speakers gave us only
    # in the masculine.
    for number, entries in SPEAKER_FORMS.items():
        if number > 21:
            continue
        for entry in entries:
            if entry.get("gender") != "m":
                continue
            feminine_form = feminine(entry["text"])
            if feminine_form:
                forms.setdefault(number, []).append(
                    {"text": feminine_form, "gender": "f", "source": "reconstructed"}
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
# that quietly changes how the 50s are built fails here.
SHAPE_CHECKS = {
    30: "deg ar hugain",
    41: "un a deugain",
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
        if speaker is None or speaker["source"] == "reconstructed":
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

Written by languages/cy/generate_numbers_traditional.py. Every form here is
`reconstructed`: produced by a rule, confirmed by nobody. They are withheld from
learners while config.SERVE_RECONSTRUCTED is False, and exist so they can be
exported for review (tools/export_unconfirmed_forms.py).

To correct one, add the speaker's form to numbers_traditional.py — that file
wins, and this one is regenerated around it.

TENS_CONNECTIVE at the time of writing: {connective!r}
"""

GENERATED = {{
'''


def write(forms):
    lines = [HEADER.format(connective=TENS_CONNECTIVE)]
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
    print(f"TENS_CONNECTIVE = {TENS_CONNECTIVE!r}")
    print(f"wrote {total} reconstructed forms for {len(forms)} numbers")
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
    print("\nNothing here reaches a learner: config.SERVE_RECONSTRUCTED is the switch.")


if __name__ == "__main__":
    main()
