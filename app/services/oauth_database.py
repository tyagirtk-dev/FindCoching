from app import db
from app.models.oauth_account import OAuthAccount


def ensure_oauth_database():
    """
    Creates ONLY the OAuthAccount table if it does not exist.

    Existing FindCoching tables are not altered.
    """
    db.create_all()
