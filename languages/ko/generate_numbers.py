"""Generate Korean (Sino-Korean) numbers programmatically for diminumero.

Sino-Korean numbers use 만(10000) grouping:
- 일 is dropped before 십/백/천 but used before 만: "일만"
- Single group has no spaces: "삼백사십오" (345)
- Space between 만-groups: "만 이천삼백사십오" (12345)
"""

import os
import random


def number_to_korean(n):
    """Convert a number to Sino-Korean."""
    if n == 0:
        return "영"

    digits = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]

    def under_10000(n):
        """Convert a number under 10000 to Korean (no spaces)."""
        if n == 0:
            return ""

        result = ""

        # Thousands
        th, remainder = divmod(n, 1000)
        if th > 0:
            if th == 1:
                result += "천"
            else:
                result += digits[th] + "천"

        # Hundreds
        h, remainder = divmod(remainder, 100)
        if h > 0:
            if h == 1:
                result += "백"
            else:
                result += digits[h] + "백"

        # Tens
        t, o = divmod(remainder, 10)
        if t > 0:
            if t == 1:
                result += "십"
            else:
                result += digits[t] + "십"

        # Ones
        if o > 0:
            result += digits[o]

        return result

    if n < 10000:
        return under_10000(n)

    if n < 100000000:  # Under 1억
        man, rest = divmod(n, 10000)
        if man == 1:
            result = "만"
        else:
            result = under_10000(man) + "만"

        if rest > 0:
            result += " " + under_10000(rest)
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
NUMBERS = {n: number_to_korean(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Korean (Sino-Korean) numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, korean in NUMBERS.items():
        f.write(f'    {num}: "{korean}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Korean numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [10, 100, 1000, 10000, 12345, 100000, 1000000]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
