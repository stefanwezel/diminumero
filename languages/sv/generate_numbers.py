"""Generate Swedish numbers programmatically for diminumero.

Swedish numbers:
- Compound 21-99 as one word: "tjugoen", "tjugotvå"
- 100 = "hundra", 200 = "tvåhundra"
- "en miljon", "två miljoner"
"""

import os
import random


def number_to_swedish(n):
    """Convert a number to Swedish."""
    if n == 0:
        return "noll"

    ones = [
        "",
        "en",
        "två",
        "tre",
        "fyra",
        "fem",
        "sex",
        "sju",
        "åtta",
        "nio",
        "tio",
        "elva",
        "tolv",
        "tretton",
        "fjorton",
        "femton",
        "sexton",
        "sjutton",
        "arton",
        "nitton",
    ]

    tens_words = {
        2: "tjugo",
        3: "trettio",
        4: "fyrtio",
        5: "femtio",
        6: "sextio",
        7: "sjuttio",
        8: "åttio",
        9: "nittio",
    }

    if n < 20:
        return ones[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens_words[t]
        return tens_words[t] + ones[o]

    if n < 1000:
        h, rest = divmod(n, 100)
        if h == 1:
            result = "hundra"
        else:
            result = ones[h] + "hundra"

        if rest > 0:
            result += number_to_swedish(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "tusen"
        else:
            result = number_to_swedish(th) + "tusen"

        if rest > 0:
            result += number_to_swedish(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "en miljon"
        else:
            result = number_to_swedish(mill) + " miljoner"

        if rest > 0:
            result += " " + number_to_swedish(rest)
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
NUMBERS = {n: number_to_swedish(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Swedish numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, swedish in NUMBERS.items():
        f.write(f'    {num}: "{swedish}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Swedish numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [20, 21, 100, 101, 200, 1000, 1001, 10000, 1000000, 2000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
