"""SQLAlchemy models for diminumero."""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "front": self.front,
            "back": self.back,
        }
