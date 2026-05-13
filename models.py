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
