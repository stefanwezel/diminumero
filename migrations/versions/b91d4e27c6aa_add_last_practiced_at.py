"""add last_practiced_at to cards and verb_cards

Gives the prioritized sampler a spacing signal. updated_at could not serve:
its onupdate fires on any row change, so editing a card's text would look
like practising it.

Revision ID: b91d4e27c6aa
Revises: 5bcdb98cd1e9
Create Date: 2026-08-27 10:14:02.881904

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b91d4e27c6aa"
down_revision = "5bcdb98cd1e9"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable with no backfill: existing rows have no honest last-practiced
    # time, and the sampler reads NULL as "no spacing signal" (neutral),
    # not as "infinitely stale". Each card stamps itself on its next attempt.
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_practiced_at", sa.DateTime(), nullable=True)
        )

    with op.batch_alter_table("verb_cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_practiced_at", sa.DateTime(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("verb_cards", schema=None) as batch_op:
        batch_op.drop_column("last_practiced_at")

    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("last_practiced_at")
