from urllib.parse import urlparse

from authlib.integrations.base_client import OAuthError
from flask import (
    render_template,
    Blueprint,
    current_app,
    flash,
    redirect,
    request,
    session,
    url_for,
)

from app import db
from app.models.oauth_account import OAuthAccount
from app.services.google_oauth import oauth
from app.services.google_auth_flow import (
    clear_google_registration,
    find_user_by_google_email,
    get_google_registration,
    link_google_account,
    save_google_registration,
)


google_auth_bp = Blueprint(
    "google_auth",
    __name__,
    url_prefix="/auth",
)


def _safe_next_url(value):
    if not value:
        return None

    parsed = urlparse(value)

    if parsed.scheme or parsed.netloc:
        return None

    if not value.startswith("/"):
        return None

    return value


@google_auth_bp.get("/google")
def google_login():
    """
    Start Google OpenID Connect login.
    """
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google login is not configured yet.", "warning")
        return redirect(url_for("auth.login"))

    redirect_uri = url_for(
        "google_auth.google_callback",
        _external=True,
    )

    return oauth.google.authorize_redirect(
        redirect_uri,
        prompt="select_account",
    )


@google_auth_bp.get("/google/callback")
def google_callback():
    """
    Verify Google's OpenID Connect response.

    Existing users are linked safely.
    New users are sent to role selection.
    """
    try:
        token = oauth.google.authorize_access_token()

        userinfo = token.get("userinfo")

        if not userinfo:
            userinfo = oauth.google.userinfo()

    except OAuthError:
        flash("Google login failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    email = (userinfo.get("email") or "").strip().lower()
    name = (userinfo.get("name") or "").strip()
    provider_user_id = userinfo.get("sub")
    email_verified = bool(userinfo.get("email_verified"))

    if not email or not provider_user_id:
        flash("Google did not provide the required account information.", "danger")
        return redirect(url_for("auth.login"))

    if not email_verified:
        flash("Your Google email must be verified.", "warning")
        return redirect(url_for("auth.login"))

    # First priority: exact Google identity.
    oauth_account = OAuthAccount.query.filter_by(
        provider="google",
        provider_user_id=provider_user_id,
    ).first()

    if oauth_account:
        from flask_login import login_user

        login_user(oauth_account.user)

        clear_google_registration()

        next_url = _safe_next_url(session.pop("google_next", None))

        if next_url:
            return redirect(next_url)

        return redirect(url_for("main.index"))

    # Second priority: existing FindCoching email.
    try:
        from app.models.user import User
    except ImportError:
        flash("User model could not be loaded.", "danger")
        return redirect(url_for("auth.login"))

    existing_user = find_user_by_google_email(User, email)

    if existing_user:
        try:
            link_google_account(
                existing_user,
                provider_user_id,
                email,
            )
        except ValueError:
            db.session.rollback()
            flash(
                "This Google account is already linked elsewhere.",
                "danger",
            )
            return redirect(url_for("auth.login"))

        from flask_login import login_user

        login_user(existing_user)

        clear_google_registration()

        next_url = _safe_next_url(session.pop("google_next", None))

        if next_url:
            return redirect(next_url)

        return redirect(url_for("main.index"))

    # New Google user.
    save_google_registration(
        {
            "provider_user_id": provider_user_id,
            "email": email,
            "name": name,
            "email_verified": email_verified,
        }
    )

    return redirect(url_for("google_auth.google_role"))


@google_auth_bp.get("/google/role")
def google_role():
    pending = get_google_registration()

    if not pending:
        flash("Google registration session expired.", "warning")
        return redirect(url_for("auth.login"))

    return render_template("auth/google_role.html")




@google_auth_bp.get("/google/continue")
def google_continue():
    role = request.args.get("role", "").strip().lower()

    if role not in {"student", "teacher"}:
        return redirect(url_for("google_auth.google_role"))

    pending = get_google_registration()

    if not pending:
        flash("Google registration session expired.", "warning")
        return redirect(url_for("auth.login"))

    session["google_registration_role"] = role

    if role == "student":
        return redirect(url_for("auth.register_student"))

    return redirect(url_for("auth.register_teacher"))
