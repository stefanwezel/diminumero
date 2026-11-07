# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Fill in the numbers up to 1000 that a language's drill deck doesn't carry.

    uv run tools/generate_number_reference.py

The drill decks hold 1-100 and a random 200 of 101-1000, which is right for a
quiz and useless for a page called "how to count to 1,000": it would have no
500. So this writes languages/<code>/numbers_reference.json with the other 700,
for the reference pages only. The decks, and therefore every drill, worksheet
and listening round, are untouched.

The forms come from the same number_to_<language>() that built the deck, and
that is the whole case for trusting them, so it is checked rather than assumed:
a generator that doesn't reproduce every word of its committed deck aborts the
run. A language with no generator (Nepali, whose deck is hand-curated) gets no
file, and languages/number_reference.py then offers no 1-1000 page for it.
"""

import ast
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "languages"
FILENAME = "numbers_reference.json"
REFERENCE_MAX = 1000


def load_generator(code):
    """The language's number_to_<language>() function, or None if it has none.

    Most generate_numbers.py scripts rewrite their numbers.py at module level,
    so importing one would regenerate the deck. Only the definitions are run.
    """
    path = LANGUAGES / code / "generate_numbers.py"
    if not path.exists():
        return None

    tree = ast.parse(path.read_text(encoding="utf-8"))

    def is_definition(node):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            return True
        return isinstance(node, (ast.Assign, ast.AnnAssign)) and not any(
            isinstance(child, ast.Call) for child in ast.walk(node)
        )

    definitions = ast.Module(
        body=[node for node in tree.body if is_definition(node)], type_ignores=[]
    )
    namespace = {}
    exec(compile(definitions, str(path), "exec"), namespace)

    functions = [
        value for name, value in namespace.items() if name.startswith("number_to_")
    ]
    if len(functions) != 1:
        raise SystemExit(f"{code}: expected one number_to_*() in {path}")
    return functions[0]


def load_deck(code):
    """The committed deck, read directly so this script needs no dependencies."""
    return runpy.run_path(str(LANGUAGES / code / "numbers.py"))["NUMBERS"]


def build(code):
    """{number: word} for every 1-1000 number the deck lacks, or None.

    Raises SystemExit if the generator has drifted from the committed deck.
    """
    generator = load_generator(code)
    if generator is None:
        return None

    deck = load_deck(code)
    drifted = [
        f"{number}: deck {word!r}, generator {generator(number)!r}"
        for number, word in deck.items()
        if generator(number) != word
    ]
    if drifted:
        raise SystemExit(
            f"{code}: the generator no longer reproduces its deck, so its other "
            f"forms can't be trusted either:\n  " + "\n  ".join(drifted[:10])
        )

    forms = {
        number: generator(number)
        for number in range(1, REFERENCE_MAX + 1)
        if number not in deck
    }
    words = [deck.get(n) or forms[n] for n in range(1, REFERENCE_MAX + 1)]
    if len(set(words)) != len(words) or not all(words):
        raise SystemExit(f"{code}: blank or duplicate words in 1-{REFERENCE_MAX}")
    return forms


def serialize(forms):
    """One number per line, in order, so a regeneration diffs by the form."""
    lines = [
        f"  {json.dumps(str(number))}: {json.dumps(word, ensure_ascii=False)}"
        for number, word in sorted(forms.items())
    ]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def language_codes():
    return sorted(path.parent.name for path in LANGUAGES.glob("*/numbers.py"))


def main():
    for code in language_codes():
        forms = build(code)
        if forms is None:
            print(f"{code}: no generator, skipped")
            continue
        path = LANGUAGES / code / FILENAME
        path.write_text(serialize(forms), encoding="utf-8")
        print(f"{code}: wrote {len(forms)} forms to {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
