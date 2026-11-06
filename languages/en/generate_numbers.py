"""Generate English numbers programmatically for diminumero.

Uses British English, matching the UK flag the language is listed under.

Rules baked into the strings:
- "and" before the tens and units: two hundred and thirty-four, one thousand
  and five, one million and one. American English usually drops it.
- It only ever bridges to a bare tens-and-units remainder, so 1200 stays
  one thousand two hundred and 1005000 stays one million five thousand.
- A hyphen between tens and units: twenty-three
- "one", not "a", before hundred/thousand/million: one hundred
- No commas between groups, since a typed answer is compared literally
"""

import os
import random

UNDER_TWENTY = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]

TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def number_to_english(n):
    """Convert a non-negative integer below one billion to British English."""
    if n < 20:
        return UNDER_TWENTY[n]

    if n < 100:
        t, o = divmod(n, 10)
        return TENS[t] + ("-" + UNDER_TWENTY[o] if o else "")

    if n < 1000:
        h, rest = divmod(n, 100)
        result = UNDER_TWENTY[h] + " hundred"
        if rest:
            result += " and " + number_to_english(rest)
        return result

    if n < 1000000:
        th, rest = divmod(n, 1000)
        result = number_to_english(th) + " thousand"
    else:
        mill, rest = divmod(n, 1000000)
        result = number_to_english(mill) + " million"

    if rest:
        result += (" and " if rest < 100 else " ") + number_to_english(rest)
    return result


if __name__ == "__main__":
    # Generate ~1000 unique numbers across magnitude bands
    random.seed(42)
    numbers_set = set()

    numbers_set.update(range(0, 101))
    numbers_set.update(random.sample(range(101, 1001), 200))
    numbers_set.update(random.sample(range(1001, 10001), 300))
    numbers_set.update(random.sample(range(10001, 100001), 200))
    numbers_set.update(random.sample(range(100001, 1000001), 100))
    numbers_set.update(random.sample(range(1000001, 10000001), 100))

    NUMBERS = {n: number_to_english(n) for n in sorted(numbers_set)}

    output_dir = os.path.dirname(os.path.abspath(__file__))

    with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
        f.write('"""English numbers data for the quiz application."""\n\n')
        f.write("NUMBERS = {\n")
        for num, english in NUMBERS.items():
            f.write(f'    {num}: "{english}",\n')
        f.write("}\n")

    print(
        f"Generated {len(NUMBERS)} English numbers and wrote to {output_dir}/numbers.py"
    )
    print("\nFirst 20 numbers:")
    for num in list(NUMBERS.keys())[:20]:
        print(f"  {num}: {NUMBERS[num]}")
    print("\nKey numbers:")
    for num in [20, 21, 30, 47, 100, 101, 200, 365, 1000, 1234, 1000000, 2000000]:
        if num in NUMBERS:
            print(f"  {num}: {NUMBERS[num]}")
