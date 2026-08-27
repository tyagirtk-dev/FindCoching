from datetime import datetime, timezone

from app import db


class OAuthAccount(db.Model):
    """
    External OAuth identity linked to an existing FindCoching User.

    One FindCoching user may have one or more external login identities.
    Existing User/password authentication remains untouched.
    """

    __tablename__ = "oauth_accounts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider = db.Column(
        db.String(32),
        nullable=False,
    )

    provider_user_id = db.Column(
        db.String(255),
        nullable=False,
    )

    provider_email = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "oauth_accounts",
            lazy="dynamic",
            cascade="all, delete-orphan",
        ),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_oauth_provider_subject",
        ),
        db.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_user_oauth_provider",
        ),
    )

    def __repr__(self):
        return (
            f"<OAuthAccount "
            f"id={self.id} "
            f"provider={self.provider!r} "
            f"user_id={self.user_id}>"
        )
