"""Generate Chinese (Mandarin) numbers programmatically for diminumero.

Chinese numbers:
- No spaces
- 一 dropped before 十 only for 10-19 (when 十 is the highest unit)
- 零 inserted for gaps between non-zero digit positions (only one 零 per gap)
- Uses 万 (10000) grouping: "一万二千三百四十五" (12345)
"""

import os
import random

DIGITS = ["零", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def _under_10000(n, is_leading=True):
    """Convert a number under 10000 to Chinese.

    Args:
        n: Number 0-9999
        is_leading: If True, drop 一 before 十 for 10-19
    """
    if n == 0:
        return ""

    th = n // 1000
    h = (n % 1000) // 100
    t = (n % 100) // 10
    o = n % 10

    result = ""
    need_zero = False

    if th > 0:
        result += DIGITS[th] + "千"

    if h > 0:
        if need_zero:
            result += "零"
        result += DIGITS[h] + "百"
        need_zero = False
    else:
        if th > 0:
            need_zero = True

    if t > 0:
        if need_zero:
            result += "零"
        # Drop 一 before 十 for 10-19
        if t == 1 and is_leading and th == 0 and h == 0:
            result += "十"
        else:
            result += DIGITS[t] + "十"
        need_zero = False
    else:
        if th > 0 or h > 0:
            need_zero = True

    if o > 0:
        if need_zero:
            result += "零"
        result += DIGITS[o]

    return result


def number_to_chinese(n):
    """Convert a number to Chinese (Mandarin)."""
    if n == 0:
        return "零"

    if n < 10000:
        return _under_10000(n, is_leading=True)

    if n < 100000000:  # Under 1亿
        man, rest = divmod(n, 10000)
        result = _under_10000(man, is_leading=True) + "万"

        if rest > 0:
            # Need 零 if thousands place of rest is 0
            if rest < 1000:
                result += "零" + _under_10000(rest, is_leading=False)
            else:
                result += _under_10000(rest, is_leading=False)
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
NUMBERS = {n: number_to_chinese(n) for n in sorted(numbers_set)}

# Write to numbers.py
output_dir = os.path.dirname(os.path.abspath(__file__))

with open(f"{output_dir}/numbers.py", "w", encoding="utf-8") as f:
    f.write('"""Chinese (Mandarin) numbers data for the quiz application."""\n\n')
    f.write("NUMBERS = {\n")
    for num, chinese in NUMBERS.items():
        f.write(f'    {num}: "{chinese}",\n')
    f.write("}\n")

print(f"Generated {len(NUMBERS)} Chinese numbers and wrote to {output_dir}/numbers.py")
print("\nFirst 20 numbers:")
for num in list(NUMBERS.keys())[:20]:
    print(f"  {num}: {NUMBERS[num]}")
print("\nKey numbers:")
for num in [10, 11, 20, 100, 101, 110, 1000, 1001, 1010, 10000, 10001, 12345]:
    if num in NUMBERS:
        print(f"  {num}: {NUMBERS[num]}")
