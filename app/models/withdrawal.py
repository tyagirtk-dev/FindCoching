import enum
from datetime import datetime

from app import db


class WithdrawalStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class WithdrawalRequest(db.Model):
    __tablename__ = "withdrawal_requests"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)

    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.Enum(WithdrawalStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=WithdrawalStatus.REQUESTED, index=True)

    payout_method = db.Column(db.String(20), nullable=False, default="upi")  # upi or bank
    admin_note = db.Column(db.String(500), nullable=True)
    transaction_reference = db.Column(db.String(120), nullable=True)  # admin fills after manual transfer

    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
    )
