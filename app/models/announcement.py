import enum
from datetime import datetime

from app import db


class AnnouncementAudience(str, enum.Enum):
    ALL = "all"
    TEACHERS = "teachers"
    STUDENTS = "students"


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.Enum(AnnouncementAudience, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=AnnouncementAudience.ALL)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_by = db.relationship("User")
