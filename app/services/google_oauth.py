from authlib.integrations.flask_client import OAuth

oauth = OAuth()


def init_google_oauth(app):
    """
    Initialize Google OAuth.

    Credentials are read from Flask configuration.
    No client secret is stored in source code.
    """

    client_id = app.config.get("GOOGLE_CLIENT_ID")
    client_secret = app.config.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        return False

    oauth.init_app(app)

    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=(
            "https://accounts.google.com/.well-known/"
            "openid-configuration"
        ),
        client_kwargs={
            "scope": "openid email profile",
        },
    )

    return True
