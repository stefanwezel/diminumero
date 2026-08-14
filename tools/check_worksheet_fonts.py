#!/usr/bin/env python3
"""Verify the running environment can draw every character a worksheet uses.

    uv run tools/check_worksheet_fonts.py            # this machine
    docker run --rm <image> python tools/check_worksheet_fonts.py

This is the production gate for worksheet PDFs. `python:3.12-slim` ships no
fonts at all, so without the font packages in the Dockerfile a PDF still comes
back as a valid, correct-looking `application/pdf` — with blank boxes where the
Japanese, Korean, Chinese or Nepali words should be. Nothing about the response
reveals that, which makes it the failure most likely to reach production
unnoticed. Run this against the built image whenever the Dockerfile, the font
packages or a language deck changes.

The required characters are derived from the data, never from a hand-written
list: every word in every ready language's NUMBERS deck, plus every worksheet
string in every UI language (a sheet's chrome is rendered in the UI language,
so an Arabic or Ukrainian teacher needs those glyphs too).

Exits 1 and names the offending characters if any of them has no font.
"""

import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from languages import AVAILABLE_LANGUAGES, get_language_numbers  # noqa: E402
from translations import TRANSLATIONS  # noqa: E402

# Worksheet UI strings live under this prefix; the sheet also prints a couple
# of shared keys.
WORKSHEET_KEY_PREFIX = "worksheet_"
EXTRA_KEYS = ("info_numbers", "learn_btn_back")


def deck_characters():
    """Every character used by any ready language's number words."""
    found = {}
    for code, info in AVAILABLE_LANGUAGES.items():
        if not info.get("ready"):
            continue
        for word in get_language_numbers(code).values():
            for char in word:
                found.setdefault(char, set()).add(code)
    return found


def ui_characters():
    """Every character in the worksheet strings of every UI language."""
    found = {}
    for ui_lang, texts in TRANSLATIONS.items():
        for key, value in texts.items():
            if not (key.startswith(WORKSHEET_KEY_PREFIX) or key in EXTRA_KEYS):
                continue
            for char in str(value):
                found.setdefault(char, set()).add(f"ui:{ui_lang}")
    return found


def required_characters():
    """The full character set a worksheet can put on a page, with sources."""
    required = deck_characters()
    for char, sources in ui_characters().items():
        required.setdefault(char, set()).update(sources)
    # ASCII is covered by any font that exists at all; keeping it in the check
    # would only add noise to the failure output.
    return {char: sources for char, sources in required.items() if ord(char) > 127}


def covered_codepoints():
    """Every codepoint fontconfig can serve, from the installed fonts."""
    try:
        output = subprocess.run(
            ["fc-list", "--format=%{charset}\n"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot query fontconfig (is it installed?): {exc}")

    covered = set()
    for line in output.splitlines():
        for span in line.split():
            bounds = span.split("-")
            try:
                low = int(bounds[0], 16)
                high = int(bounds[-1], 16)
            except ValueError:
                continue
            covered.update(range(low, high + 1))
    return covered


def main():
    required = required_characters()
    covered = covered_codepoints()
    if not covered:
        print("FAIL: fontconfig reports no fonts at all", file=sys.stderr)
        return 1

    missing = sorted(
        (char, sources)
        for char, sources in required.items()
        if ord(char) not in covered
    )

    print(f"fonts known to fontconfig cover {len(covered)} codepoints")
    print(f"worksheets need {len(required)} non-ASCII characters")

    if missing:
        print(f"\nFAIL: {len(missing)} character(s) have no font:", file=sys.stderr)
        for char, sources in missing:
            name = unicodedata.name(char, "unnamed")
            print(
                f"  {char!r} U+{ord(char):04X} {name} — used by "
                f"{', '.join(sorted(sources))}",
                file=sys.stderr,
            )
        print(
            "\nInstall the font package covering those scripts in the Dockerfile.",
            file=sys.stderr,
        )
        return 1

    print("OK: every worksheet character has a font")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
