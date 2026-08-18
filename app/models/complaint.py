import enum
from datetime import datetime

from app import db


class ComplaintStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=True, index=True)

    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(ComplaintStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=ComplaintStatus.OPEN, index=True)
    admin_response = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("StudentProfile", foreign_keys=[student_id])
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])
