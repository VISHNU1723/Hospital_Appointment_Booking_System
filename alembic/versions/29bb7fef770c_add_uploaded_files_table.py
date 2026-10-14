"""add uploaded files table"""

from typing import Sequence, Union

from alembic import op

revision: str = "29bb7fef770c"
down_revision: Union[str, Sequence[str], None] = "37125b0e05b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The uploaded_files table already exists in the database.
    # Keep the existing table and its foreign keys unchanged.
    pass


def downgrade() -> None:
    # Do not drop the existing table or its data.
    pass