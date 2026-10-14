"""add doctor reviews

Revision ID: 634aa86ad571
Revises: f41e5d46cdc7
Create Date: 2026-10-14 12:41:45.324460
"""

from alembic import op
import sqlalchemy as sa

revision = "634aa86ad571"
down_revision = "f41e5d46cdc7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create only the new doctor_reviews table.
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "appointment_id",
            sa.Integer(),
            sa.ForeignKey("appointments.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id"),
            nullable=False,
        ),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("reviews")
