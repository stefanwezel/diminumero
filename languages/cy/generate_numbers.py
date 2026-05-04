"""Generate Welsh numbers programmatically for diminumero.

Uses the modern decimal system ("Cyfrif degol y Gymraeg") taught in
primary schools today, not the traditional vigesimal system.

Mutation rules baked into the strings:
- pump -> pum, chwech -> chwe before deg/cant/mil (apocope)
- Soft mutation after dau: dau ddeg, dau gant
- Aspirate mutation after tri/chwe: tri chant, chwe chant
- Feminine forms before mil for 2-4: dwy fil, tair mil, pedair mil
"""

import os
import random


def _apocope(s):
    """Apply pump->pum, chwech->chwe apocope to trailing word before mil/miliwn."""
    if s.endswith("pump"):
        return s[:-4] + "pum"
    if s.endswith("chwech"):
        return s[:-6] + "chwe"
    return s


def number_to_welsh(n):
    """Convert a non-negative integer to Welsh (modern decimal system)."""
    if n == 0:
        return "dim"

    ones = [
        "",
        "un",
        "dau",
        "tri",
        "pedwar",
        "pump",
        "chwech",
        "saith",
        "wyth",
        "naw",
        "deg",
        "un deg un",
        "un deg dau",
        "un deg tri",
        "un deg pedwar",
        "un deg pump",
        "un deg chwech",
        "un deg saith",
        "un deg wyth",
        "un deg naw",
    ]

    tens = {
        2: "dau ddeg",
        3: "tri deg",
        4: "pedwar deg",
        5: "pum deg",
        6: "chwe deg",
        7: "saith deg",
        8: "wyth deg",
        9: "naw deg",
    }

    hundreds = {
        1: "cant",
        2: "dau gant",
        3: "tri chant",
        4: "pedwar cant",
        5: "pum cant",
        6: "chwe chant",
        7: "saith cant",
        8: "wyth cant",
        9: "naw cant",
    }

    thousands_low = {
        2: "dwy fil",
        3: "tair mil",
        4: "pedair mil",
        5: "pum mil",
        6: "chwe mil",
        7: "saith mil",
        8: "wyth mil",
        9: "naw mil",
    }

    if n < 20:
        return ones[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens[t]
        return tens[t] + " " + ones[o]

    if n < 1000:
        h, rest = divmod(n, 100)
        result = hundreds[h]
        if rest > 0:
            result += " " + number_to_welsh(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "mil"
        elif 2 <= th <= 9:
            result = thousands_low[th]
        else:
            th_str = number_to_welsh(th)
            if th_str.endswith("ant"):
                th_str = th_str[:-1]
            th_str = _apocope(th_str)
            result = th_str + " mil"
        if rest > 0:
            result += " " + number_to_welsh(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "miliwn"
        else:
            result = _apocope(number_to_welsh(mill)) + " miliwn"
        if rest > 0:
            result += " " + number_to_welsh(rest)
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

NUMBERS = {n: number_to_welsh(n) for n in sorted(numbers_set)}

output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Welsh numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, welsh in NUMBERS.items():
        f.write(f'    {num}: "{welsh}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Welsh numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [20, 21, 30, 47, 100, 101, 200, 365, 1000, 1234, 1000000, 2000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
