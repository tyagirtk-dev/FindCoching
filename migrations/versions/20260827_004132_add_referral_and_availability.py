"""Add referral system and recurring availability slots.

Revision ID: 20260827_004132
Revises: 75364882518b
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_004132"
down_revision = "75364882518b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "referral_code",
                sa.String(length=32),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "referred_by_user_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_users_referral_code",
            ["referral_code"],
            unique=True,
        )

        batch_op.create_index(
            "ix_users_referred_by_user_id",
            ["referred_by_user_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_users_referred_by_user_id_users",
            "users",
            ["referred_by_user_id"],
            ["id"],
        )

    op.create_table(
        "teacher_availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["teacher_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "teacher_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_teacher_availability_slot",
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_teacher_availability_weekday",
        ),
    )

    op.create_index(
        "ix_teacher_availability_slots_teacher_id",
        "teacher_availability_slots",
        ["teacher_id"],
    )

    op.create_table(
        "student_availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "student_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_student_availability_slot",
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_student_availability_weekday",
        ),
    )

    op.create_index(
        "ix_student_availability_slots_student_id",
        "student_availability_slots",
        ["student_id"],
    )


def downgrade():
    op.drop_index(
        "ix_student_availability_slots_student_id",
        table_name="student_availability_slots",
    )
    op.drop_table("student_availability_slots")

    op.drop_index(
        "ix_teacher_availability_slots_teacher_id",
        table_name="teacher_availability_slots",
    )
    op.drop_table("teacher_availability_slots")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_users_referred_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_users_referred_by_user_id")
        batch_op.drop_index("ix_users_referral_code")
        batch_op.drop_column("referred_by_user_id")
        batch_op.drop_column("referral_code")
