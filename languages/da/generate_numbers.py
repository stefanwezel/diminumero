"""Generate Danish numbers programmatically for diminumero.

This script generates Danish number translations and saves them to numbers.py.

Danish numbers use a vigesimal (base-20) system for tens 50-90:
- halvtreds = 2.5 × 20 = 50
- tres = 3 × 20 = 60
- halvfjerds = 3.5 × 20 = 70
- firs = 4 × 20 = 80
- halvfems = 4.5 × 20 = 90

Compound numbers 21-99 are written as one word: unit + "og" + tens.
E.g., 25 = femogtyve, 73 = treoghalvfjerds
"""

import os
import random


def number_to_danish(n):
    """Convert a number to Danish."""
    if n == 0:
        return "nul"

    ones = [
        "",
        "en",
        "to",
        "tre",
        "fire",
        "fem",
        "seks",
        "syv",
        "otte",
        "ni",
        "ti",
        "elleve",
        "tolv",
        "tretten",
        "fjorten",
        "femten",
        "seksten",
        "sytten",
        "atten",
        "nitten",
    ]

    tens_words = {
        2: "tyve",
        3: "tredive",
        4: "fyrre",
        5: "halvtreds",
        6: "tres",
        7: "halvfjerds",
        8: "firs",
        9: "halvfems",
    }

    if n < 20:
        return ones[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens_words[t]
        return ones[o] + "og" + tens_words[t]

    if n < 1000:
        h, rest = divmod(n, 100)
        if h == 1:
            result = "et hundrede"
        else:
            result = ones[h] + " hundrede"

        if rest > 0:
            result += " og " + number_to_danish(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "et tusind"
        else:
            result = number_to_danish(th) + " tusind"

        if rest > 0:
            if rest < 100:
                result += " og " + number_to_danish(rest)
            else:
                result += " " + number_to_danish(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "en million"
        else:
            result = number_to_danish(mill) + " millioner"

        if rest > 0:
            if rest < 100:
                result += " og " + number_to_danish(rest)
            elif rest < 1000:
                result += " " + number_to_danish(rest)
            else:
                result += " " + number_to_danish(rest)
        return result

    return str(n)


# Generate ~1000 unique numbers
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
NUMBERS = {n: number_to_danish(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Danish numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, danish in NUMBERS.items():
        f.write(f'    {num}: "{danish}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Danish numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey vigesimal numbers:")
for num in [20, 21, 30, 40, 50, 55, 60, 70, 73, 80, 90, 99]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
print("\nLarger numbers:")
for num in [100, 125, 1000, 1001, 10000, 100000, 1000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
