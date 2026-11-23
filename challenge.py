"""Friend challenges: one random round, shared by link, compared by score.

Someone picks a language and a kind of round, and gets a link. Whoever opens
it plays exactly the same ten numbers, and finishes with a link of their own
that carries their score. Sending that back is how two people compare.

Nothing is stored on the server. A challenge lives entirely in its URL, as a
token signed with the app's secret key: the language, the mode, a seed, an
optional host name, and the scores of the people who played it so far. The
signature means a score can't be edited after the fact: change one character
and the link stops working. It does not stop a player looking up answers
while they play. Signed is not encrypted, so anyone can base64-decode a token
(or the session cookie). The token holds the seed rather than the numbers,
and the session keeps no list of them, but the seed and this file reproduce
the round, and in Listening the clip's URL names its number. Nothing here
could change that without hiding the audio behind a server-side lookup, and
for a game between friends it is accepted.

The ten numbers are a pure function of the seed and the deck, drawn the way
worksheets are (`random.Random` seeded from a SHA-256 of the seed, never
CPython's text seeding), so every player gets the same round in the same order.
Regenerating a deck between two people's runs would change the draw, and
rotating FLASK_SECRET_KEY would invalidate every link already sent. Both are
rare, and both are accepted rather than solved with a database.
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

# The kinds of round the form offers. "surprise" is resolved to one of the
# other two when the challenge is created, so a token never holds it.
KIND_NUMBERS = "numbers"
KIND_LISTENING = "listening"
KIND_SURPRISE = "surprise"
KINDS = (KIND_NUMBERS, KIND_LISTENING, KIND_SURPRISE)

# The magnitude dial a challenge is drawn at. Fixed per mode rather than taken
# from the player's session, because both players must get the same numbers.
CHALLENGE_MAGNITUDE = {"easy": 1, "advanced": 2, "hardcore": 3, "audio": 2}

# The worksheet's alphabet: no 0/o, 1/l, so a seed read aloud survives.
SEED_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
SEED_LENGTH = 8
_SEED_RE = re.compile(rf"^[{SEED_ALPHABET}]{{{SEED_LENGTH}}}$")
_LANG_RE = re.compile(r"^[a-z]{2,3}$")

NAME_MAX = 24
# How many scores travel with a link. The creator's is always kept, so the
# person who started it never drops off their own scoreboard; before they have
# played, the first score is kept in its place.
MAX_RESULTS = 5
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
    name: str
    score: int
    seconds: int
    # Played by whoever created the challenge. Not necessarily the first
    # score: a creator who pressed Share may play after their friends.
    creator: bool = False


@dataclass(frozen=True)
class Challenge:
    lang: str
    mode: str
    seed: str
    host: str = ""
    results: tuple = ()

    @property
    def kind(self):
        return KIND_LISTENING if self.mode == "audio" else KIND_NUMBERS

    def encode(self, secret):
        payload = {
            "v": TOKEN_VERSION,
            "l": self.lang,
            "m": MODE_CODES[self.mode],
            "s": self.seed,
        }
        if self.host:
            payload["h"] = self.host
        if self.results:
            payload["r"] = [
                [r.name, r.score, r.seconds, *([1] if r.creator else [])]
                for r in self.results
            ]
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
        raw_results = data.get("r", [])
        if not (isinstance(lang, str) and _LANG_RE.match(lang)):
            return None
        if mode is None or not (isinstance(seed, str) and _SEED_RE.match(seed)):
            return None
        if not _is_clean_name(host):
            return None
        if not isinstance(raw_results, list) or len(raw_results) > MAX_RESULTS:
            return None

        results = []
        for entry in raw_results:
            # [name, score, seconds], with a trailing 1 on the creator's.
            if not (isinstance(entry, list) and len(entry) in (3, 4)):
                return None
            name, score, seconds, *flag = entry
            if flag and not _is_int_in(flag[0], 1, 1):
                return None
            if not _is_clean_name(name):
                return None
            if not _is_int_in(score, 0, QUESTIONS_PER_QUIZ):
                return None
            if not _is_int_in(seconds, 0, MAX_SECONDS):
                return None
            results.append(Result(name, score, seconds, creator=bool(flag)))
        if sum(r.creator for r in results) > 1:
            return None
        return cls(lang, mode, seed, host, tuple(results))

    def with_result(self, name, score, seconds, creator=False):
        """This challenge with one more score on it: the link a player sends back.

        `creator` marks the score of the person who made the challenge. Only
        the first such score is marked, so a token never holds two.
        """
        result = Result(
            clean_name(name),
            min(max(int(score), 0), QUESTIONS_PER_QUIZ),
            min(max(int(seconds), 0), MAX_SECONDS),
            creator=creator and not self.has_creator_result,
        )
        results = (*self.results, result)
        if len(results) > MAX_RESULTS:
            # Keep the creator's score (or, before they've played, the first)
            # and the newest others, in the order they were played: the order
            # breaks ties, and the last is the player who just finished.
            keep = next((i for i, r in enumerate(results) if r.creator), 0)
            others = [i for i in range(len(results)) if i != keep]
            kept = sorted({keep, *others[-(MAX_RESULTS - 1) :]})
            results = tuple(results[i] for i in kept)
        return Challenge(self.lang, self.mode, self.seed, self.host, results)

    @property
    def has_creator_result(self):
        return any(r.creator for r in self.results)

    def ranked(self):
        """The scoreboard: best score first, the faster time breaking a tie.

        Each row is a dict for the template. `newest` marks the score added
        last, which is the viewer's own on the page they reach on finishing.
        Rows with the same score and time share a rank.
        """
        order = sorted(
            range(len(self.results)),
            key=lambda i: (-self.results[i].score, self.results[i].seconds, i),
        )
        rows = []
        previous = None
        for position, index in enumerate(order, start=1):
            result = self.results[index]
            key = (result.score, result.seconds)
            rank = rows[-1]["rank"] if key == previous else position
            previous = key
            rows.append(
                {
                    "rank": rank,
                    "name": result.name,
                    "score": result.score,
                    "seconds": result.seconds,
                    "time": format_seconds(result.seconds),
                    "newest": index == len(self.results) - 1,
                }
            )
        return rows

    def best(self):
        """The top row of the scoreboard, or None before anyone has played."""
        rows = self.ranked()
        return rows[0] if rows else None


def _serializer(secret):
    return URLSafeSerializer(secret, salt=TOKEN_SALT)


def _is_int_in(value, low, high):
    # bool is an int to Python, but `true` is not a score.
    return (
        isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    )


def _is_clean_name(value):
    return isinstance(value, str) and clean_name(value) == value


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
