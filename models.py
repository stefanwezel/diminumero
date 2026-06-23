"""SQLAlchemy models for diminumero."""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

SCORE_WINDOW_SIZE = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Card(db.Model):
    """A user-owned vocabulary index card.

    Belongs to an Auth0 user via `user_sub` (the OIDC `sub` claim).
    Both sides are free-form text — no per-card language tag — and
    answer comparison is normalized via quiz_logic.normalize_text.
    """

    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(255), nullable=False, index=True)
    front = db.Column(db.Text, nullable=False)
    back = db.Column(db.Text, nullable=False)
    times_practiced = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    times_correct = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    recent_results = db.Column(
        db.String(SCORE_WINDOW_SIZE),
        nullable=False,
        default="",
        server_default="",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    @property
    def score(self) -> float | None:
        history = self.recent_results or ""
        if not history:
            return None
        return history.count("1") / len(history)

    def record_attempt(self, correct: bool) -> None:
        history = (self.recent_results or "") + ("1" if correct else "0")
        self.recent_results = history[-SCORE_WINDOW_SIZE:]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "front": self.front,
            "back": self.back,
            "times_practiced": self.times_practiced,
            "times_correct": self.times_correct,
            "score": self.score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VerbCard(db.Model):
    """A Spanish verb a user has added to their conjugation-practice pool.

    Holds only the infinitive — the conjugations live in the committed global
    pool (languages/es/conjugations.json), validated at add time. Scoring mirrors
    `Card`: a 10-char `recent_results` window plus lifetime counters, used to bias
    the practice sampler toward weak/unpracticed verbs.
    """

    __tablename__ = "verb_cards"

    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(255), nullable=False, index=True)
    infinitive = db.Column(db.String(64), nullable=False)
    times_practiced = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    times_correct = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    recent_results = db.Column(
        db.String(SCORE_WINDOW_SIZE),
        nullable=False,
        default="",
        server_default="",
    )
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    @property
    def score(self) -> float | None:
        history = self.recent_results or ""
        if not history:
            return None
        return history.count("1") / len(history)

    def record_attempt(self, correct: bool) -> None:
        history = (self.recent_results or "") + ("1" if correct else "0")
        self.recent_results = history[-SCORE_WINDOW_SIZE:]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "infinitive": self.infinitive,
            "times_practiced": self.times_practiced,
            "times_correct": self.times_correct,
            "score": self.score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DeckShare(db.Model):
    """A shareable snapshot of one user's deck.

    Created on demand when a user clicks "Share". The snapshot of
    (front, back) pairs is frozen at creation time so the recipient
    sees the deck as it existed when shared — later edits or deletes
    by the owner don't affect what gets imported.
    """

    __tablename__ = "deck_shares"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    owner_sub = db.Column(db.String(255), nullable=False, index=True)
    owner_name = db.Column(db.String(255), nullable=True)
    cards_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    @property
    def cards(self) -> list[dict]:
        import json as _json

        try:
            data = _json.loads(self.cards_json or "[]")
        except ValueError:
            return []
        return [c for c in data if isinstance(c, dict) and "front" in c and "back" in c]


class PollResponse(db.Model):
    """A single submission of the in-app feedback poll.

    `user_sub` is nullable — anonymous visitors may also respond.
    """

    __tablename__ = "poll_responses"

    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(255), nullable=True, index=True)
    color_scheme_pref = db.Column(db.String(16), nullable=False)
    cards_aware = db.Column(db.String(16), nullable=False)
    device = db.Column(db.String(16), nullable=False)
    freeform = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
