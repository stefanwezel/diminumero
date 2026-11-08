"""Generate Italian numbers programmatically for diminumero.

This script generates Italian number translations and saves them to numbers.py.
"""

import os
import random


def number_to_italian(n):
    """Convert a number to Italian.

    A compound ending in 3 is accented on that last syllable, wherever the 3
    comes from: ventitré, centotré, milletré. Only at the end of the written
    word, so 23,000 is ventitremila, and never on a bare tre ("tre milioni").
    That is one rule about the finished word, so it is applied once, here,
    rather than in each branch that can end on a 3.
    """
    return " ".join(
        word[: -len("tre")] + "tré" if word.endswith("tre") and word != "tre" else word
        for word in spell_italian(n).split(" ")
    )


def spell_italian(n):
    """The number in Italian, unaccented."""
    if n == 0:
        return "zero"

    ones = [
        "",
        "uno",
        "due",
        "tre",
        "quattro",
        "cinque",
        "sei",
        "sette",
        "otto",
        "nove",
        "dieci",
        "undici",
        "dodici",
        "tredici",
        "quattordici",
        "quindici",
        "sedici",
        "diciassette",
        "diciotto",
        "diciannove",
    ]

    tens = [
        "",
        "dieci",
        "venti",
        "trenta",
        "quaranta",
        "cinquanta",
        "sessanta",
        "settanta",
        "ottanta",
        "novanta",
    ]

    if n < 20:
        return ones[n]

    elif n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens[t]
        elif o == 1 or o == 8:
            # Drop the final vowel of the tens: venti -> vent + uno/otto
            return tens[t][:-1] + ones[o]
        else:
            return tens[t] + ones[o]

    elif n < 1000:
        h, rest = divmod(n, 100)
        if h == 1:
            result = "cento"
        else:
            result = ones[h] + "cento"

        if rest > 0:
            result += spell_italian(rest)
        return result

    elif n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "mille"
        else:
            result = spell_italian(th) + "mila"

        if rest > 0:
            result += spell_italian(rest)
        return result

    elif n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "un milione"
        else:
            result = spell_italian(mill) + " milioni"

        if rest > 0:
            result += " " + spell_italian(rest)
        return result

    else:
        bill, rest = divmod(n, 1000000000)
        if bill == 1:
            result = "un miliardo"
        else:
            result = spell_italian(bill) + " miliardi"

        if rest > 0:
            result += " " + spell_italian(rest)
        return result


# Generate 1000 unique numbers
random.seed(42)  # For reproducibility
numbers_set = set()

# Ensure variety across ranges
numbers_set.update(range(0, 101))
numbers_set.update(random.sample(range(101, 1001), 200))
numbers_set.update(random.sample(range(1001, 10001), 300))
numbers_set.update(random.sample(range(10001, 100001), 200))
numbers_set.update(random.sample(range(100001, 1000001), 100))
numbers_set.update(random.sample(range(1000001, 10000001), 100))

# Generate the dictionary
NUMBERS = {n: number_to_italian(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = "languages/it"
os.makedirs(output_dir, exist_ok=True)

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Italian numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, italian in NUMBERS.items():
        f.write(f'    {num}: "{italian}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Italian numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nSample numbers:")
for num in [21, 28, 33, 100, 101, 200, 1000, 2000, 1000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
