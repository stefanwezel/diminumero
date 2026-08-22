"""Per-number notes: short factual asides attached to numbers.

A note is a sentence a learner benefits from at the moment a number is in front
of them — "before a word starting with m-, deg becomes deng" — plus optional
example/gloss pairs. Notes live in ``languages/<code>/notes.toml``, one file per
language, parsed with the standard library's ``tomllib`` so contributing one
needs no dependency, no build step and no source file. See ADD_NOTES.md.

Three things this module is responsible for:

1. **Scope.** A note attaches to one number, a list, a range, or everything
   (``applies_to``), optionally narrowed to one numeral system (``systems``).
2. **The answer-leak rule.** A note must never appear next to an unanswered
   prompt if it gives the answer away. ``when="prompt"`` returns only notes that
   declare they reveal nothing *and* have been reviewed; every other surface
   (after a reveal, on the results page, on a reference page) gets all of them.
   ``validate_notes()`` re-checks the declaration mechanically so a mistaken
   ``reveals_answer = false`` fails CI rather than leaking in production.
3. **Never breaking a drill.** Reading notes at request time swallows every
   error and returns nothing: a malformed note file must not take a quiz down.
   Strictness lives in ``validate_notes()``, which the test suite runs.
"""

import logging
import re
import tomllib
from pathlib import Path

from .config import (
    AVAILABLE_LANGUAGES,
    get_language_numbers,
    get_number_systems,
)

LANGUAGES_DIR = Path(__file__).resolve().parent

NOTES_FILENAME = "notes.toml"

# Notes that may sit next to a live, unanswered prompt: they must both declare
# that they give nothing away and have been checked by someone who knows the
# language. Everything else waits until the answer is on screen.
WHEN_PROMPT = "prompt"

# "20", "11-19", "11-19,30", "all"
_APPLIES_TOKEN = re.compile(r"^(?:all|\d+(?:-\d+)?)$")

_CACHE = {}

logger = logging.getLogger(__name__)


def reset_cache():
    """Drop the parsed-notes cache (tests write temporary note files)."""
    _CACHE.clear()


def notes_path(lang_code, ui_lang=None):
    """Where a language's notes file (or one of its translations) lives."""
    name = NOTES_FILENAME if ui_lang is None else f"notes.{ui_lang}.toml"
    return LANGUAGES_DIR / lang_code / name


def languages_with_notes():
    """Language codes that ship a notes file."""
    return sorted(code for code in AVAILABLE_LANGUAGES if notes_path(code).is_file())


def parse_applies_to(value):
    """Parse an ``applies_to`` string into a matcher.

    Returns ``(is_everything, [(low, high), ...])``. Raises ValueError on
    anything the grammar doesn't cover — callers at request time catch it.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("applies_to must be a non-empty string")

    everything = False
    ranges = []
    for raw in value.split(","):
        token = raw.strip()
        if not _APPLIES_TOKEN.match(token):
            raise ValueError(f"invalid applies_to token: {raw!r}")
        if token == "all":
            everything = True
            continue
        if "-" in token:
            low, high = (int(part) for part in token.split("-", 1))
            if low > high:
                low, high = high, low
        else:
            low = high = int(token)
        ranges.append((low, high))
    return everything, ranges


def _matches_number(note, number):
    if note["applies_to_all"]:
        return True
    return any(low <= number <= high for low, high in note["applies_to_ranges"])


def _matches_system(note, system):
    if system is None or not note["systems"]:
        return True
    return system in note["systems"]


def _read_toml(path):
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _build_note(raw, authored_in):
    """Normalise one ``[[note]]`` table into the shape templates render."""
    note_id = raw.get("id")
    text = raw.get("text")
    if not isinstance(note_id, str) or not note_id.strip():
        raise ValueError("note is missing an id")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"note {note_id!r} is missing text")

    everything, ranges = parse_applies_to(raw.get("applies_to", "all"))

    systems = raw.get("systems") or []
    if not isinstance(systems, list) or any(not isinstance(s, str) for s in systems):
        raise ValueError(f"note {note_id!r}: systems must be a list of strings")

    examples = []
    for example in raw.get("examples") or []:
        phrase = example.get("phrase")
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError(f"note {note_id!r}: an example has no phrase")
        gloss = example.get("gloss")
        if gloss is not None and not isinstance(gloss, str):
            raise ValueError(f"note {note_id!r}: gloss must be a string")
        examples.append({"phrase": phrase, "gloss": gloss})

    return {
        "id": note_id,
        "text": text,
        "examples": examples,
        "source": raw.get("source"),
        "reviewed": bool(raw.get("reviewed", False)),
        # Default true: a note is assumed to give the answer away until its
        # author says otherwise, because that is the safe direction to be wrong.
        "reveals_answer": bool(raw.get("reveals_answer", True)),
        "systems": systems,
        "applies_to": raw.get("applies_to", "all"),
        "applies_to_all": everything,
        "applies_to_ranges": ranges,
        "lang": authored_in,
        "translated": True,
    }


def _load_source(lang_code):
    """Parse a language's authoritative notes file. Raises on malformed input."""
    path = notes_path(lang_code)
    if not path.is_file():
        return []

    data = _read_toml(path)
    authored_in = data.get("authored_in", "en")
    return [_build_note(raw, authored_in) for raw in data.get("note") or []]


def _load_overrides(lang_code, ui_lang):
    """Translated text for a UI language, keyed by note id."""
    path = notes_path(lang_code, ui_lang)
    if not path.is_file():
        return {}

    data = _read_toml(path)
    overrides = {}
    for raw in data.get("note") or []:
        note_id = raw.get("id")
        if not isinstance(note_id, str):
            continue
        overrides[note_id] = raw
    return overrides


def _apply_override(note, override, ui_lang):
    """Overlay a translation onto a note; phrases stay in the target language."""
    translated = dict(note)
    text = override.get("text")
    if isinstance(text, str) and text.strip():
        translated["text"] = text
        translated["lang"] = ui_lang
        translated["translated"] = True

    glosses = {
        example.get("phrase"): example.get("gloss")
        for example in override.get("examples") or []
    }
    if glosses:
        translated["examples"] = [
            {
                "phrase": example["phrase"],
                "gloss": glosses.get(example["phrase"], example["gloss"]),
            }
            for example in note["examples"]
        ]
    return translated


def load_notes(lang_code, ui_lang=None):
    """Every note for a language, resolved into ``ui_lang`` where possible.

    A note with no translation is returned in the language it was written in
    with ``translated`` False, so the page can say so rather than hide a fact
    from everyone who doesn't read the authoring language.
    """
    cache_key = (lang_code, ui_lang)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    try:
        notes = _load_source(lang_code)
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        # A broken notes file costs the notes, never the drill.
        logger.exception("Could not load notes for %r", lang_code)
        _CACHE[cache_key] = []
        return []

    if ui_lang:
        try:
            overrides = _load_overrides(lang_code, ui_lang)
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            logger.exception("Could not load %r note translations", ui_lang)
            overrides = {}

        resolved = []
        for note in notes:
            if note["lang"] == ui_lang:
                resolved.append(note)
            elif note["id"] in overrides:
                resolved.append(_apply_override(note, overrides[note["id"]], ui_lang))
            else:
                untranslated = dict(note)
                untranslated["translated"] = False
                resolved.append(untranslated)
        notes = resolved

    _CACHE[cache_key] = notes
    return notes


def get_notes(lang_code, system=None, numbers=None, when="reference", ui_lang=None):
    """Notes to render on one surface. Never raises.

    Args:
        lang_code: learning language.
        system: numeral system key, or None to ignore system scoping.
        numbers: an int, an iterable of ints, or None for every note.
        when: ``"prompt"`` while the answer is still hidden (returns only notes
            that reveal nothing and have been reviewed), anything else for a
            surface where the answer is already known.
        ui_lang: UI language to resolve translations against.
    """
    try:
        notes = load_notes(lang_code, ui_lang)
    except Exception:  # pragma: no cover - load_notes already swallows
        logger.exception("Could not read notes for %r", lang_code)
        return []

    if numbers is None:
        wanted = None
    elif isinstance(numbers, int):
        wanted = [numbers]
    else:
        wanted = [n for n in numbers if isinstance(n, int)]

    selected = []
    for note in notes:
        if not _matches_system(note, system):
            continue
        if wanted is not None and not any(_matches_number(note, n) for n in wanted):
            continue
        if when == WHEN_PROMPT and not (
            not note["reveals_answer"] and note["reviewed"]
        ):
            continue
        selected.append(note)
    return selected


# ===== Validation (run by the test suite, i.e. by CI) =====


def _deck_numbers(lang_code, systems):
    """Every number the given systems (or all of them) can ask about."""
    numbers = set()
    for system in get_number_systems(lang_code):
        if systems and system["key"] not in systems:
            continue
        try:
            numbers.update(get_language_numbers(lang_code, system["key"]))
        except ValueError:
            continue
    return numbers


def _deck_words(lang_code, systems):
    """Every answer string the given systems can ask for, normalised."""
    from quiz_logic import normalize_text

    words = set()
    for system in get_number_systems(lang_code):
        if systems and system["key"] not in systems:
            continue
        try:
            deck = get_language_numbers(lang_code, system["key"])
        except ValueError:
            continue
        words.update(normalize_text(word) for word in deck.values())
    return words


def _leaks_answer(note, lang_code):
    """Whether a note's own text contains an answer it could sit next to.

    Mechanical and deliberately blunt: it catches a note that spells out a word
    the learner is being asked to produce. It cannot catch a note that gives the
    answer away by description ("this one is literally 'two nines'"), which is
    why a prompt-side note must also be reviewed by a human.
    """
    from quiz_logic import normalize_text

    haystack = " ".join(
        [note["text"]] + [example["phrase"] for example in note["examples"]]
    )
    haystack = f" {normalize_text(haystack)} "

    scoped_numbers = None
    if not note["applies_to_all"]:
        scoped_numbers = {
            number
            for low, high in note["applies_to_ranges"]
            for number in range(low, high + 1)
        }

    for system in get_number_systems(lang_code):
        if note["systems"] and system["key"] not in note["systems"]:
            continue
        try:
            deck = get_language_numbers(lang_code, system["key"])
        except ValueError:
            continue
        for number, word in deck.items():
            if scoped_numbers is not None and number not in scoped_numbers:
                continue
            if f" {normalize_text(word)} " in haystack:
                return word
    return None


def validate_notes(lang_code):
    """Every problem with a language's notes, as human-readable strings.

    Returns an empty list when the file is fine (or absent). This is what makes
    a bad note a failing build instead of a wrong lesson.
    """
    errors = []
    path = notes_path(lang_code)
    if not path.is_file():
        return errors

    if lang_code not in AVAILABLE_LANGUAGES:
        return [f"{path.name}: {lang_code!r} is not a registered language"]

    try:
        notes = _load_source(lang_code)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"{lang_code}/{NOTES_FILENAME}: {exc}"]

    declared_systems = {system["key"] for system in get_number_systems(lang_code)}
    seen_ids = set()

    for note in notes:
        where = f"{lang_code}/{NOTES_FILENAME} [{note['id']}]"

        if note["id"] in seen_ids:
            errors.append(f"{where}: duplicate id")
        seen_ids.add(note["id"])

        unknown = [s for s in note["systems"] if s not in declared_systems]
        if unknown:
            errors.append(f"{where}: unknown number system(s) {unknown}")

        strings = [note["text"], note["source"] or ""]
        strings += [example["phrase"] for example in note["examples"]]
        strings += [example["gloss"] or "" for example in note["examples"]]
        if any("<" in value for value in strings):
            errors.append(f"{where}: notes are plain text, '<' is not allowed")

        if not note["applies_to_all"]:
            deck = _deck_numbers(lang_code, note["systems"])
            # Every part of applies_to has to select something. Decks are sparse
            # above 100 by design, so a range only has to *overlap* the deck —
            # but a note aimed at one specific number that isn't there, or at a
            # range entirely outside it, is a typo pointing at nothing.
            for low, high in note["applies_to_ranges"]:
                if not any(number in deck for number in range(low, high + 1)):
                    token = str(low) if low == high else f"{low}-{high}"
                    errors.append(
                        f"{where}: applies_to {token} matches no number this "
                        f"language has a word for"
                    )

        if not note["reveals_answer"]:
            leaked = _leaks_answer(note, lang_code)
            if leaked:
                errors.append(
                    f"{where}: reveals_answer is false but the note contains the "
                    f"answer {leaked!r}"
                )

    for ui_lang in _override_languages(lang_code):
        try:
            overrides = _load_overrides(lang_code, ui_lang)
        except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{lang_code}/notes.{ui_lang}.toml: {exc}")
            continue
        for note_id in overrides:
            if note_id not in seen_ids:
                errors.append(
                    f"{lang_code}/notes.{ui_lang}.toml [{note_id}]: no such note "
                    f"in {NOTES_FILENAME}"
                )

    return errors


def _override_languages(lang_code):
    """UI languages this language ships note translations for."""
    directory = LANGUAGES_DIR / lang_code
    if not directory.is_dir():
        return []
    found = []
    for path in directory.glob("notes.*.toml"):
        parts = path.name.split(".")
        if len(parts) == 3:
            found.append(parts[1])
    return sorted(found)
