"""Generate Norwegian (Bokmål) numbers programmatically for diminumero.

Norwegian numbers:
- Compound 21-99 as one word: "tjueen", "trettifire"
- Spaces for hundreds+: "et hundre og tjueen"
- "en million", "to millioner"
"""

import os
import random


def number_to_norwegian(n):
    """Convert a number to Norwegian (Bokmål)."""
    if n == 0:
        return "null"

    ones = [
        "",
        "en",
        "to",
        "tre",
        "fire",
        "fem",
        "seks",
        "sju",
        "åtte",
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
        2: "tjue",
        3: "tretti",
        4: "førti",
        5: "femti",
        6: "seksti",
        7: "sytti",
        8: "åtti",
        9: "nitti",
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
            result = "et hundre"
        else:
            result = ones[h] + " hundre"

        if rest > 0:
            result += " og " + number_to_norwegian(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "et tusen"
        else:
            result = number_to_norwegian(th) + " tusen"

        if rest > 0:
            if rest < 100:
                result += " og " + number_to_norwegian(rest)
            else:
                result += " " + number_to_norwegian(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "en million"
        else:
            result = number_to_norwegian(mill) + " millioner"

        if rest > 0:
            if rest < 100:
                result += " og " + number_to_norwegian(rest)
            else:
                result += " " + number_to_norwegian(rest)
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
NUMBERS = {n: number_to_norwegian(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Norwegian (Bokmål) numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, norwegian in NUMBERS.items():
        f.write(f'    {num}: "{norwegian}",\n')
    f.write("}\n")

print(
    f"Generated {len(NUMBERS)} Norwegian numbers and wrote to {output_dir}/numbers.py"
)
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [20, 21, 30, 42, 100, 101, 200, 1000, 1001, 1000000, 2000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
