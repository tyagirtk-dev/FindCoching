from datetime import datetime

from app import db


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), unique=True, nullable=False, index=True)

    pending_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    paid_balance = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_earned = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    teacher_profile = db.relationship("TeacherProfile", back_populates="wallet")
    transactions = db.relationship("WalletTransaction", back_populates="wallet", cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint("pending_balance >= 0", name="ck_wallet_pending_nonneg"),
        db.CheckConstraint("paid_balance >= 0", name="ck_wallet_paid_nonneg"),
    )


class WalletTransactionType:
    CREDIT = "credit"        # payment verified, added to pending
    WITHDRAWAL = "withdrawal"  # moved from pending to paid via withdrawal
    ADJUSTMENT = "adjustment"


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transactions"

    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey("wallets.id"), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    reference = db.Column(db.String(255), nullable=True)  # e.g. payment id / withdrawal id
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    wallet = db.relationship("Wallet", back_populates="transactions")
