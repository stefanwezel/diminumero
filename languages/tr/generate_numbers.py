"""Generate Turkish numbers programmatically for diminumero.

Turkish numbers are space-separated and regular:
- 100 = "yüz" (not "bir yüz")
- 1000 = "bin" (not "bir bin")
- 21 = "yirmi bir", 345 = "üç yüz kırk beş"
"""

import os
import random


def number_to_turkish(n):
    """Convert a number to Turkish."""
    if n == 0:
        return "sıfır"

    ones = [
        "",
        "bir",
        "iki",
        "üç",
        "dört",
        "beş",
        "altı",
        "yedi",
        "sekiz",
        "dokuz",
    ]

    tens = [
        "",
        "on",
        "yirmi",
        "otuz",
        "kırk",
        "elli",
        "altmış",
        "yetmiş",
        "seksen",
        "doksan",
    ]

    if n < 10:
        return ones[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens[t]
        return tens[t] + " " + ones[o]

    if n < 1000:
        h, rest = divmod(n, 100)
        if h == 1:
            result = "yüz"
        else:
            result = ones[h] + " yüz"

        if rest > 0:
            result += " " + number_to_turkish(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "bin"
        else:
            result = number_to_turkish(th) + " bin"

        if rest > 0:
            result += " " + number_to_turkish(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        result = number_to_turkish(mill) + " milyon"

        if rest > 0:
            result += " " + number_to_turkish(rest)
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
NUMBERS = {n: number_to_turkish(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Turkish numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, turkish in NUMBERS.items():
        f.write(f'    {num}: "{turkish}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Turkish numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [10, 20, 21, 30, 40, 50, 99, 100, 101, 200, 1000, 1001, 1000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
