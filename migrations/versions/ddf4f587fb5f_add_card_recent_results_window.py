"""add card recent results window

Revision ID: ddf4f587fb5f
Revises: 1ba2818cd571
Create Date: 2026-05-13 09:30:17.404888

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ddf4f587fb5f"
down_revision = "1ba2818cd571"
branch_labels = None
depends_on = None


WINDOW_SIZE = 10


def upgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "recent_results",
                sa.String(length=10),
                server_default="",
                nullable=False,
            )
        )

    # Backfill recent_results from the existing lifetime counters so users
    # don't see their progress rings reset on deploy. We don't have per-attempt
    # history, so we synthesize a window of size min(10, times_practiced)
    # with the right ratio of "1"s.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, times_practiced, times_correct FROM cards WHERE times_practiced > 0"
        )
    ).fetchall()
    for row in rows:
        practiced = row.times_practiced
        correct = row.times_correct
        window = min(WINDOW_SIZE, practiced)
        ones = round(correct / practiced * window)
        ones = max(0, min(window, ones))
        recent = "1" * ones + "0" * (window - ones)
        bind.execute(
            sa.text("UPDATE cards SET recent_results = :r WHERE id = :id"),
            {"r": recent, "id": row.id},
        )


def downgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("recent_results")
