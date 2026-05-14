"""add deck_shares table

Revision ID: a7c3f4e91b22
Revises: e5f9dc9f4bd4
Create Date: 2026-05-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7c3f4e91b22"
down_revision = "e5f9dc9f4bd4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deck_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("owner_sub", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("cards_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("deck_shares", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_deck_shares_token"), ["token"], unique=True
        )
        batch_op.create_index(
            batch_op.f("ix_deck_shares_owner_sub"), ["owner_sub"], unique=False
        )


def downgrade():
    with op.batch_alter_table("deck_shares", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deck_shares_owner_sub"))
        batch_op.drop_index(batch_op.f("ix_deck_shares_token"))
    op.drop_table("deck_shares")
