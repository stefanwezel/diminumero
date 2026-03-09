"""Generate Brazilian Portuguese numbers programmatically for diminumero.

Brazilian Portuguese numbers:
- "e" connector: "vinte e um"
- 100 = "cem" exactly, 101+ = "cento e ..."
- Special hundreds: "duzentos", "trezentos", "quinhentos"
- 1000 = "mil" (no "um")
"""

import os
import random


def number_to_portuguese(n):
    """Convert a number to Brazilian Portuguese."""
    if n == 0:
        return "zero"

    ones = [
        "",
        "um",
        "dois",
        "três",
        "quatro",
        "cinco",
        "seis",
        "sete",
        "oito",
        "nove",
        "dez",
        "onze",
        "doze",
        "treze",
        "quatorze",
        "quinze",
        "dezesseis",
        "dezessete",
        "dezoito",
        "dezenove",
    ]

    tens_words = {
        2: "vinte",
        3: "trinta",
        4: "quarenta",
        5: "cinquenta",
        6: "sessenta",
        7: "setenta",
        8: "oitenta",
        9: "noventa",
    }

    hundreds_words = {
        1: "cento",
        2: "duzentos",
        3: "trezentos",
        4: "quatrocentos",
        5: "quinhentos",
        6: "seiscentos",
        7: "setecentos",
        8: "oitocentos",
        9: "novecentos",
    }

    if n < 20:
        return ones[n]

    if n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens_words[t]
        return tens_words[t] + " e " + ones[o]

    if n == 100:
        return "cem"

    if n < 1000:
        h, rest = divmod(n, 100)
        result = hundreds_words[h]

        if rest > 0:
            result += " e " + number_to_portuguese(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        if th == 1:
            result = "mil"
        else:
            result = number_to_portuguese(th) + " mil"

        if rest > 0:
            if rest < 100 or rest % 100 == 0:
                result += " e " + number_to_portuguese(rest)
            else:
                result += " " + number_to_portuguese(rest)
        return result

    if n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "um milhão"
        else:
            result = number_to_portuguese(mill) + " milhões"

        if rest > 0:
            if rest < 100 or rest % 100 == 0:
                result += " e " + number_to_portuguese(rest)
            else:
                result += " " + number_to_portuguese(rest)
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
NUMBERS = {n: number_to_portuguese(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Brazilian Portuguese numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, portuguese in NUMBERS.items():
        f.write(f'    {num}: "{portuguese}",\n')
    f.write("}\n")

print(
    f"Generated {len(NUMBERS)} Portuguese numbers and wrote to {output_dir}/numbers.py"
)
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [20, 21, 100, 101, 200, 300, 500, 1000, 1001, 1000000, 2000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
