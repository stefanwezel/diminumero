"""Generate Spanish numbers programmatically for diminumero.

This script generates Spanish number translations and saves them to numbers.py.
To use this as a template for other languages:
1. Copy this file to languages/<lang_code>/generate_numbers.py
2. Update the number_to_<language>() function with the target language rules
3. Update the output path
4. Run the script to generate the numbers.py file
"""


def number_to_spanish(n):
    """Convert a number to Spanish."""
    if n == 0:
        return "cero"

    ones = [
        "",
        "uno",
        "dos",
        "tres",
        "cuatro",
        "cinco",
        "seis",
        "siete",
        "ocho",
        "nueve",
    ]
    teens = [
        "diez",
        "once",
        "doce",
        "trece",
        "catorce",
        "quince",
        "dieciséis",
        "diecisiete",
        "dieciocho",
        "diecinueve",
    ]
    twenties = [
        "veinte",
        "veintiuno",
        "veintidós",
        "veintitrés",
        "veinticuatro",
        "veinticinco",
        "veintiséis",
        "veintisiete",
        "veintiocho",
        "veintinueve",
    ]
    tens = [
        "",
        "",
        "veinte",
        "treinta",
        "cuarenta",
        "cincuenta",
        "sesenta",
        "setenta",
        "ochenta",
        "noventa",
    ]
    hundreds = [
        "",
        "ciento",
        "doscientos",
        "trescientos",
        "cuatrocientos",
        "quinientos",
        "seiscientos",
        "setecientos",
        "ochocientos",
        "novecientos",
    ]

    if n < 10:
        return ones[n]
    elif n < 20:
        return teens[n - 10]
    elif n < 30:
        return twenties[n - 20]
    elif n < 100:
        t, o = divmod(n, 10)
        return tens[t] + (" y " + ones[o] if o else "")
    elif n == 100:
        return "cien"
    elif n < 1000:
        h, rest = divmod(n, 100)
        result = hundreds[h]
        if rest:
            result += " " + number_to_spanish(rest)
        return result
    elif n < 1000000:
        if n == 1000:
            return "mil"
        thousands, rest = divmod(n, 1000)
        result = (number_to_spanish(thousands) + " mil") if thousands > 1 else "mil"
        if rest:
            result += " " + number_to_spanish(rest)
        return result
    elif n < 1000000000:
        if n == 1000000:
            return "un millón"
        millions, rest = divmod(n, 1000000)
        result = number_to_spanish(millions) + (
            " millones" if millions > 1 else " millón"
        )
        if rest:
            result += " " + number_to_spanish(rest)
        return result
    else:
        billions, rest = divmod(n, 1000000000)
        result = number_to_spanish(billions) + " mil millones"
        if rest:
            result += " " + number_to_spanish(rest)
        return result


# Generate 1000 unique numbers
import random

random.seed(42)  # For reproducibility
numbers_set = set()

# Include some specific ranges to ensure variety
# 1-100: 100 numbers
numbers_set.update(range(1, 101))

# 101-1000: 200 numbers
numbers_set.update(random.sample(range(101, 1001), 200))

# 1001-10000: 300 numbers
numbers_set.update(random.sample(range(1001, 10001), 300))

# 10001-100000: 200 numbers
numbers_set.update(random.sample(range(10001, 100001), 200))

# 100001-1000000: 100 numbers
numbers_set.update(random.sample(range(100001, 1000001), 100))

# Over 1000000: 100 numbers
numbers_set.update(random.sample(range(1000001, 10000001), 100))

# Generate the dictionary
NUMBERS = {n: number_to_spanish(n) for n in sorted(numbers_set)}

# Write to numbers.py in the same directory
with open("languages/es/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Spanish numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, spanish in NUMBERS.items():
        f.write(f'    {num}: "{spanish}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Spanish numbers and wrote to languages/es/numbers.py")
print("\nFirst 10 numbers:")
for num in list(NUMBERS.keys())[:10]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nLast 10 numbers:")
for num in list(NUMBERS.keys())[-10:]:
    print(f"  {num}: {NUMBERS[num]}")
