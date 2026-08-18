import enum
import random
from datetime import datetime, timedelta

from app import db


class OtpPurpose(str, enum.Enum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"


class OtpCode(db.Model):
    __tablename__ = "otp_codes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.Enum(OtpPurpose, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")

    __table_args__ = (
        db.Index("ix_otp_user_purpose", "user_id", "purpose"),
    )

    @staticmethod
    def generate_code(length=6):
        return "".join(str(random.randint(0, 9)) for _ in range(length))

    @classmethod
    def create_for_user(cls, user_id, purpose, expiry_minutes=10, length=6):
        code = cls.generate_code(length)
        otp = cls(
            user_id=user_id,
            code=code,
            purpose=purpose,
            expires_at=datetime.utcnow() + timedelta(minutes=expiry_minutes),
        )
        db.session.add(otp)
        return otp

    def is_valid(self, code):
        if self.is_used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        if self.attempts >= 5:
            return False
        return self.code == code
