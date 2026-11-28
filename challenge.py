"""Friend challenges: one random round, shared by link, compared by score.

Someone picks a language and a kind of round, and gets a link. Whoever opens
it plays exactly the same ten numbers, and their score goes on the
challenge's scoreboard, which every copy of the link shows.

A challenge is its URL: a token signed with the app's secret key holding the
language, the mode, a seed and an optional host name. The scores are not in
it. They are stored on the server under the seed (models.ChallengeResult, see
app.py), because a link can't be changed once sent: when scores travelled in
the link, one copied before its creator played never showed their score.
The signature means a token can't be edited; it does not stop a player
looking up answers while they play. Signed is not encrypted, so anyone can
base64-decode a token (or the session cookie). The token holds the seed
rather than the numbers, and the session keeps no list of them, but the seed
and this file reproduce the round, and in Listening the clip's URL names its
number. Nothing here could change that without hiding the audio behind a
server-side lookup, and for a game between friends it is accepted.

The ten numbers are a pure function of the seed and the deck, drawn the way
worksheets are (`random.Random` seeded from a SHA-256 of the seed, never
CPython's text seeding), so every player gets the same round in the same order.
Regenerating a deck between two people's runs would change the draw, and
rotating FLASK_SECRET_KEY would invalidate every link already sent. Both are
rare, and both are accepted.

A verb challenge is the same idea with the creator's own verbs: the token
carries up to ten of the infinitives on their list and the tenses to ask, and
the ten (verb, tense, person) questions are drawn from those with the seed.
The verbs are in the token on purpose, since sharing what you are learning is
the point (the page lists them, and lets a player add the ones they lack);
which person and tense each is asked in is not, for the same reason the
numbers aren't. The tenses are stored by key, not by position in the
language's list, so a renamed tense breaks a link loudly rather than quietly
asking the second player something else.
"""

import hashlib
import random
import re
import secrets
import unicodedata
from dataclasses import dataclass

from itsdangerous import BadData, URLSafeSerializer

import quiz_logic
from config import QUESTIONS_PER_QUIZ

TOKEN_VERSION = 1
TOKEN_SALT = "diminumero-challenge-v1"
# A real token is a couple of hundred characters. Anything far longer is not
# one of ours, and need not be decoded to find that out.
TOKEN_MAX_LENGTH = 1000

# Session mode -> the one letter that stands for it in a token, and back.
MODE_CODES = {"easy": "e", "advanced": "a", "hardcore": "h", "audio": "l"}
CODE_MODES = {code: mode for mode, code in MODE_CODES.items()}
NUMBER_MODES = ("easy", "advanced", "hardcore")
DEFAULT_NUMBER_MODE = "advanced"

# The kinds of round the form offers. "surprise" is resolved to numbers or
# listening when the challenge is created, so a token never holds it. It never
# picks verbs, which need an account and verbs of the creator's own.
KIND_NUMBERS = "numbers"
KIND_LISTENING = "listening"
KIND_VERBS = "verbs"
KIND_SURPRISE = "surprise"
KINDS = (KIND_NUMBERS, KIND_LISTENING, KIND_VERBS, KIND_SURPRISE)

# A verb challenge is typed, like conjugation practice: there is no multiple
# choice to play it as.
VERB_MODES = ("advanced", "hardcore")
DEFAULT_VERB_MODE = "advanced"
# One verb per question at most, so every verb in the token is asked.
MAX_VERBS = QUESTIONS_PER_QUIZ
VERB_MAX_LENGTH = 40
# Tense keys are each language's own ("indicativo/presente"); the longest list
# today has ten. Generous, but a bound, so a token can't be stuffed.
MAX_TENSES = 16
TENSE_MAX_LENGTH = 64

# The magnitude dial a challenge is drawn at. Fixed per mode rather than taken
# from the player's session, because both players must get the same numbers.
CHALLENGE_MAGNITUDE = {"easy": 1, "advanced": 2, "hardcore": 3, "audio": 2}

# The worksheet's alphabet: no 0/o, 1/l, so a seed read aloud survives.
SEED_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
SEED_LENGTH = 8
_SEED_RE = re.compile(rf"^[{SEED_ALPHABET}]{{{SEED_LENGTH}}}$")
_LANG_RE = re.compile(r"^[a-z]{2,3}$")

NAME_MAX = 24
# How many rows a scoreboard shows: the best, plus the viewer's own if it is
# further down. A link posted somewhere public could gather hundreds.
SCOREBOARD_ROWS = 10
MAX_SECONDS = 3599
# Seeds the session remembers having created or played, newest last.
MAX_REMEMBERED = 20

# Invisible characters that are part of how a name is written (Persian ZWNJ,
# the joiner inside emoji sequences) and so are kept. Every other format
# character goes, the bidi overrides among them: U+202E would let a name
# reverse the text after it.
_KEPT_FORMAT_CHARS = {"‌", "‍"}


@dataclass(frozen=True)
class Result:
    """One score, shaped like a stored models.ChallengeResult row."""

    name: str
    score: int
    seconds: int
    # Order of play: the earlier of two equal scores and times ranks first.
    id: int = 0


@dataclass(frozen=True)
class Challenge:
    lang: str
    mode: str
    seed: str
    host: str = ""
    # A verb challenge: the creator's verbs and the tenses to ask them in, and
    # whether the language's optional person (Spanish vosotros) is asked too.
    # Empty for a numbers or listening round.
    verbs: tuple = ()
    tenses: tuple = ()
    optional_person: bool = False

    @property
    def kind(self):
        if self.verbs:
            return KIND_VERBS
        return KIND_LISTENING if self.mode == "audio" else KIND_NUMBERS

    @property
    def is_verbs(self):
        return bool(self.verbs)

    def encode(self, secret):
        payload = {
            "v": TOKEN_VERSION,
            "l": self.lang,
            "m": MODE_CODES[self.mode],
            "s": self.seed,
        }
        if self.host:
            payload["h"] = self.host
        if self.verbs:
            payload["vb"] = list(self.verbs)
            payload["t"] = list(self.tenses)
            if self.optional_person:
                payload["o"] = 1
        return _serializer(secret).dumps(payload)

    @classmethod
    def decode(cls, token, secret):
        """The challenge a token describes, or None for anything not exactly ours."""
        if not isinstance(token, str) or len(token) > TOKEN_MAX_LENGTH:
            return None
        try:
            data = _serializer(secret).loads(token)
        except BadData:
            return None
        if not isinstance(data, dict) or data.get("v") != TOKEN_VERSION:
            return None

        lang = data.get("l")
        mode = CODE_MODES.get(data.get("m"))
        seed = data.get("s")
        host = data.get("h", "")
        # A token from before scores were stored may still hold some ("r");
        # they are ignored, and the challenge reads its scores like any other.
        if not (isinstance(lang, str) and _LANG_RE.match(lang)):
            return None
        if mode is None or not (isinstance(seed, str) and _SEED_RE.match(seed)):
            return None
        if not _is_clean_name(host):
            return None

        verbs, tenses, optional_person = (), (), False
        if "vb" in data or "t" in data or "o" in data:
            verbs = _string_list(data.get("vb"), MAX_VERBS, VERB_MAX_LENGTH)
            tenses = _string_list(data.get("t"), MAX_TENSES, TENSE_MAX_LENGTH)
            if verbs is None or tenses is None or mode not in VERB_MODES:
                return None
            flag = data.get("o", 0)
            if not _is_int_in(flag, 0, 1):
                return None
            optional_person = bool(flag)

        return cls(
            lang,
            mode,
            seed,
            host,
            verbs=verbs,
            tenses=tenses,
            optional_person=optional_person,
        )


def ranked(results, mine=None, limit=SCOREBOARD_ROWS):
    """The scoreboard: best score first, the faster time breaking a tie.

    `results` are a challenge's scores (Result, or stored rows, which have the
    same fields). Equal scores and times share a rank, and are listed in the
    order they were played. Each row is a dict for the template; `mine` is the
    id of the viewer's own score, marked on its row and shown even when it is
    below the first `limit`.
    """
    order = sorted(results, key=lambda r: (-r.score, r.seconds, r.id))
    rows = []
    previous = None
    for position, result in enumerate(order, start=1):
        key = (result.score, result.seconds)
        rank = rows[-1]["rank"] if key == previous else position
        previous = key
        rows.append(board_row(result, rank, mine is not None and result.id == mine))
    shown = rows[:limit]
    shown += [row for row in rows[limit:] if row["mine"]]
    return shown


def board_row(result, rank, mine=False):
    """One scoreboard row for the template, as ranked() makes them."""
    return {
        "rank": rank,
        "name": result.name,
        "score": result.score,
        "seconds": result.seconds,
        "time": format_seconds(result.seconds),
        "mine": mine,
    }


def _serializer(secret):
    return URLSafeSerializer(secret, salt=TOKEN_SALT)


def _is_int_in(value, low, high):
    # bool is an int to Python, but `true` is not a score.
    return (
        isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    )


def _is_clean_name(value):
    return isinstance(value, str) and clean_name(value) == value


def _string_list(value, max_items, max_length):
    """`value` as a tuple of distinct, non-empty, printable strings, or None.

    Whether each one is a real verb or tense is the app's question (it has the
    pools); this only keeps a token to the shape encode() writes.
    """
    if not isinstance(value, list) or not 1 <= len(value) <= max_items:
        return None
    for item in value:
        if not (
            isinstance(item, str)
            and 0 < len(item) <= max_length
            and item == item.strip()
            and all(unicodedata.category(ch)[0] != "C" for ch in item)
        ):
            return None
    if len(set(value)) != len(value):
        return None
    return tuple(value)


def clean_name(raw):
    """A display name fit to put on a page someone else will open.

    Whitespace collapsed, control and invisible formatting characters removed,
    at most NAME_MAX characters. Empty means anonymous.
    """
    if not isinstance(raw, str):
        return ""
    # Whitespace (a newline is a control character too) separates words, so it
    # becomes a space; any other control or format character is dropped.
    kept = "".join(
        " " if ch.isspace() else ch
        for ch in raw
        if ch.isspace()
        or ch in _KEPT_FORMAT_CHARS
        or unicodedata.category(ch)[0] != "C"
    )
    return " ".join(kept.split())[:NAME_MAX].strip()


def new_seed():
    return "".join(secrets.choice(SEED_ALPHABET) for _ in range(SEED_LENGTH))


def _rng(purpose, seed):
    digest = hashlib.sha256(f"challenge:{purpose}:{seed}".encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


def draw_numbers(deck, seed, mode, count=QUESTIONS_PER_QUIZ):
    """The challenge's numbers, in the order they are asked.

    A weighted draw without repeats from the sorted deck, at the mode's fixed
    magnitude level, so the same seed and deck always give the same round.
    """
    pool = sorted(deck)
    level = CHALLENGE_MAGNITUDE.get(mode, 1)
    weights = [quiz_logic.magnitude_weight(num, level) for num in pool]
    rng = _rng("numbers", seed)
    picked = []
    for _ in range(min(count, len(pool))):
        index = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        picked.append(pool.pop(index))
        weights.pop(index)
    return picked


def draw_verb_questions(
    verbs, tenses, persons, has_form, seed, count=QUESTIONS_PER_QUIZ
):
    """A verb challenge's questions, as (verb, tense, person) in the order asked.

    `has_form(verb, tense, person)` says whether the pool has that cell (a
    stative English verb has no continuous, Spanish has no yo imperative). The
    verbs are dealt out in turn, so no verb is asked twice before every verb
    has been asked once, and the round is then shuffled so they don't come in
    a fixed cycle. Like draw_numbers(), a pure function of its arguments: the
    same token gives everyone the same round.
    """
    rng = _rng("verbs", seed)
    cells = {
        verb: [
            (tense, person)
            for tense in tenses
            for person in persons
            if has_form(verb, tense, person)
        ]
        for verb in verbs
    }
    order = [verb for verb in verbs if cells[verb]]
    rng.shuffle(order)
    picked = []
    while len(picked) < count and any(cells[verb] for verb in order):
        for verb in order:
            if len(picked) == count:
                break
            if cells[verb]:
                tense, person = cells[verb].pop(rng.randrange(len(cells[verb])))
                picked.append((verb, tense, person))
    rng.shuffle(picked)
    return picked


def options_rng(seed, number):
    """The generator for one easy-mode question's options, the same for everyone."""
    return _rng(f"options:{number}", seed)


def remember_seed(me, key, seed):
    """`me` (the session's challenge memory) with `seed` added under `key`."""
    me = dict(me or {})
    seeds = [s for s in me.get(key, []) if s != seed]
    seeds.append(seed)
    me[key] = seeds[-MAX_REMEMBERED:]
    return me


def format_seconds(seconds):
    """0:41, 2:05 — no unit word, so nothing to translate."""
    return f"{seconds // 60}:{seconds % 60:02d}"
