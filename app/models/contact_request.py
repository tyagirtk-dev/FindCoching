import enum
from datetime import datetime

from app import db


class ContactStatus(str, enum.Enum):
    NEW = "new"
    RESPONDED = "responded"
    CLOSED = "closed"


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(ContactStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=ContactStatus.NEW, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
