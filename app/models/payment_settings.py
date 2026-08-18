from datetime import datetime

from app import db


class PaymentSettings(db.Model):
    """
    Singleton table (always exactly one row, id=1) holding admin-editable
    payment configuration: UPI details, QR code, withdrawal limits, commission,
    auto-approval, timeout, and maintenance mode.

    Use PaymentSettings.get_solo() to fetch (creating the default row if needed).
    """
    __tablename__ = "payment_settings"

    id = db.Column(db.Integer, primary_key=True)

    upi_enabled = db.Column(db.Boolean, nullable=False, default=True)

    gpay_upi_id = db.Column(db.String(120), nullable=True)
    phonepe_upi_id = db.Column(db.String(120), nullable=True)
    paytm_upi_id = db.Column(db.String(120), nullable=True)
    primary_upi_id = db.Column(db.String(120), nullable=True)

    merchant_name = db.Column(db.String(150), nullable=True)
    merchant_mobile = db.Column(db.String(20), nullable=True)

    qr_code_path = db.Column(db.String(255), nullable=True)
    payment_instructions = db.Column(db.Text, nullable=True)

    min_withdrawal = db.Column(db.Numeric(12, 2), nullable=False, default=100)
    max_withdrawal = db.Column(db.Numeric(12, 2), nullable=False, default=50000)

    commission_percent = db.Column(db.Numeric(5, 2), nullable=False, default=10)

    auto_approval = db.Column(db.Boolean, nullable=False, default=False)
    payment_timeout_minutes = db.Column(db.Integer, nullable=False, default=30)

    maintenance_mode = db.Column(db.Boolean, nullable=False, default=False)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        db.CheckConstraint("min_withdrawal >= 0", name="ck_paysettings_min_wd_nonneg"),
        db.CheckConstraint("max_withdrawal >= 0", name="ck_paysettings_max_wd_nonneg"),
        db.CheckConstraint("commission_percent >= 0 AND commission_percent <= 100", name="ck_paysettings_commission_range"),
    )

    @classmethod
    def get_solo(cls):
        """Fetch the single settings row, creating it with defaults on first use."""
        settings = cls.query.get(1)
        if settings is None:
            settings = cls(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings

    def __repr__(self):
        return f"<PaymentSettings maintenance={self.maintenance_mode} auto_approval={self.auto_approval}>"
