from flask import current_app

from app import db
from app.models.otp import OtpCode, OtpPurpose
from app.services.email_service import send_otp_email

PURPOSE_LABELS = {
    OtpPurpose.EMAIL_VERIFICATION: "Email Verification",
    OtpPurpose.PASSWORD_RESET: "Password Reset",
}


def issue_otp(user, purpose: OtpPurpose):
    expiry_minutes = current_app.config["OTP_EXPIRY_MINUTES"]
    length = current_app.config["OTP_LENGTH"]

    # Invalidate previous unused OTPs of the same purpose
    OtpCode.query.filter_by(user_id=user.id, purpose=purpose, is_used=False).update({"is_used": True})

    otp = OtpCode.create_for_user(user.id, purpose, expiry_minutes=expiry_minutes, length=length)
    db.session.commit()

    send_otp_email(
        to_email=user.email,
        name=user.name,
        code=otp.code,
        purpose_label=PURPOSE_LABELS.get(purpose, "Verification"),
        expiry_minutes=expiry_minutes,
    )
    return otp


def verify_otp(user, purpose: OtpPurpose, code: str) -> bool:
    otp = (
        OtpCode.query.filter_by(user_id=user.id, purpose=purpose, is_used=False)
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if not otp:
        return False

    otp.attempts += 1
    if otp.is_valid(code):
        otp.is_used = True
        db.session.commit()
        return True

    db.session.commit()
    return False
