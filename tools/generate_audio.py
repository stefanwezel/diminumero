# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "elevenlabs",
#   "python-dotenv",
# ]
# ///
"""
Generate pronunciation MP3s for Spanish numbers used by the Listening quiz.

Each entry in languages/es/numbers.py is synthesized with ElevenLabs'
eleven_turbo_v2_5 cloud model and written to static/audio/es/<n>.mp3 at
mp3_44100_64 (~64 kbps mono). No local model is downloaded; synthesis happens
in the cloud, so an API key is required.

Set API_KEY_11_LABS in .env (loaded via python-dotenv). Each number is voiced
by a speaker drawn at random from the built-in VOICE_IDS pool, so the generated
deck mixes voices instead of using a single speaker.

Usage:
    uv run tools/generate_audio.py                    # generate everything (skips existing)
    uv run tools/generate_audio.py --force            # re-render even if file exists
    uv run tools/generate_audio.py --only 42          # synthesize just one number
    uv run tools/generate_audio.py --limit 10         # cap the run for quick testing
"""

import argparse
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "static" / "audio" / "es"

MODEL_ID = "eleven_turbo_v2_5"
OUTPUT_FORMAT = "mp3_44100_64"

# Speaker pool sampled per number. Duplicates are intentional: they bias the
# random draw toward those voices.
VOICE_IDS = [
    "ckoC20vA7eZDdCGKkIRK",
    "n5Et1BZxBTTgPqtFr6AC",
    "n5Et1BZxBTTgPqtFr6AC",
    "n4GNpJP6Y2Nd09pDtetA",
    "nTkjq09AuYgsNR8E4sDe",
    "v4b4rQBhckrIsOHsrbub",
    "kVp3G6YINMUwOL7ROfIF",
    "kVp3G6YINMUwOL7ROfIF",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Spanish number pronunciation MP3s.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-render files even when they already exist.",
    )
    parser.add_argument(
        "--only",
        type=int,
        help="Synthesize only this single number (must exist in NUMBERS).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Stop after generating this many files (useful for smoke tests).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    from languages.es import NUMBERS

    load_dotenv()
    api_key = os.getenv("API_KEY_11_LABS")
    if not api_key:
        print("[err] API_KEY_11_LABS not found in .env", file=sys.stderr)
        sys.exit(1)

    print(
        f"Synthesizing with ElevenLabs {MODEL_ID}, "
        f"sampling from {len(set(VOICE_IDS))} voices..."
    )
    client = ElevenLabs(api_key=api_key)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.only is not None:
        if args.only not in NUMBERS:
            print(f"[err] {args.only} not in NUMBERS dictionary", file=sys.stderr)
            sys.exit(1)
        items = [(args.only, NUMBERS[args.only])]
    else:
        items = sorted(NUMBERS.items())

    total = len(items)
    generated = 0
    skipped = 0
    failed = 0

    for idx, (n, text) in enumerate(items, start=1):
        if args.limit is not None and generated >= args.limit:
            print(f"Hit --limit={args.limit}, stopping.")
            break

        out_path = OUT_DIR / f"{n}.mp3"
        if out_path.exists() and not args.force:
            skipped += 1
            continue

        voice_id = random.choice(VOICE_IDS)
        try:
            audio = client.text_to_speech.convert(
                voice_id=voice_id,
                # Terminal punctuation tells the model the utterance is done,
                # which avoids trailing noise/artifacts on bare short text.
                text=f"{text}.",
                model_id=MODEL_ID,
                output_format=OUTPUT_FORMAT,
            )
            with open(out_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            generated += 1
            print(
                f"[{idx}/{total}] {n} -> {out_path.name}  ({text}) [{voice_id}]",
                flush=True,
            )
        except ApiError as exc:
            failed += 1
            print(
                f"[{idx}/{total}] FAILED {n} ({text}): "
                f"API error ({exc.status_code}): {exc.body}",
                file=sys.stderr,
            )

    print()
    print(f"Done. generated={generated} skipped={skipped} failed={failed}")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
