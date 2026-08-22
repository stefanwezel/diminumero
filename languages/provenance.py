"""Provenance for number forms: who says this is a word?

A deck of number words is a set of claims about a language. Most of this repo's
decks are generated from rules and then read by a native speaker; the Welsh
traditional deck is being assembled the other way round, one confirmed form at a
time, from a public review thread. That makes the difference between "a speaker
told us this" and "a rule produced this" the single most important fact about a
form — more important than the spelling itself, because a plausible wrong form
teaches with the same confidence as a right one.

So every form in a provenance-tracked deck carries a `source`:

    confirmed      two or more speakers agreed, or one corrected another
    single         one speaker, uncorroborated
    attested       a rule produced it, and that rule is documented in a
                   published reference which a reviewer cited. No speaker
                   checked this individual form — the *rule behind it* is what
                   has a source.
    reconstructed  derived from a grammatical rule, by a script or an LLM,
                   with nothing published behind the rule. NOT verified by any
                   speaker.

`attested` is the tier the August 2026 review round created. A respondent
answered the 41-99 connective question with Wiktionary's usage note at
*deugain* (41-59 take `a`), a 19th-century citation for `tri a deugain`, a
second modern source for `pedwar a deugain`, and the Cornish split
(`warn ugens` 21-39 vs `ha dew-ugens` 41) as comparative evidence. That is a
different kind of claim from "a script applied a rule nobody has checked", and
collapsing the two would either withhold documented forms forever or serve
undocumented ones — so it gets its own tier, and it is served.

`reconstructed` forms are committed but **not served** unless
``config.SERVE_RECONSTRUCTED`` is turned on. They exist so they can be exported
for confirm-or-correct review and switched on in one line once they come back.

The deck a drill sees is derived here (`build_numbers`), so the plain
``dict[int, str]`` contract every other language uses is preserved and no caller
outside this module has to know provenance exists.
"""

from config import SERVE_RECONSTRUCTED

# Ordered weakest-claim-last, which is also the order tooling reports them in.
SOURCES = ("confirmed", "single", "attested", "reconstructed")

# A person who speaks the language said this form, in as many words.
SPEAKER_SOURCES = ("confirmed", "single")

# Sources a learner may be shown regardless of the flag. `attested` is here and
# `reconstructed` is not: the line is whether anything outside this repo backs
# the form, not whether a script happened to type it.
SERVED_SOURCES = SPEAKER_SOURCES + ("attested",)

# Gender values a form may declare. "both" (the default) means invariable.
GENDERS = ("m", "f", "both")

# The gender a bare-digit drill shows. A number with no noun beside it has
# nothing to agree with, so it gets the masculine citation form — the feminine
# series is carried in the data for the Learn page and for any future mode that
# attaches a noun.
DRILL_GENDER = "m"


def served_sources(serve_reconstructed=None):
    """Which source tiers may reach a learner right now."""
    if serve_reconstructed is None:
        serve_reconstructed = SERVE_RECONSTRUCTED
    if serve_reconstructed:
        return set(SOURCES)
    return set(SERVED_SOURCES)


def build_numbers(forms, serve_reconstructed=None, gender=DRILL_GENDER):
    """Derive a plain ``{number: word}`` deck from provenance-tracked forms.

    Takes the first form of each number that is both servable and usable for the
    requested gender. A number whose only forms are withheld is **absent** from
    the result — the loader drops it, the drill never picks it, and nothing
    downstream needs to know why.
    """
    allowed = served_sources(serve_reconstructed)
    numbers = {}
    for number, entries in forms.items():
        for entry in entries:
            if entry.get("source") not in allowed:
                continue
            if entry.get("gender", "both") not in (gender, "both"):
                continue
            if not entry.get("text"):
                continue
            numbers[number] = entry["text"]
            break
    return numbers


def merge_forms(speaker_forms, generated_forms):
    """Combine hand-edited forms with rule-derived ones.

    Speaker forms always come first, so they are what gets served and what gets
    taught. A generated form that duplicates one is dropped; a generated form
    that *contradicts* one is kept as an alternative — withheld from the drill
    like every reconstructed form, but visible to the review export, which is
    where a disagreement between a rule and a speaker belongs.
    """
    merged = {number: list(entries) for number, entries in speaker_forms.items()}
    for number, entries in generated_forms.items():
        existing = merged.setdefault(number, [])
        # Deduped on the text alone, not on (text, gender): when a rule
        # reproduces a form a speaker already gave us, that is agreement, not a
        # second form. Keeping both would double-count it in every review table.
        seen = {e.get("text") for e in existing}
        for entry in entries:
            if entry.get("text") in seen:
                continue
            existing.append(entry)
            seen.add(entry.get("text"))
    return dict(sorted(merged.items()))


def iter_forms(forms):
    """Yield ``(number, entry)`` in number order, then declaration order.

    Used by the export tool and the tests; keeps every consumer reporting the
    same order so a regenerated review table diffs cleanly.
    """
    for number in sorted(forms):
        for entry in forms[number]:
            yield number, entry


def validate_forms(forms):
    """Every structural problem with a provenance-tracked deck, as strings.

    Empty list means the deck is well-formed. Called from the tests, so a
    malformed deck is a failing build rather than a surprise at runtime.
    """
    errors = []
    for number, entry in iter_forms(forms):
        where = f"{number}"
        if not isinstance(number, int):
            errors.append(f"{where}: number keys must be integers")
        text = entry.get("text")
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{where}: form has no text")
        elif text != text.strip() or "  " in text:
            errors.append(f"{where}: {text!r} has stray whitespace")
        elif text != text.lower():
            errors.append(f"{where}: {text!r} should be lowercase")
        if entry.get("source") not in SOURCES:
            errors.append(
                f"{where}: source must be one of {SOURCES}, got {entry.get('source')!r}"
            )
        if entry.get("gender", "both") not in GENDERS:
            errors.append(f"{where}: gender must be one of {GENDERS}")

    for number, entries in forms.items():
        seen = set()
        for entry in entries:
            key = (entry.get("text"), entry.get("gender", "both"))
            if key in seen:
                errors.append(f"{number}: duplicate form {entry.get('text')!r}")
            seen.add(key)

    return errors
