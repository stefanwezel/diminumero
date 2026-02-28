"""Generate French numbers programmatically for diminumero.

This script generates French number translations and saves them to numbers.py.
"""

import os
import random


def number_to_french(n):
    """Convert a number to French."""
    if n == 0:
        return "zéro"

    ones = [
        "",
        "un",
        "deux",
        "trois",
        "quatre",
        "cinq",
        "six",
        "sept",
        "huit",
        "neuf",
        "dix",
        "onze",
        "douze",
        "treize",
        "quatorze",
        "quinze",
        "seize",
    ]

    tens = [
        "",
        "dix",
        "vingt",
        "trente",
        "quarante",
        "cinquante",
        "soixante",
        "soixante",  # 70s use soixante-dix
        "quatre-vingt",  # 80s
        "quatre-vingt",  # 90s use quatre-vingt-dix
    ]

    if n < 17:
        return ones[n]

    elif n < 20:
        # 17, 18, 19: dix-sept, dix-huit, dix-neuf
        return "dix-" + ones[n - 10]

    elif n < 70:
        t, o = divmod(n, 10)
        if o == 0:
            return tens[t]
        elif o == 1:
            # 21, 31, 41, 51, 61 use "et un"
            return tens[t] + " et un"
        else:
            return tens[t] + "-" + ones[o]

    elif n < 80:
        # 70-79: soixante-dix, soixante-et-onze, soixante-douze, etc.
        o = n - 70
        if o == 0:
            return "soixante-dix"
        elif o == 1:
            return "soixante et onze"
        elif o < 7:
            return "soixante-" + ones[o + 10]
        else:
            # 77, 78, 79: soixante-dix-sept, etc.
            return "soixante-dix-" + ones[o]

    elif n < 100:
        # 80-99: quatre-vingts, quatre-vingt-un, etc.
        o = n - 80
        if o == 0:
            return "quatre-vingts"  # Note the 's'
        elif o < 10:
            return "quatre-vingt-" + ones[o]
        elif o == 10:
            return "quatre-vingt-dix"
        elif o < 17:
            # 91-96: quatre-vingt-onze, douze, treize, quatorze, quinze, seize
            return "quatre-vingt-" + ones[o]
        else:
            # 97, 98, 99: quatre-vingt-dix-sept, dix-huit, dix-neuf
            return "quatre-vingt-dix-" + ones[o - 10]

    elif n < 1000:
        h, rest = divmod(n, 100)
        if h == 1:
            result = "cent"
        else:
            result = ones[h] + " cent"
            if rest == 0:
                result += "s"  # cents when exactly 200, 300, etc.

        if rest > 0:
            result += " " + number_to_french(rest)
        return result

    elif n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "mille"
        else:
            result = number_to_french(th) + " mille"

        if rest > 0:
            result += " " + number_to_french(rest)
        return result

    elif n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "un million"
        else:
            result = number_to_french(mill) + " millions"

        if rest > 0:
            result += " " + number_to_french(rest)
        return result

    else:
        bill, rest = divmod(n, 1000000000)
        if bill == 1:
            result = "un milliard"
        else:
            result = number_to_french(bill) + " milliards"

        if rest > 0:
            result += " " + number_to_french(rest)
        return result


# Generate 1000 unique numbers
random.seed(42)  # For reproducibility
numbers_set = set()

# Ensure variety across ranges
numbers_set.update(range(1, 101))
numbers_set.update(random.sample(range(101, 1001), 200))
numbers_set.update(random.sample(range(1001, 10001), 300))
numbers_set.update(random.sample(range(10001, 100001), 200))
numbers_set.update(random.sample(range(100001, 1000001), 100))
numbers_set.update(random.sample(range(1000001, 10000001), 100))

# Generate the dictionary
NUMBERS = {n: number_to_french(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = "languages/fr"
os.makedirs(output_dir, exist_ok=True)

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""French numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, french in NUMBERS.items():
        f.write(f'    {num}: "{french}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} French numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 10 numbers:")
for num in list(NUMBERS.keys())[:10]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nSample numbers (70s, 80s, 90s):")
for num in [70, 71, 77, 80, 81, 90, 91, 99]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
