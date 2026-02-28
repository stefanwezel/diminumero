"""Generate German numbers programmatically for diminumero.

This script generates German number translations and saves them to numbers.py.
"""

import os
import random


def number_to_german(n):
    """Convert a number to German."""
    if n == 0:
        return "Null"

    ones = [
        "",
        "Eins",
        "Zwei",
        "Drei",
        "Vier",
        "Fünf",
        "Sechs",
        "Sieben",
        "Acht",
        "Neun",
    ]

    # Lowercase versions for compounding
    ones_low = [
        "",
        "ein",
        "zwei",
        "drei",
        "vier",
        "fünf",
        "sechs",
        "sieben",
        "acht",
        "neun",
    ]

    tens = [
        "",
        "zehn",
        "zwanzig",
        "dreißig",
        "vierzig",
        "fünfzig",
        "sechzig",
        "siebzig",
        "achtzig",
        "neunzig",
    ]

    if n < 10:
        return ones[n]

    elif n < 20:
        if n == 10:
            return "Zehn"
        if n == 11:
            return "Elf"
        if n == 12:
            return "Zwölf"
        if n == 16:
            return "Sechzehn"  # Drops the 's'
        if n == 17:
            return "Siebzehn"  # Drops the 'en'
        return ones[n % 10] + "zehn"

    elif n < 100:
        t, o = divmod(n, 10)
        if o == 0:
            return tens[t].capitalize()
        # German flips it: "one and twenty"
        return (ones_low[o] + "und" + tens[t]).capitalize()

    elif n < 1000:
        h, rest = divmod(n, 100)
        prefix = "Ein" if h == 1 else ones[h]
        result = prefix + "hundert"
        if rest > 0:
            result += number_to_german(rest).lower()
        return result.capitalize()

    elif n < 1000000:
        th, rest = divmod(n, 1000)
        prefix = "Ein" if th == 1 else number_to_german(th)
        result = prefix + "tausend"
        if rest > 0:
            # Check if we need to lowercase the joining part
            rest_str = number_to_german(rest)
            result += rest_str.lower()
        return result.capitalize()

    elif n < 1000000000:
        mill, rest = divmod(n, 1000000)
        if mill == 1:
            result = "Eine Million"
        else:
            result = number_to_german(mill) + " Millionen"

        if rest > 0:
            result += " " + number_to_german(rest)
        return result

    else:
        bill, rest = divmod(n, 1000000000)
        if bill == 1:
            result = "Eine Milliarde"
        else:
            result = number_to_german(bill) + " Milliarden"

        if rest > 0:
            result += " " + number_to_german(rest)
        return result


# Generate 1000 unique numbers
random.seed(42)  # For reproducibility
numbers_set = set()

# Ensure variety ranges
numbers_set.update(range(1, 101))
numbers_set.update(random.sample(range(101, 1001), 200))
numbers_set.update(random.sample(range(1001, 10001), 300))
numbers_set.update(random.sample(range(10001, 100001), 200))
numbers_set.update(random.sample(range(100001, 1000001), 100))
numbers_set.update(random.sample(range(1000001, 10000001), 100))

# Generate the dictionary
NUMBERS = {n: number_to_german(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = "languages/de"
os.makedirs(output_dir, exist_ok=True)

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""German numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, german in NUMBERS.items():
        f.write(f'    {num}: "{german}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} German numbers and wrote to {output_dir}/numbers.py")
