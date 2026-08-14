#!/usr/bin/env python3
"""Batch-generate printable worksheet PDFs for upload to OER portals.

    uv run tools/generate_worksheets.py                    # every ready language
    uv run tools/generate_worksheets.py --lang es de cy    # just these
    uv run tools/generate_worksheets.py --out build/sheets
    uv run tools/generate_worksheets.py --list             # show the plan only

Writes `<out>/<lang>/diminumero-<lang>-numbers-<range>-<seed>.pdf` plus a
`manifest.csv` describing every sheet (language, range, direction, sheet ID and
the URL that reprints it) — that CSV is what you paste into a portal's upload
form or use to fill in per-file metadata.

The run is reproducible: each sheet's ID is derived from its own settings, so
re-running the tool overwrites the same files with byte-identical content
rather than minting a new corpus every time. Pass --salt to deliberately
generate a *different* standard set.

Requests go through the Flask test client rather than reimplementing anything,
so a batch PDF is the same bytes as `?format=pdf` on the live site.
"""

import argparse
import csv
import hashlib
import sys
from pathlib import Path
from urllib.parse import urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app import app  # noqa: E402
from languages import AVAILABLE_LANGUAGES  # noqa: E402

# The standard set, one entry per sheet shape: (low, high, exercise count).
# Deliberately small — four shapes per direction is enough to cover a course
# without burying a portal in near-identical files.
STANDARD_RANGES = [
    (1, 20, 20),
    (1, 100, 24),
    (1, 1000, 20),
    (1000, 9999999, 14),
]

DIRECTIONS = ["digits_to_words", "words_to_digits"]


def sheet_seed(lang, low, high, count, direction, salt):
    """A stable sheet ID for one entry of the standard set.

    Derived from the settings so the corpus is reproducible: regenerating
    after a rebuild gives the same sheets, and a teacher's downloaded copy
    still matches the one on the portal.
    """
    key = f"{salt}|{lang}|{low}-{high}|{count}|{direction}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:6]


def planned_sheets(languages, salt):
    """Every sheet the run will produce, as query-param dicts."""
    for lang in languages:
        for low, high, count in STANDARD_RANGES:
            for direction in DIRECTIONS:
                yield (
                    lang,
                    {
                        "count": count,
                        "direction": direction,
                        "range": f"{low}-{high}",
                        "seed": sheet_seed(lang, low, high, count, direction, salt),
                    },
                )


def ready_languages():
    return [code for code, info in AVAILABLE_LANGUAGES.items() if info.get("ready")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lang",
        nargs="+",
        metavar="CODE",
        help="language codes to generate (default: every ready language)",
    )
    parser.add_argument(
        "--out",
        default="build/worksheets",
        help="output directory (default: build/worksheets)",
    )
    parser.add_argument(
        "--salt",
        default="v1",
        help="change to mint a different standard set (default: v1)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the plan without generating anything",
    )
    args = parser.parse_args()

    available = ready_languages()
    languages = args.lang or available
    unknown = [code for code in languages if code not in available]
    if unknown:
        parser.error(f"not a ready language: {', '.join(unknown)}")

    plan = list(planned_sheets(languages, args.salt))
    if args.list:
        for lang, params in plan:
            print(f"/{lang}/worksheet?{urlencode(params)}")
        print(f"\n{len(plan)} sheets across {len(languages)} languages")
        return 0

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    failures = []
    client = app.test_client()

    for index, (lang, params) in enumerate(plan, start=1):
        url = f"/{lang}/worksheet?{urlencode({**params, 'format': 'pdf'})}"
        response = client.get(url)

        # The route degrades to the HTML sheet if PDF rendering breaks (a
        # missing font package, say). Silently writing that HTML into a file
        # named .pdf is exactly the failure that would reach a portal, so it
        # counts as an error here.
        if response.status_code != 200 or response.mimetype != "application/pdf":
            failures.append((url, f"{response.status_code} {response.mimetype}"))
            print(f"[{index}/{len(plan)}] FAILED {url}", file=sys.stderr)
            continue

        lang_dir = out_root / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        filename = response.headers["Content-Disposition"].split('filename="')[1]
        filename = filename.rstrip('"')
        path = lang_dir / filename
        path.write_bytes(response.data)

        rows.append(
            {
                "file": str(path.relative_to(out_root)),
                "language": lang,
                "language_name": AVAILABLE_LANGUAGES[lang].get("name", lang),
                "range": params["range"],
                "exercises": params["count"],
                "direction": params["direction"],
                "sheet_id": params["seed"],
                "reprint_url": f"https://diminumero.com/{lang}/worksheet?"
                + urlencode(params),
                "licence": "CC BY-SA 4.0",
            }
        )
        print(f"[{index}/{len(plan)}] {path} ({len(response.data) // 1024} KB)")

    manifest = out_root / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])) if rows else None
        if writer:
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n{len(rows)} sheets written to {out_root}/")
    print(f"manifest: {manifest}")
    if failures:
        print(f"\n{len(failures)} FAILED:", file=sys.stderr)
        for url, why in failures:
            print(f"  {url} -> {why}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
