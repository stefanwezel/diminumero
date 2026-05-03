"""Generate Irish numbers programmatically for diminumero.

Uses the modern decimal system (córas deachúlach) taught in Irish
primary schools today, not the traditional vigesimal "trí fichid" system.

The standalone counting form ("a haon, a dó, ...") is used for 1-19.
The connector "a" reappears between tens and units (fiche a haon, etc.).

Mutation rules baked into the strings:
- Lenition on céad/míle/milliún after 1-6 (dhá chéad, trí chéad, ...)
- Eclipsis on céad after 7-9 (seacht gcéad)
- m is not eclipsed, so seacht/ocht/naoi míle stays as-is
- h-prothesis on vowel-initial: a haon, a hocht
- Lenition on déag after "dó": a dó dhéag
"""

import os
import random


def number_to_irish(n):
    """Convert a non-negative integer to Irish (modern decimal, abstract form)."""
    if n == 0:
        return "náid"

    abstract_1_19 = {
        1: "a haon",
        2: "a dó",
        3: "a trí",
        4: "a ceathair",
        5: "a cúig",
        6: "a sé",
        7: "a seacht",
        8: "a hocht",
        9: "a naoi",
        10: "a deich",
        11: "a haon déag",
        12: "a dó dhéag",
        13: "a trí déag",
        14: "a ceathair déag",
        15: "a cúig déag",
        16: "a sé déag",
        17: "a seacht déag",
        18: "a hocht déag",
        19: "a naoi déag",
    }

    counting_10_19 = {
        10: "deich",
        11: "aon déag",
        12: "dó dhéag",
        13: "trí déag",
        14: "ceathair déag",
        15: "cúig déag",
        16: "sé déag",
        17: "seacht déag",
        18: "ocht déag",
        19: "naoi déag",
    }

    tens_form = {
        2: "fiche",
        3: "tríocha",
        4: "daichead",
        5: "caoga",
        6: "seasca",
        7: "seachtó",
        8: "ochtó",
        9: "nócha",
    }

    hundreds_form = {
        1: "céad",
        2: "dhá chéad",
        3: "trí chéad",
        4: "ceithre chéad",
        5: "cúig chéad",
        6: "sé chéad",
        7: "seacht gcéad",
        8: "ocht gcéad",
        9: "naoi gcéad",
    }

    thousands_form_low = {
        1: "míle",
        2: "dhá mhíle",
        3: "trí mhíle",
        4: "ceithre mhíle",
        5: "cúig mhíle",
        6: "sé mhíle",
        7: "seacht míle",
        8: "ocht míle",
        9: "naoi míle",
    }

    millions_form_low = {
        1: "milliún",
        2: "dhá mhilliún",
        3: "trí mhilliún",
        4: "ceithre mhilliún",
        5: "cúig mhilliún",
        6: "sé mhilliún",
        7: "seacht milliún",
        8: "ocht milliún",
        9: "naoi milliún",
    }

    if n < 20:
        return abstract_1_19[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens_form[t]
        return tens_form[t] + " " + abstract_1_19[o]

    if n < 1000:
        h, rest = divmod(n, 100)
        result = hundreds_form[h]
        if rest > 0:
            result += " " + number_to_irish(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if 1 <= th <= 9:
            result = thousands_form_low[th]
        elif th < 20:
            result = counting_10_19[th] + " míle"
        else:
            result = number_to_irish(th) + " míle"
        if rest > 0:
            result += " " + number_to_irish(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if 1 <= mill <= 9:
            result = millions_form_low[mill]
        elif mill < 20:
            result = counting_10_19[mill] + " milliún"
        else:
            result = number_to_irish(mill) + " milliún"
        if rest > 0:
            result += " " + number_to_irish(rest)
        return result

    return str(n)


# Generate ~1000 unique numbers across magnitude bands
random.seed(42)
numbers_set = set()

numbers_set.update(range(1, 101))
numbers_set.update(random.sample(range(101, 1001), 200))
numbers_set.update(random.sample(range(1001, 10001), 300))
numbers_set.update(random.sample(range(10001, 100001), 200))
numbers_set.update(random.sample(range(100001, 1000001), 100))
numbers_set.update(random.sample(range(1000001, 10000001), 100))

NUMBERS = {n: number_to_irish(n) for n in sorted(numbers_set)}

output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Irish numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, irish in NUMBERS.items():
        f.write(f'    {num}: "{irish}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Irish numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [20, 21, 30, 47, 100, 101, 200, 365, 1000, 1234, 1000000, 2000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
