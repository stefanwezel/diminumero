"""Traditional (vigesimal) Welsh numbers — WORK IN PROGRESS.

This is the second numeral system of Welsh, declared as `traditional` in
languages/config.py. It is the system used for telling the time, for dates and
for age, and it is not optional knowledge — see
docs/plans/welsh-traditional-numbers.md.

HOW THIS FILE WORKS
-------------------
`None` means "nobody has told us this form yet". Those entries are dropped by
the loader, so an unfinished deck can never put a blank in front of a learner,
and the system stays hidden from the site until every number from 1 to 100 is
filled in (`requires_complete` in languages/config.py). Filling the last gap
switches the feature on with no code change.

**Do not fill a gap from a pattern.** Several patterns were described to us
("[2-9] ar hugain" for 22-29, "[11-19] ar hugain" for 31-39) but the individual
forms were never given, and a rule that is right nine times out of ten still
teaches one person something wrong. If you know a form, add it; if you are
extrapolating, leave the `None` and answer the questions in
docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md instead.

PROVENANCE
----------
Every filled form below was stated verbatim in the r/learnwelsh review thread
of August 2026. Confidence is marked per line:

    OK  = stated and then corrected or confirmed by a second commenter
    ??  = single source, plausible, not yet verified

Zero is deliberately absent: the thread discussed counting, and nobody said
whether `dim` is used with this system. Decimal Welsh covers 0.

The biggest open gap is 41-99: apart from 45, no form between the tens was ever
given. That is question 1 in docs/QUESTIONS-FOR-NATIVE-SPEAKERS.md.
"""

NUMBERS = {
    # 1-10 are identical to the decimal forms (stated in the thread).
    1: "un",  # OK
    2: "dau",  # OK
    3: "tri",  # OK
    4: "pedwar",  # OK
    5: "pump",  # OK
    6: "chwech",  # OK
    7: "saith",  # OK
    8: "wyth",  # OK
    9: "naw",  # OK
    10: "deg",  # OK
    # 11-19: the "ar ddeg" / "ar bymtheg" series.
    11: "un ar ddeg",  # OK - corrected from "unarddeg" (spacing)
    12: "deuddeg",  # ?? - "deudeg" also appeared; see question 2
    13: "tri ar ddeg",  # ??
    14: "pedwar ar ddeg",  # ??
    15: "pymtheg",  # ??
    16: "un ar bymtheg",  # ??
    17: "dau ar bymtheg",  # OK - "ail ar bymtheg" is the ordinal (17th)
    18: "deunaw",  # OK - corrected from "ddeunaw" (that is the mutated form)
    19: "pedwar ar bymtheg",  # OK - "ugain namyn un" exists but is older/rural
    20: "ugain",  # OK
    21: "un ar hugain",  # OK - ugain -> hugain after "ar"
    # 22-29: described as "[2-9] ar hugain", but the forms were never
    # enumerated. TODO: needs a native speaker.
    22: None,
    23: None,
    24: None,
    25: None,
    26: None,
    27: None,
    28: None,
    29: None,
    30: "deg ar hugain",  # ??
    # 31-39: described as "[11-19] ar hugain", forms never enumerated.
    # TODO: needs a native speaker.
    31: None,
    32: None,
    33: None,
    34: None,
    35: None,
    36: None,
    37: None,
    38: None,
    39: None,
    40: "deugain",  # ?? - literally "two twenties"
    # 41-49: TODO. Only 45 was ever given, and that inside an example of what
    # you would *not* say about money. See question 1.
    41: None,
    42: None,
    43: None,
    44: None,
    45: "pump ar ddeugain",  # ?? - single source, deugain -> ddeugain after "ar"
    46: None,
    47: None,
    48: None,
    49: None,
    50: "hanner cant",  # ?? - literally "half a hundred"
    # 51-59: TODO. See question 1.
    51: None,
    52: None,
    53: None,
    54: None,
    55: None,
    56: None,
    57: None,
    58: None,
    59: None,
    60: "trigain",  # ??
    # 61-69: TODO. See question 1.
    61: None,
    62: None,
    63: None,
    64: None,
    65: None,
    66: None,
    67: None,
    68: None,
    69: None,
    70: "deg a thrigain",  # OK - corrected from "deg ar trigain"
    # 71-79: TODO. See question 1.
    71: None,
    72: None,
    73: None,
    74: None,
    75: None,
    76: None,
    77: None,
    78: None,
    79: None,
    80: "pedwar ugain",  # ?? - literally "four twenties"
    # 81-89: TODO. See question 1.
    81: None,
    82: None,
    83: None,
    84: None,
    85: None,
    86: None,
    87: None,
    88: None,
    89: None,
    90: "deg a phedwar ugain",  # ??
    # 91-99: TODO. See question 1.
    91: None,
    92: None,
    93: None,
    94: None,
    95: None,
    96: None,
    97: None,
    98: None,
    99: None,
    100: "cant",  # ??
    # 120 was mentioned as a number speakers genuinely use, but the form was
    # never given. See question 4. It sits outside the 1-100 completeness gate,
    # so adding it later does not change when the system goes live.
}
