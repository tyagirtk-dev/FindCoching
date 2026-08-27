from secrets import token_urlsafe

from flask import session

from app import db
from app.models.oauth_account import OAuthAccount


GOOGLE_PENDING_SESSION_KEY = "_google_pending_registration"


def save_google_registration(data):
    """
    Store only temporary, non-sensitive Google profile information
    in the user's signed Flask session.

    Never store Google access/refresh tokens here.
    """
    session[GOOGLE_PENDING_SESSION_KEY] = {
        "provider": "google",
        "provider_user_id": data.get("provider_user_id"),
        "email": data.get("email"),
        "name": data.get("name"),
        "email_verified": bool(data.get("email_verified")),
        "nonce": token_urlsafe(32),
    }
    session.modified = True


def get_google_registration():
    return session.get(GOOGLE_PENDING_SESSION_KEY)


def clear_google_registration():
    session.pop(GOOGLE_PENDING_SESSION_KEY, None)


def find_google_account(provider_user_id):
    return OAuthAccount.query.filter_by(
        provider="google",
        provider_user_id=provider_user_id,
    ).first()


def find_user_by_google_email(User, email):
    if not email:
        return None

    return User.query.filter_by(email=email.lower().strip()).first()


def link_google_account(user, provider_user_id, email):
    existing = find_google_account(provider_user_id)

    if existing:
        if existing.user_id != user.id:
            raise ValueError("Google account is already linked to another user")
        return existing

    existing_for_user = OAuthAccount.query.filter_by(
        user_id=user.id,
        provider="google",
    ).first()

    if existing_for_user:
        if existing_for_user.provider_user_id != provider_user_id:
            raise ValueError(
                "This FindCoching account already has a different Google account linked"
            )
        return existing_for_user

    account = OAuthAccount(
        user_id=user.id,
        provider="google",
        provider_user_id=provider_user_id,
        provider_email=email,
    )

    db.session.add(account)
    db.session.commit()

    return account
