from datetime import datetime

from app import db


class SystemSetting(db.Model):
    """
    Generic key-value settings store, editable from the Admin Panel.
    Used for SMTP config, search radius, commission %, site name, etc.
    Sensitive values (like SMTP password) are stored as-is in DB; in production
    this table should live in an encrypted-at-rest database/volume.
    """
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
