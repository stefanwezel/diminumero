"""The data behind the number reference pages (/<lang>/numbers/1-100 and 1-1000).

Two things live here. The word lists: the drill deck plus, above 100, the forms
tools/generate_number_reference.py committed for the numbers the deck leaves
out. And the "how it works" paragraph for each page.

Availability is derived from the data, like the numeral-system gate: a page
exists only when every number in its range has a word. Nepali has no generator,
so its 1-1000 list has holes and that page doesn't exist. Nothing here builds a
number word at request time.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import get_language_numbers

# URL slug -> inclusive range. A slug here is a page some languages can have.
REFERENCE_RANGES = {
    "1-100": (1, 100),
    "1-1000": (1, 1000),
}

_REFERENCE_DIR = Path(__file__).resolve().parent
_NUMBER_TOKEN = re.compile(r"\{(\d+)\}")

# English only for now; a non-English page shows it with the existing "not
# translated yet" marker, the way an untranslated note is shown. {n} renders the
# word for n from the same data as the table, so a paragraph can't misspell a
# number word or drift from the deck. tests/test_number_reference.py checks each
# token resolves. Words that are only fragments of a number stay in plain text.
NUMBER_PATTERNS = {
    "es": {
        "1-100": "Learn {1} to {15} by heart: they have no pattern to lean on. After that the words build themselves. {16} and {22} fuse tens and ones into a single word (watch the accents), and from {31} upward you write tens + y + ones, as in {42}.",
        "1-1000": "{100} only stands alone: anything after it turns it into ciento, as in {125}. Most hundreds are a digit plus -cientos, like {200} and {300}, but three are irregular: {500}, {700} and {900}. Then add the tens and ones with no extra word in between: {347}.",
    },
    "en": {
        "1-100": "{11} and {12} are one-offs, the teens end in -teen, like {16}, and the tens in -ty, like {20}. Note that {40} has no u. Everything from {21} to {99} joins tens and ones with a hyphen.",
        "1-1000": "Say the hundreds, then and, then the rest: {347}. That and is standard British English, which is what this list follows; American English usually drops it. Round hundreds never take an -s: {200}, not two hundreds.",
    },
    "ja": {
        "1-100": "You only need the words {1} to {10}. The rest is arithmetic you can read off the characters: {11} is ten-one, {20} is two-ten and {42} is four-ten-two. These are the Sino-Japanese numbers used for prices, dates and math. In speech, 4 and 7 are usually read yon and nana rather than shi and shichi.",
        "1-1000": "Hundreds work the same way: {300} is three-hundred and {347} is three-hundred-four-ten-seven. Plain {100} and {1000} drop the one. The characters stay regular but the sounds don't: 300 is read sanbyaku, 600 roppyaku and 800 happyaku.",
    },
    "de": {
        "1-100": "German says the ones before the tens: {21} is literally one-and-twenty and {42} is two-and-forty, all written as one word. Watch the small irregularities: {16} and {17} lose letters, and {30} ends in -ßig where the other tens end in -zig.",
        "1-1000": "Hundreds go in front and everything stays one long word, with the ones still before the tens: {347} reads as three-hundred-seven-and-forty. In speech the Ein- of {100} and {1000} is often dropped.",
    },
    "fr": {
        "1-100": "French counts in tens up to {60}, then in twenties: {70} is sixty-ten, {80} is four-twenties and {90} is four-twenty-ten. A one joins with et, as in {21} and {71}, other digits with a hyphen, as in {22}, and {81} and {91} take no et at all. Belgian and Swiss French say septante and nonante instead.",
        "1-1000": "{100} never takes un in front of it. Round hundreds take an -s, as in {200}, which disappears as soon as another number follows: {201}. So {347} has neither an and nor an -s.",
    },
    "ko": {
        "1-100": "This list uses the Sino-Korean numbers, the set for dates, money, minutes and phone numbers. They are pure arithmetic: {11} is ten-one, {20} is two-ten and {42} is four-ten-two. Sounds link across syllables, so {16} is pronounced simnyuk. Korean also has a native set (hana, dul, set) for counting things, hours and age.",
        "1-1000": "Hundreds continue the same way: {300} is three-hundred and {347} is three-hundred-four-ten-seven. Plain {100} and {1000} drop the one.",
    },
    "it": {
        "1-100": "Tens drop their final vowel before {1} and {8}, so {21} and {28} but {22}. Anything ending in 3 takes an accent: {23}. {11} to {16} end in -dici, then {17} flips the order.",
        "1-1000": "Hundreds run together with whatever follows, so {347} is a single word. {100} needs no one in front of it, and {200} to {900} are a digit plus cento: {300}, {500}.",
    },
    "zh": {
        "1-100": "You only need the words {1} to {10}. The characters spell out the arithmetic: {11} is ten-one, {20} is two-ten and {42} is four-ten-two.",
        "1-1000": "Unlike the tens, a lone {100} keeps its one. A gap inside a number is spoken as 零 (zero), as in {101}, and a one comes back before the tens after a hundred: {110}. For 2 before a hundred, {200} is also commonly said with 两 instead of 二.",
    },
    "pt": {
        "1-100": "Portuguese joins tens and ones with e: {42} is forty and two. This list uses Brazilian spelling for {14}, {16}, {17} and {19}; Portugal writes catorze, dezasseis, dezassete and dezanove. {1} and {2} also have feminine forms, uma and duas.",
        "1-1000": "{100} only stands alone: anything after it turns it into cento, as in {101}. Several hundreds are irregular enough to memorize: {200}, {300}, {500}. Put e between the parts: {347}.",
    },
    "tr": {
        "1-100": "Turkish is about as regular as numbers get. Learn {1} to {10} and the tens, then place them side by side: {11} is ten one and {42} is forty two. There are no joining words and no irregular teens.",
        "1-1000": "Hundreds are a digit plus {100}, written as separate words: {300}, {347}. A lone {100} or {1000} takes no bir (one) in front.",
    },
    "ne": {
        "1-100": "Nepali has a separate word for each number up to {99}. The start of a word often hints at the ones and the end at the tens, as in {21} and {31}, but the sounds shift too much to rely on, so most learners memorize them block by block. {99} is built from {100}.",
    },
    "sv": {
        "1-100": "Swedish writes tens and ones as one word: {42}. Teens end in -ton, like {15}, and tens in -tio, like {50}, apart from {20}. In everyday speech the -tio is usually softened, so {30} sounds like tretti.",
        "1-1000": "Hundreds stay solid too: {300}, {347}. {100} can stand alone, though you will also see etthundra.",
    },
    "da": {
        "1-100": "Danish puts the ones first, joined with og: {21} is one-and-twenty. Above {40} it counts in twenties, using shortened old words: {50} means two and a half twenties, {60} three, {70} three and a half, {80} four and {90} four and a half.",
        "1-1000": "Hundreds are a digit plus hundrede, and og comes before the last part: {347}. Inside that last part the ones still go first.",
    },
    "no": {
        "1-100": "Modern Norwegian says tens before ones, written as one word: {21}, {42}. That order became official in 1951, so you will still hear the older ones-first style from some speakers, as in en-og-tjue.",
        "1-1000": "Hundreds are written apart and og comes before the last part: {125}, {347}.",
    },
    "cy": {
        "1-100": "Welsh has two systems, and this list shows both. Decimal, taught in schools, is pure arithmetic: {11} is one-ten-one, {20} is two-ten and {42} is four-ten-two. Traditional is based on twenty and is still the one used for the time, dates and age.",
        "1-1000": "The digit before {100} changes shape or sound: {200} softens the c, {300} and {600} turn it into ch, and {500} shortens the digit. Then add the rest with decimal tens: {347}.",
    },
    "ga": {
        "1-100": "When counting, Irish numbers take the particle a: {1}, {2}. The teens add déag, as in {11}, or dhéag after 2, as in {12}. The tens are words of their own, like {30} and {40}, and the ones follow with a: {42}.",
        "1-1000": "The digit before {100} changes its first sound. Up to 6 it softens: {200}, {300}. From 7 to 9 it eclipses: {700}, {800}, {900}. Then add the rest as usual: {347}.",
    },
}


@lru_cache(maxsize=None)
def _committed_forms(lang_code):
    """The generated forms for numbers the deck leaves out. Empty if none."""
    path = _REFERENCE_DIR / lang_code / "numbers_reference.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        return {int(number): word for number, word in json.load(handle).items()}


def get_reference_numbers(lang_code, slug):
    """{number: word} for every number in the page's range, or None.

    None means the page doesn't exist for this language: the slug is unknown or
    a number in its range has no word. The deck wins over the committed forms.
    """
    if slug not in REFERENCE_RANGES:
        return None
    low, high = REFERENCE_RANGES[slug]
    deck = get_language_numbers(lang_code)
    forms = _committed_forms(lang_code)
    words = {
        number: deck.get(number) or forms.get(number) for number in range(low, high + 1)
    }
    return words if all(words.values()) else None


@lru_cache(maxsize=None)
def get_reference_slugs(lang_code):
    """The reference pages this language has, in reading order.

    Cached because every language menu asks and the data is committed.
    """
    return tuple(
        slug
        for slug in REFERENCE_RANGES
        if get_reference_numbers(lang_code, slug) is not None
    )


def render_pattern(lang_code, slug, words):
    """The page's "how it works" paragraph as segments, or None if it has none.

    Each segment is {"text": str} or {"word": str, "number": int}; the template
    decides the markup, so nothing here has to be marked safe.
    """
    template = NUMBER_PATTERNS.get(lang_code, {}).get(slug)
    if template is None:
        return None
    segments = []
    for index, part in enumerate(_NUMBER_TOKEN.split(template)):
        if index % 2:
            number = int(part)
            segments.append({"word": words[number], "number": number})
        elif part:
            segments.append({"text": part})
    return segments
