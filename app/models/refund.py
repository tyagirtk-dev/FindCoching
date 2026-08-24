import enum
from datetime import datetime

from app import db


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class Refund(db.Model):
    __tablename__ = "refunds"

    id = db.Column(db.Integer, primary_key=True)
    payment_transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transactions.id"), nullable=False, index=True)

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    status = db.Column(
        db.Enum(RefundStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=RefundStatus.COMPLETED, index=True,
    )

    processed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    payment_transaction = db.relationship("PaymentTransaction", back_populates="refunds")
    processed_by = db.relationship("User", foreign_keys=[processed_by_id])

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_refund_amount_positive"),
    )

    def __repr__(self):
        return f"<Refund txn={self.payment_transaction_id} amount={self.amount}>"
