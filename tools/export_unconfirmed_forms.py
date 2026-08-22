#!/usr/bin/env python3
"""Dump every number form no speaker has confirmed, as a markdown table.

    uv run tools/export_unconfirmed_forms.py --lang cy --system traditional
    uv run tools/export_unconfirmed_forms.py --source single      # smallest ask
    uv run tools/export_unconfirmed_forms.py --include-notes
    uv run tools/export_unconfirmed_forms.py --out review.md

This is the other half of the provenance rule. Withholding unconfirmed forms
from learners is only useful if there is a cheap way to get them confirmed, and
that means handing a speaker a table they can correct in one pass rather than a
Python file they have to read.

`--source single` is the staged ask: a dozen forms one person gave us, which is
a far smaller favour than the whole table and unblocks more (those forms are
already being drilled).

Two of the three tiers here **are** being taught — `single` and `attested` —
which is the reason to export them rather than only the withheld ones. Only
`reconstructed` waits for config.SERVE_RECONSTRUCTED. See
languages/provenance.py.
"""

import argparse
import importlib
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from languages.config import get_number_system  # noqa: E402
from languages.provenance import SOURCES, iter_forms  # noqa: E402

# What each tier means, printed above the table so a reviewer knows what they
# are being asked to do.
SOURCE_BLURB = {
    "single": (
        "One person told us this and nobody corroborated it. **These are already "
        "being taught**, so a correction here matters most."
    ),
    "attested": (
        "Produced by a rule that a published reference states, cited by a "
        "reviewer. **These are being taught**, but no speaker has checked these "
        "individual forms — a spot-check is exactly what is wanted."
    ),
    "reconstructed": (
        "Produced by applying a grammatical rule — by a script or an LLM — with "
        "nothing published behind the rule. **No speaker has ever confirmed "
        "these**, and the site does not teach them. They are guesses written "
        "down so they can be checked."
    ),
}

GENDER_LABEL = {"m": "masculine", "f": "feminine", "both": ""}


def load_forms(lang_code, system_key):
    """The provenance-tracked FORMS dict of one language's numeral system."""
    system = get_number_system(lang_code, system_key)
    if system is None:
        raise SystemExit(f"{lang_code} has no numeral system {system_key!r}")
    module = importlib.import_module(f"languages.{lang_code}.{system['module']}")
    forms = getattr(module, "FORMS", None)
    if forms is None:
        raise SystemExit(
            f"languages/{lang_code}/{system['module']}.py has no FORMS dict — "
            "it is not provenance-tracked, so there is nothing to review."
        )
    return forms


def rows(forms, wanted_sources):
    for number, entry in iter_forms(forms):
        if entry["source"] not in wanted_sources:
            continue
        detail = " · ".join(
            part
            for part in (
                GENDER_LABEL.get(entry.get("gender", "both"), ""),
                entry.get("variant", ""),
                entry.get("note", ""),
            )
            if part
        )
        yield number, entry["text"], detail


def render_table(forms, source):
    lines = [
        f"### Forms marked `{source}`",
        "",
        SOURCE_BLURB.get(source, ""),
        "",
        "| Number | Our form | Notes | Correct? |",
        "|---|---|---|---|",
    ]
    count = 0
    for number, text, detail in rows(forms, {source}):
        lines.append(f"| {number} | `{text}` | {detail} | |")
        count += 1
    lines.append("")
    return ("\n".join(lines), count) if count else ("", 0)


def load_notes(lang_code):
    path = REPO_ROOT / "languages" / lang_code / "notes.toml"
    if not path.is_file():
        return []
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return [note for note in data.get("note") or [] if not note.get("reviewed")]


def render_notes(notes):
    if not notes:
        return ""
    lines = [
        "### Notes awaiting review",
        "",
        "Short factual asides shown next to a number after the learner answers. "
        "These are prose, which makes them harder to check than a word list and "
        "easier to be subtly wrong in — a note that is nearly right teaches with "
        "more authority than a bare form ever could.",
        "",
        "| Applies to | Note | Correct? |",
        "|---|---|---|",
    ]
    for note in notes:
        text = note.get("text", "").replace("|", "\\|")
        scope = note.get("applies_to", "all")
        systems = note.get("systems")
        if systems:
            scope = f"{scope} ({', '.join(systems)})"
        lines.append(f"| {scope} | {text} | |")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="cy")
    parser.add_argument("--system", default="traditional")
    parser.add_argument(
        "--source",
        choices=[s for s in SOURCES if s != "confirmed"],
        action="append",
        help="restrict to one tier (repeatable); default is every unconfirmed tier",
    )
    parser.add_argument("--include-notes", action="store_true")
    parser.add_argument("--out", type=Path, help="write here instead of stdout")
    args = parser.parse_args()

    forms = load_forms(args.lang, args.system)
    wanted = args.source or [s for s in SOURCES if s != "confirmed"]

    chunks = [
        f"## {args.lang}/{args.system}: forms awaiting confirmation",
        "",
        "Everything below is either uncorroborated or derived from a rule. "
        "Correct anything that is wrong, and say so if a form is right — a "
        "second person agreeing is what moves a form to confirmed.",
        "",
    ]
    total = 0
    for source in wanted:
        table, count = render_table(forms, source)
        if count:
            chunks.append(table)
            total += count

    if args.include_notes:
        chunks.append(render_notes(load_notes(args.lang)))

    output = "\n".join(chunks).rstrip() + "\n"

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"{total} forms -> {args.out}")
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
