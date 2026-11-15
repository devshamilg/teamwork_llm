"""add room_members

Revision ID: a1b2c3d4e5f6
Revises: c848e5bbf329
Create Date: 2026-11-15 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import fastapi_users_db_sqlalchemy

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c848e5bbf329"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "room_members",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("room_id", sa.UUID(), nullable=False),
        sa.Column(
            "user_id",
            fastapi_users_db_sqlalchemy.generics.GUID(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default=sa.text("'member'"),
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "user_id", name="uq_room_members_room_user"),
    )

    # Backfill room creators as owners
    op.execute(
        """
        INSERT INTO room_members (room_id, user_id, role)
        SELECT id, created_by, 'owner'
        FROM rooms
        ON CONFLICT DO NOTHING;
        """
    )

    # Backfill existing invitations
    op.execute(
        """
        INSERT INTO room_members (room_id, user_id, role)
        SELECT room_id, user_id, role
        FROM room_invitations
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_table("room_members")
