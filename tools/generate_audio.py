# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "transformers",
#   "torch",
#   "numpy",
#   "lameenc",
# ]
# ///
"""
Generate pronunciation MP3s for Spanish numbers used by the Hear & Type quiz.

Each entry in languages/es/numbers.py is synthesized with facebook/mms-tts-spa
and written to static/audio/es/<n>.mp3 at 64 kbps mono. Encoding uses lameenc
(pure-Python LAME wheel) so no system ffmpeg is required.

First run downloads the MMS-TTS Spanish model (~150 MB) from Hugging Face.

Usage:
    uv run tools/generate_audio.py               # generate everything (skips existing)
    uv run tools/generate_audio.py --force       # re-render even if file exists
    uv run tools/generate_audio.py --only 42     # synthesize just one number
    uv run tools/generate_audio.py --limit 10    # cap the run for quick testing
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "static" / "audio" / "es"


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


def to_int16(audio) -> "np.ndarray":  # noqa: F821
    import numpy as np

    arr = np.asarray(audio).squeeze()
    if arr.dtype == np.int16:
        return arr
    peak = float(max(abs(arr.max()), abs(arr.min()), 1e-9))
    return (arr / peak * 32767.0).astype(np.int16)


def encode_mp3(pcm_int16, sample_rate, out_path) -> None:
    import lameenc

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(64)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)  # 2 = high quality / slower
    data = encoder.encode(pcm_int16.tobytes())
    data += encoder.flush()
    out_path.write_bytes(data)


def main() -> None:
    args = parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    from languages.es import NUMBERS

    import torch
    from transformers import pipeline

    device = 0 if torch.cuda.is_available() else -1
    print(f"Loading facebook/mms-tts-spa on device={device}...")
    tts = pipeline("text-to-speech", model="facebook/mms-tts-spa", device=device)

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

        try:
            output = tts(text)
            audio = to_int16(output["audio"])
            encode_mp3(audio, output["sampling_rate"], out_path)
            generated += 1
            print(f"[{idx}/{total}] {n} -> {out_path.name}  ({text})", flush=True)
        except Exception as exc:
            failed += 1
            print(f"[{idx}/{total}] FAILED {n} ({text}): {exc}", file=sys.stderr)

    print()
    print(f"Done. generated={generated} skipped={skipped} failed={failed}")
    print(f"Output: {OUT_DIR}")


if __name__ == "__main__":
    main()
