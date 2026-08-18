"""Phase 1: Payment Settings + Payment Verification System

Adds PaymentSettings, PaymentTransaction (replaces Payment), PaymentVerification,
and Refund. Existing rows in the old `payments` table are copied into
`payment_transactions` before the old table is dropped, so no payment history
is lost.

Revision ID: 0002_payment_phase1
Revises: 0001_initial
Create Date: 2026-07-23 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_payment_phase1"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


OLD_TO_NEW_STATUS = {
    "submitted": "pending",
    "verified": "verified",
    "rejected": "rejected",
}


def _table_exists(bind, name):
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    # 1. Preserve existing payment rows before dropping the old table
    # ------------------------------------------------------------------
    old_rows = []
    if _table_exists(bind, "payments"):
        old_rows = bind.execute(sa.text("SELECT * FROM payments")).mappings().all()
        op.drop_table("payments")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS paymentstatus")

    # ------------------------------------------------------------------
    # 2. PaymentSettings (singleton row table)
    # ------------------------------------------------------------------
    op.create_table(
        "payment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("upi_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("gpay_upi_id", sa.String(120), nullable=True),
        sa.Column("phonepe_upi_id", sa.String(120), nullable=True),
        sa.Column("paytm_upi_id", sa.String(120), nullable=True),
        sa.Column("primary_upi_id", sa.String(120), nullable=True),
        sa.Column("merchant_name", sa.String(150), nullable=True),
        sa.Column("merchant_mobile", sa.String(20), nullable=True),
        sa.Column("qr_code_path", sa.String(255), nullable=True),
        sa.Column("payment_instructions", sa.Text(), nullable=True),
        sa.Column("min_withdrawal", sa.Numeric(12, 2), nullable=False, server_default="100"),
        sa.Column("max_withdrawal", sa.Numeric(12, 2), nullable=False, server_default="50000"),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False, server_default="10"),
        sa.Column("auto_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payment_timeout_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("maintenance_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.CheckConstraint("min_withdrawal >= 0", name="ck_paysettings_min_wd_nonneg"),
        sa.CheckConstraint("max_withdrawal >= 0", name="ck_paysettings_max_wd_nonneg"),
        sa.CheckConstraint("commission_percent >= 0 AND commission_percent <= 100", name="ck_paysettings_commission_range"),
    )

    # ------------------------------------------------------------------
    # 3. PaymentTransaction (replaces Payment)
    # ------------------------------------------------------------------
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("net_to_teacher", sa.Numeric(10, 2), nullable=False),
        sa.Column("transaction_id", sa.String(120), nullable=True),
        sa.Column("screenshot_path", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("pending", "verified", "rejected", "failed", "refunded", name="paymentstatus"), nullable=False, server_default="pending"),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("billing_period", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_paytxn_amount_positive"),
    )
    op.create_index("ix_payment_transactions_student_id", "payment_transactions", ["student_id"])
    op.create_index("ix_payment_transactions_teacher_id", "payment_transactions", ["teacher_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])

    # ------------------------------------------------------------------
    # 4. PaymentVerification (audit trail)
    # ------------------------------------------------------------------
    op.create_table(
        "payment_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_transaction_id", sa.Integer(), sa.ForeignKey("payment_transactions.id"), nullable=False),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_payment_verifications_payment_transaction_id", "payment_verifications", ["payment_transaction_id"])

    # ------------------------------------------------------------------
    # 5. Refund
    # ------------------------------------------------------------------
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_transaction_id", sa.Integer(), sa.ForeignKey("payment_transactions.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("status", sa.Enum("pending", "completed", name="refundstatus"), nullable=False, server_default="completed"),
        sa.Column("processed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_refund_amount_positive"),
    )
    op.create_index("ix_refunds_payment_transaction_id", "refunds", ["payment_transaction_id"])
    op.create_index("ix_refunds_status", "refunds", ["status"])

    # ------------------------------------------------------------------
    # 6. Re-insert preserved payment history into the new table
    # ------------------------------------------------------------------
    if old_rows:
        payment_transactions = sa.table(
            "payment_transactions",
            sa.column("id", sa.Integer),
            sa.column("student_id", sa.Integer),
            sa.column("teacher_id", sa.Integer),
            sa.column("amount", sa.Numeric),
            sa.column("commission_percent", sa.Numeric),
            sa.column("commission_amount", sa.Numeric),
            sa.column("net_to_teacher", sa.Numeric),
            sa.column("transaction_id", sa.String),
            sa.column("screenshot_path", sa.String),
            sa.column("status", sa.String),
            sa.column("verified_by_id", sa.Integer),
            sa.column("verified_at", sa.DateTime),
            sa.column("rejection_reason", sa.String),
            sa.column("billing_period", sa.String),
            sa.column("created_at", sa.DateTime),
            sa.column("updated_at", sa.DateTime),
        )
        for row in old_rows:
            op.execute(
                payment_transactions.insert().values(
                    id=row["id"],
                    student_id=row["student_id"],
                    teacher_id=row["teacher_id"],
                    amount=row["amount"],
                    commission_percent=row["commission_percent"],
                    commission_amount=row["commission_amount"],
                    net_to_teacher=row["net_to_teacher"],
                    transaction_id=row["utr_reference"],
                    screenshot_path=row["proof_screenshot_path"],
                    status=OLD_TO_NEW_STATUS.get(row["status"], "pending"),
                    verified_by_id=row["verified_by_id"],
                    verified_at=row["verified_at"],
                    rejection_reason=row["rejection_reason"],
                    billing_period=row["billing_period"],
                    created_at=row["created_at"],
                    updated_at=row["created_at"],
                )
            )
        if is_postgres:
            op.execute(
                "SELECT setval(pg_get_serial_sequence('payment_transactions','id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM payment_transactions))"
            )

    # ------------------------------------------------------------------
    # 7. Seed a default (singleton) payment_settings row
    # ------------------------------------------------------------------
    op.execute("INSERT INTO payment_settings (id) VALUES (1)")


def downgrade():
    op.drop_table("refunds")
    op.drop_table("payment_verifications")
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_teacher_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_student_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_table("payment_settings")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS paymentstatus")
        op.execute("DROP TYPE IF EXISTS refundstatus")

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("commission_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("net_to_teacher", sa.Numeric(10, 2), nullable=False),
        sa.Column("utr_reference", sa.String(120), nullable=True),
        sa.Column("proof_screenshot_path", sa.String(255), nullable=True),
        sa.Column("status", sa.Enum("submitted", "verified", "rejected", name="paymentstatus"), nullable=False, server_default="submitted"),
        sa.Column("verified_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("billing_period", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
    )
    op.create_index("ix_payments_student_id", "payments", ["student_id"])
    op.create_index("ix_payments_teacher_id", "payments", ["teacher_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
