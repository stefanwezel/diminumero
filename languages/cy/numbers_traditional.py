"""Traditional (vigesimal) Welsh numbers, with provenance per form.

GENERATED IN PART. Rule-derived forms are written by
languages/cy/generate_numbers_traditional.py; speaker-sourced forms are edited
by hand and never overwritten by it. Run the generator after adding a form to
see whether the rule agrees with the speaker — a disagreement is reported, not
silently resolved.

This is the second numeral system of Welsh (declared as `traditional` in
languages/config.py): the one used for telling the time, for dates and for age.

FORM SHAPE
----------
    FORMS = {
        13: [
            {"text": "tri ar ddeg",  "gender": "m", "source": "single"},
            {"text": "tair ar ddeg", "gender": "f", "source": "reconstructed"},
        ],
    }

`text`    the form, lowercase, single-spaced.
`gender`  "m", "f", or absent for an invariable form. The bare-digit drill
          shows masculine; the feminine series is carried for the Learn page
          and any future noun-attached mode.
`source`  confirmed | single | reconstructed — see languages/provenance.py.
`note`    optional, for a form that needs a word of context (register,
          idiomatic vs regular).
`variant` optional label used by the review export.

The first entry of each number is the form taught.

WHAT REACHES A LEARNER
----------------------
`NUMBERS` at the bottom is derived from `FORMS`, and while
config.SERVE_RECONSTRUCTED is False it contains only speaker-sourced forms.
Reconstructed forms are committed so they can be exported for confirm-or-correct
review (tools/export_unconfirmed_forms.py) and switched on in one line — never
so they can quietly reach a learner first.

PROVENANCE OF WHAT IS HERE
--------------------------
Speaker-sourced forms come from the r/learnwelsh review thread of August 2026.
`confirmed` means two or more commenters agreed or one corrected another;
`single` means one commenter, uncorroborated. 1-10 are recorded as confirmed on
the strength of "1-10 are identical to the decimal forms" plus the separate
endorsement of the decimal deck.

The open questions are in docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md. The largest is
the 41-99 connective (`a` vs `ar`), which decides 54 forms at once.
"""

from ..provenance import build_numbers, merge_forms

try:
    # Rule-derived forms, written by generate_numbers_traditional.py. A missing
    # file is fine: the deck is then exactly what speakers have given us.
    from .numbers_traditional_generated import GENERATED
except ImportError:  # pragma: no cover - only before the first generator run
    GENERATED = {}

# Hand-edited. The generator reads this file and never writes it, so an
# editorial comment or a newly confirmed form cannot be clobbered by a rerun.
SPEAKER_FORMS = {
    0: [
        {"text": "dim", "source": "reconstructed", "note": "same in both systems"},
        {
            "text": "sero",
            "source": "reconstructed",
            "note": "temperature and maths",
            "variant": "technical",
        },
    ],
    1: [{"text": "un", "source": "confirmed"}],
    2: [{"text": "dau", "gender": "m", "source": "confirmed"}],
    3: [{"text": "tri", "gender": "m", "source": "confirmed"}],
    4: [{"text": "pedwar", "gender": "m", "source": "confirmed"}],
    5: [{"text": "pump", "source": "confirmed"}],
    6: [{"text": "chwech", "source": "confirmed"}],
    7: [{"text": "saith", "source": "confirmed"}],
    8: [{"text": "wyth", "source": "confirmed"}],
    9: [{"text": "naw", "source": "confirmed"}],
    10: [{"text": "deg", "source": "confirmed"}],
    # Corrected from "unarddeg" (spacing) in the thread.
    11: [{"text": "un ar ddeg", "source": "confirmed"}],
    12: [
        {"text": "deuddeg", "source": "single", "note": "standard"},
        {
            "text": "deudeg",
            "source": "reconstructed",
            "note": "colloquial, common when telling the time",
            "variant": "colloquial",
        },
    ],
    13: [{"text": "tri ar ddeg", "gender": "m", "source": "single"}],
    14: [{"text": "pedwar ar ddeg", "gender": "m", "source": "single"}],
    15: [{"text": "pymtheg", "source": "single"}],
    16: [{"text": "un ar bymtheg", "source": "single"}],
    # A commenter proposed "ail ar bymtheg" and was corrected: that is the ordinal.
    17: [{"text": "dau ar bymtheg", "gender": "m", "source": "confirmed"}],
    # Corrected from "ddeunaw" (the mutated form) in the thread.
    18: [{"text": "deunaw", "source": "confirmed"}],
    # "ugain namyn un" also exists but was described as older and rural.
    19: [{"text": "pedwar ar bymtheg", "gender": "m", "source": "confirmed"}],
    20: [{"text": "ugain", "source": "confirmed"}],
    21: [{"text": "un ar hugain", "source": "confirmed"}],
    30: [{"text": "deg ar hugain", "source": "single"}],
    40: [{"text": "deugain", "source": "single"}],
    # The thread's only 40s datapoint, and it uses `ar` + soft mutation where
    # the confirmed 70/90 use `a` + aspirate. See the generator.
    45: [{"text": "pump ar ddeugain", "source": "single"}],
    50: [{"text": "hanner cant", "source": "single", "note": "idiomatic"}],
    60: [{"text": "trigain", "source": "single"}],
    # Corrected from "deg ar trigain" in the thread.
    70: [{"text": "deg a thrigain", "source": "confirmed"}],
    80: [{"text": "pedwar ugain", "source": "single"}],
    90: [{"text": "deg a phedwar ugain", "source": "single"}],
    100: [{"text": "cant", "source": "single"}],
    120: [
        {"text": "chwe ugain", "source": "reconstructed"},
        {
            "text": "chweugain",
            "source": "reconstructed",
            "note": "came to mean ten shillings (120 old pence) and survived "
            "decimalisation as slang for 50p",
            "variant": "contracted",
        },
    ],
}

# Speaker forms first, so they are what gets taught; rule-derived forms follow
# and stay withheld until config.SERVE_RECONSTRUCTED says otherwise.
FORMS = merge_forms(SPEAKER_FORMS, GENERATED)

# The deck the drill sees: masculine forms only, nothing reconstructed.
NUMBERS = build_numbers(FORMS)
