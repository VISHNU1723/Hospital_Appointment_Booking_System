"""add consultations table

Revision ID: 37125b0e05b0
Revises: 496622f137e8
Create Date: 2026-10-13 11:40:50.226195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '37125b0e05b0'
down_revision: Union[str, Sequence[str], None] = '496622f137e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_table(
        "consultations",
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=False),
        sa.Column("prescription", sa.Text(), nullable=True),
        sa.Column("advice", sa.Text(), nullable=True),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("appointment_id"),
    )
    op.create_index(
        "ix_consultations_appointment_id",
        "consultations",
        ["appointment_id"],
        unique=False,
    )



def downgrade() -> None:
    op.drop_index(
        "ix_consultations_appointment_id",
        table_name="consultations",
    )
    op.drop_table("consultations")
