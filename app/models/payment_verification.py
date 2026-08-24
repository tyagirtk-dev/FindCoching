from datetime import datetime

from app import db


class VerificationAction:
    APPROVED = "approved"
    REJECTED = "rejected"
    REFUNDED = "refunded"


class PaymentVerification(db.Model):
    """
    Audit trail: one row per admin action (approve/reject/refund) taken on a
    PaymentTransaction. A transaction can have more than one row over its
    lifetime (e.g. approved, then later refunded).
    """
    __tablename__ = "payment_verifications"

    id = db.Column(db.Integer, primary_key=True)
    payment_transaction_id = db.Column(db.Integer, db.ForeignKey("payment_transactions.id"), nullable=False, index=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    action = db.Column(db.String(20), nullable=False)  # approved / rejected / refunded
    notes = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    payment_transaction = db.relationship("PaymentTransaction", back_populates="verifications")
    admin = db.relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<PaymentVerification txn={self.payment_transaction_id} action={self.action}>"
