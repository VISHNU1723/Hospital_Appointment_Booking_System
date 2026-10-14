
"""add follow up reminder sent flag

Revision ID: f41e5d46cdc7
Revises: d6f7681985f2
Create Date: 2026-10-14 04:20:08.076960
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f41e5d46cdc7"
down_revision: Union[str, Sequence[str], None] = "d6f7681985f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the follow-up reminder sent flag."""
    op.add_column(
        "appointments",
        sa.Column(
            "follow_up_reminder_sent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Remove the follow-up reminder sent flag."""
    op.drop_column("appointments", "follow_up_reminder_sent")
