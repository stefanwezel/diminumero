# Adding Listening Exercises to diminumero

This guide explains how to enable the **Listening** quiz for a language. The
Listening quiz plays a pre-generated MP3 of a number and asks the user to type the
digits back.

Related guides:
- [ADD_NUMBERS.md](ADD_NUMBERS.md) — add a new language's number deck first (a prerequisite).
- [ADD_LEARNING_MATERIALS.md](ADD_LEARNING_MATERIALS.md) — add a Learn/tutorial page.

## Overview

Listening mode (`mode == "audio"`) is gated by two things:

1. The `has_audio_mode: True` flag on the language's entry in `languages/config.py`.
2. The MP3s that actually exist under `static/audio/<lang_code>/`.

The route never trusts the deck blindly — it intersects the number deck with
`_available_audio_numbers()` (the MP3s actually present on disk), so a
half-generated deck still works. Both the index language cards and
`mode_selection()` consult `get_languages_with_audio_mode()` to decide whether to
surface the "New · Listening" sticker.

Audio is synthesized with ElevenLabs' `eleven_turbo_v2_5` cloud model by the
PEP-723 script `tools/generate_audio.py`. Synthesis happens in the cloud — no local
model is downloaded, so an API key is required and each call uses ElevenLabs
credits. Languages currently shipping audio (1000 MP3s each): **es, de, fr, ja,
pt, sv**.

## Prerequisites

The target language must already be registered in `languages/config.py` with
`'ready': True` and a populated `languages/<lang_code>/numbers.py`. If you want to
add a new language entirely, see [ADD_NUMBERS.md](ADD_NUMBERS.md) first.

You also need an ElevenLabs API key in `.env` as `API_KEY_11_LABS` (loaded with
python-dotenv).

## Steps to Add Listening Exercises

### 1. Add a Voice Pool

In `tools/generate_audio.py`, add a `VOICE_POOLS` entry for your code — a list of
ElevenLabs voice IDs. Each number is voiced by a speaker drawn at random from this
list, so a deck mixes voices instead of using one speaker. Repeating an ID biases
the draw toward that voice.

```python
VOICE_POOLS = {
    ...
    "xx": ["voiceId1", "voiceId2", "voiceId2", "voiceId3"],
}
```

Pick voices that natively speak the target language so the pronunciation is
correct.

### 2. Generate the MP3s

Run the script with your language code:

```bash
uv run tools/generate_audio.py --lang xx
```

Each number in `languages/xx/numbers.py` is synthesized with the
`eleven_turbo_v2_5` model at `mp3_44100_64` (~64 kbps mono) and written to
`static/audio/xx/<n>.mp3`. Useful flags:

| Flag | Description |
|------|-------------|
| (none) | Skips files that already exist |
| `--force` | Re-render everything |
| `--only <n>` | Synthesize a single number |
| `--limit <n>` | Cap the run (quick test batch) |

Commit the generated MP3s — they are checked into the repo (the regeneration
output path is gitignored, but the committed files ship with the app).

### 3. Flip the Flag

Set `'has_audio_mode': True` on the language's entry in `languages/config.py`:

```python
'xx': {
    ...
    'has_audio_mode': True,
    ...
}
```

No `app.py` edits are needed — both the index language cards and
`mode_selection()` consult `get_languages_with_audio_mode()`, and the route
intersects the deck with the MP3s actually present.

## How Listening Mode Works

1. `mode_selection()` shows a Listening option for languages with `has_audio_mode: True`.
2. `/<lang_code>/listen/start` (POST) initializes a Listening session; the playable
   pool is the intersection of the number deck with `_available_audio_numbers()`.
3. `/<lang_code>/listen` (GET/POST) plays the number's MP3 (`quiz_listen.js` handles
   autoplay with a small lag), accepts a typed digit answer, and supports
   reveal/next.
4. The answer is normalized to digits (`re.sub(r"\D", "", ...)`) and compared to the
   number.
5. After 10 questions the user lands on the results page; the speed bonus reuses the
   advanced-mode time threshold (`SPEED_BONUS_TIME_ADVANCED`).

## Testing Checklist

- [ ] `VOICE_POOLS` entry added for the language code in `tools/generate_audio.py`
- [ ] MP3s generated under `static/audio/<lang_code>/` and committed
- [ ] `has_audio_mode: True` set on the language's entry in `languages/config.py`
- [ ] "New · Listening" sticker appears on the index card and mode-selection page
- [ ] Listening quiz autoplays, accepts digit answers, and reveal/next works
- [ ] A half-generated deck (only some MP3s present) still produces a valid quiz
- [ ] Native speaker confirms the pronunciations are correct

## Questions?

Check the existing audio under `static/audio/es/` and the `VOICE_POOLS` entries in
`tools/generate_audio.py` for reference, or contact the maintainer.
