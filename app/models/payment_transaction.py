import enum
from datetime import datetime

from app import db


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"      # student submitted, awaiting admin action
    VERIFIED = "verified"    # admin confirmed, wallet credited
    REJECTED = "rejected"    # admin rejected
    FAILED = "failed"        # payment failed / timed out before verification
    REFUNDED = "refunded"    # previously verified, later refunded


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    commission_percent = db.Column(db.Numeric(5, 2), nullable=False)
    commission_amount = db.Column(db.Numeric(10, 2), nullable=False)
    net_to_teacher = db.Column(db.Numeric(10, 2), nullable=False)

    transaction_id = db.Column(db.String(120), nullable=True)  # UPI transaction ref / UTR student enters
    screenshot_path = db.Column(db.String(255), nullable=True)

    status = db.Column(
        db.Enum(PaymentStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=PaymentStatus.PENDING, index=True,
    )
    verified_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)

    billing_period = db.Column(db.String(20), nullable=True)  # e.g. "2026-07"

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("StudentProfile", foreign_keys=[student_id])
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])
    verifications = db.relationship(
        "PaymentVerification", back_populates="payment_transaction",
        cascade="all, delete-orphan", order_by="PaymentVerification.created_at",
    )
    refunds = db.relationship(
        "Refund", back_populates="payment_transaction", cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_paytxn_amount_positive"),
    )

    def __repr__(self):
        return f"<PaymentTransaction id={self.id} status={self.status}>"
