# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "elevenlabs",
#   "python-dotenv",
# ]
# ///
"""
Generate pronunciation MP3s for number decks used by the Listening quiz.

For the chosen language (--lang, default "es"), each entry in
languages/<lang>/numbers.py is synthesized with ElevenLabs' eleven_turbo_v2_5
cloud model and written to static/audio/<lang>/<n>.mp3 at mp3_44100_64
(~64 kbps mono). No local model is downloaded; synthesis happens in the cloud,
so an API key is required.

Set API_KEY_11_LABS in .env (loaded via python-dotenv). Each number is voiced
by a speaker drawn at random from the language's VOICE_POOLS entry, so the
generated deck mixes voices instead of using a single speaker.

Usage:
    uv run tools/generate_audio.py                    # Spanish, generate everything (skips existing)
    uv run tools/generate_audio.py --lang ja          # Japanese deck
    uv run tools/generate_audio.py --force            # re-render even if file exists
    uv run tools/generate_audio.py --only 42          # synthesize just one number
    uv run tools/generate_audio.py --limit 10         # cap the run for quick testing
"""

import argparse
import importlib
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

REPO_ROOT = Path(__file__).resolve().parent.parent

MODEL_ID = "eleven_turbo_v2_5"
OUTPUT_FORMAT = "mp3_44100_64"

# Per-language speaker pools, sampled at random per number. Duplicates are
# intentional: they bias the random draw toward those voices.
VOICE_POOLS = {
    "es": [
        "ckoC20vA7eZDdCGKkIRK",
        "n5Et1BZxBTTgPqtFr6AC",
        "n5Et1BZxBTTgPqtFr6AC",
        "n4GNpJP6Y2Nd09pDtetA",
        "nTkjq09AuYgsNR8E4sDe",
        "v4b4rQBhckrIsOHsrbub",
        "kVp3G6YINMUwOL7ROfIF",
        "kVp3G6YINMUwOL7ROfIF",
    ],
    "ja": [
        "IIUvcn96WSMnC5WxNypI",
        "MXKtCrra8fvlDUbfKUT1",
        "urE3OJfJRxJuk9kAMN0Y",
        "urE3OJfJRxJuk9kAMN0Y",
        "4oeIbMTUt5QeJy4ZX1FC",
        "G3EZ8O36A0x9lmeOtr0f",
        "pUgmTF2V1ptIKsYb6qON",
        "8PfKHL4nZToWC3pbz9U9",
    ],
    "fr": [
        "eOwAMwUJEGkP44SKOXIH",
        "OhWejZm6c7D8CIm5epRM",
        "F1toM6PcP54s45kOOAyV",
        "ZLI7yULK3cOkcZl6GABN",
        "HuLbOdhRlvQQN8oPP0AJ",
        "gidGFDFyCSnGFnZ9hK7l",
        "bts16wA7hWMfnlEIHuRo",
        "WQKwBV2Uzw1gSGr69N8I",
    ],
    "de": [
        "NE7AIW5DoJ7lUosXV2KR",
        "v3V1d2rk6528UrLKRuy8",
        "vmVmHDKBkkCgbLVIOJRb",
        "utkd5fchbspYG3Ld0zt0",
        "t6LrOJGOwJlvBxDA0qqG",
        "fBs1tCpaSMsPcbMkLQlk",
        "z8I6YkY1XGj4qPGtLHtU",
    ],
    "pt": [
        "GM2UA3fbsIaLHcswCDX9",
        "czvzJwIVS2asEKnthV40",
        "GnDrTQvdzZ7wqAKfLzVQ",
        "DMcOknq8n1B6XshFIJKJ",
        "DMcOknq8n1B6XshFIJKJ",
        "7iqXtOF3wl3pomwXFY7G",
        "tZ2oxQJXfOrGrN7iKnta",
    ],
    "sv": [
        "kPdGSxhZAqy4bmPAf9iJ",
        "4xkUqaR9MYOJHoaC1Nak",
        "UzJFCns81AYkRdrnw0ql",
        "1Iztu4UHnTb9SUjJcpS1",
        "tomkxGQGz4b1kE0EM722",
        "HqmZnnvy6tCQd8EGWKRT",
        "DSL3PSQNPbkOavwmnYl1",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate number pronunciation MP3s via ElevenLabs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--lang",
        default="es",
        choices=sorted(VOICE_POOLS),
        help="Language code to synthesize (default: es).",
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
    voice_ids = VOICE_POOLS[args.lang]
    out_dir = REPO_ROOT / "static" / "audio" / args.lang

    sys.path.insert(0, str(REPO_ROOT))
    NUMBERS = importlib.import_module(f"languages.{args.lang}").NUMBERS

    load_dotenv()
    api_key = os.getenv("API_KEY_11_LABS")
    if not api_key:
        print("[err] API_KEY_11_LABS not found in .env", file=sys.stderr)
        sys.exit(1)

    print(
        f"Synthesizing {args.lang} with ElevenLabs {MODEL_ID}, "
        f"sampling from {len(set(voice_ids))} voices..."
    )
    client = ElevenLabs(api_key=api_key)

    out_dir.mkdir(parents=True, exist_ok=True)

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

        out_path = out_dir / f"{n}.mp3"
        if out_path.exists() and not args.force:
            skipped += 1
            continue

        voice_id = random.choice(voice_ids)
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
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
