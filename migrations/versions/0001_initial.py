"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-22 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(180), nullable=False),
        sa.Column("mobile", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("super_admin", "teacher", "student", name="roleenum"), nullable=False),
        sa.Column("is_active_account", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("mobile"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_mobile", "users", ["mobile"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_role_active", "users", ["role", "is_active_account"])

    op.create_table(
        "teacher_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("photo_path", sa.String(255), nullable=True),
        sa.Column("aadhaar_path", sa.String(255), nullable=True),
        sa.Column("qualification_certificate_path", sa.String(255), nullable=True),
        sa.Column("experience_years", sa.Numeric(4, 1), nullable=False, server_default="0"),
        sa.Column("subjects", sa.String(500), nullable=False),
        sa.Column("classes", sa.String(255), nullable=False),
        sa.Column("teaching_mode", sa.Enum("online", "offline", "both", name="teachingmode"), nullable=False, server_default="both"),
        sa.Column("monthly_fees", sa.Numeric(10, 2), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("upi_id", sa.String(120), nullable=True),
        sa.Column("bank_account_holder", sa.String(120), nullable=True),
        sa.Column("bank_account_number", sa.String(40), nullable=True),
        sa.Column("bank_ifsc", sa.String(20), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", "suspended", name="teacherstatus"), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("average_rating", sa.Float(), server_default="0"),
        sa.Column("rating_count", sa.Integer(), server_default="0"),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id"),
        sa.CheckConstraint("monthly_fees >= 0", name="ck_teacher_fees_nonneg"),
    )
    op.create_index("ix_teacher_profiles_user_id", "teacher_profiles", ["user_id"])
    op.create_index("ix_teacher_profiles_status", "teacher_profiles", ["status"])
    op.create_index("ix_teacher_lat_lng", "teacher_profiles", ["latitude", "longitude"])

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("state", sa.String(120), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("pincode", sa.String(12), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("student_class", sa.String(40), nullable=False),
        sa.Column("subjects_required", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_student_profiles_user_id", "student_profiles", ["user_id"])
    op.create_index("ix_student_profiles_city", "student_profiles", ["city"])
    op.create_index("ix_student_profiles_pincode", "student_profiles", ["pincode"])
    op.create_index("ix_student_lat_lng", "student_profiles", ["latitude", "longitude"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("purpose", sa.Enum("email_verification", "password_reset", name="otppurpose"), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_otp_codes_user_id", "otp_codes", ["user_id"])
    op.create_index("ix_otp_user_purpose", "otp_codes", ["user_id", "purpose"])

    op.create_table(
        "hire_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("message", sa.String(1000), nullable=True),
        sa.Column("status", sa.Enum("pending", "accepted", "rejected", "cancelled", name="hirestatus"), nullable=False, server_default="pending"),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("student_id", "teacher_id", "status", name="uq_active_hire_per_pair"),
    )
    op.create_index("ix_hire_requests_student_id", "hire_requests", ["student_id"])
    op.create_index("ix_hire_requests_teacher_id", "hire_requests", ["teacher_id"])
    op.create_index("ix_hire_requests_status", "hire_requests", ["status"])

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("present", "absent", "leave", name="attendancestatus"), nullable=False, server_default="present"),
        sa.Column("remarks", sa.String(500), nullable=True),
        sa.Column("marked_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("teacher_id", "student_id", "date", name="uq_attendance_per_day"),
    )
    op.create_index("ix_attendance_records_teacher_id", "attendance_records", ["teacher_id"])
    op.create_index("ix_attendance_records_student_id", "attendance_records", ["student_id"])
    op.create_index("ix_attendance_records_date", "attendance_records", ["date"])

    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("pending_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paid_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_earned", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("teacher_id"),
        sa.CheckConstraint("pending_balance >= 0", name="ck_wallet_pending_nonneg"),
        sa.CheckConstraint("paid_balance >= 0", name="ck_wallet_paid_nonneg"),
    )
    op.create_index("ix_wallets_teacher_id", "wallets", ["teacher_id"])

    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wallet_id", sa.Integer(), sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_wallet_transactions_wallet_id", "wallet_transactions", ["wallet_id"])

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

    op.create_table(
        "withdrawal_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Enum("requested", "approved", "paid", "rejected", name="withdrawalstatus"), nullable=False, server_default="requested"),
        sa.Column("payout_method", sa.String(20), nullable=False, server_default="upi"),
        sa.Column("admin_note", sa.String(500), nullable=True),
        sa.Column("transaction_reference", sa.String(120), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("processed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
    )
    op.create_index("ix_withdrawal_requests_teacher_id", "withdrawal_requests", ["teacher_id"])
    op.create_index("ix_withdrawal_requests_status", "withdrawal_requests", ["status"])

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("link", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        sa.UniqueConstraint("student_id", "teacher_id", name="uq_review_per_pair"),
    )
    op.create_index("ix_reviews_student_id", "reviews", ["student_id"])
    op.create_index("ix_reviews_teacher_id", "reviews", ["teacher_id"])

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("open", "in_review", "resolved", "closed", name="complaintstatus"), nullable=False, server_default="open"),
        sa.Column("admin_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_complaints_student_id", "complaints", ["student_id"])
    op.create_index("ix_complaints_teacher_id", "complaints", ["teacher_id"])
    op.create_index("ix_complaints_status", "complaints", ["status"])

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_profiles.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teacher_profiles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("student_id", "teacher_id", name="uq_thread_per_pair"),
    )
    op.create_index("ix_chat_threads_student_id", "chat_threads", ["student_id"])
    op.create_index("ix_chat_threads_teacher_id", "chat_threads", ["teacher_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("chat_threads.id"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_type", sa.Enum("text", "image", "file", name="messagetype"), nullable=False, server_default="text"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index("ix_chat_messages_sender_id", "chat_messages", ["sender_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.Enum("all", "teachers", "students", name="announcementaudience"), nullable=False, server_default="all"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("new", "responded", "closed", name="contactstatus"), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contact_requests_status", "contact_requests", ["status"])


def downgrade():
    op.drop_table("contact_requests")
    op.drop_table("announcements")
    op.drop_table("audit_logs")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("complaints")
    op.drop_table("reviews")
    op.drop_table("notifications")
    op.drop_table("system_settings")
    op.drop_table("withdrawal_requests")
    op.drop_table("payments")
    op.drop_table("wallet_transactions")
    op.drop_table("wallets")
    op.drop_table("attendance_records")
    op.drop_table("hire_requests")
    op.drop_table("otp_codes")
    op.drop_table("student_profiles")
    op.drop_table("teacher_profiles")
    op.drop_table("users")
