"""Generate Japanese (Kanji) numbers programmatically for diminumero.

Japanese numbers:
- No spaces ever
- 一 dropped before 十/百/千 but used before 万: "一万"
- "一万二千三百四十五" (12345)
"""

import os
import random


def number_to_japanese(n):
    """Convert a number to Japanese (Kanji)."""
    if n == 0:
        return "零"

    digits = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]

    def under_10000(n):
        """Convert a number under 10000 to Japanese (no spaces)."""
        if n == 0:
            return ""

        result = ""

        # Thousands
        th, remainder = divmod(n, 1000)
        if th > 0:
            if th == 1:
                result += "千"
            else:
                result += digits[th] + "千"

        # Hundreds
        h, remainder = divmod(remainder, 100)
        if h > 0:
            if h == 1:
                result += "百"
            else:
                result += digits[h] + "百"

        # Tens
        t, o = divmod(remainder, 10)
        if t > 0:
            if t == 1:
                result += "十"
            else:
                result += digits[t] + "十"

        # Ones
        if o > 0:
            result += digits[o]

        return result

    if n < 10000:
        return under_10000(n)

    if n < 100000000:  # Under 1億
        man, rest = divmod(n, 10000)
        result = under_10000(man) + "万"

        if rest > 0:
            result += under_10000(rest)
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
NUMBERS = {n: number_to_japanese(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Japanese (Kanji) numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, japanese in NUMBERS.items():
        f.write(f'    {num}: "{japanese}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Japanese numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [10, 100, 1000, 10000, 12345, 100000, 1000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
