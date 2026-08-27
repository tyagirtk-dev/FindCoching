import enum
from datetime import datetime

from app import db


class HireStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class HireRequest(db.Model):
    __tablename__ = "hire_requests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)

    message = db.Column(db.String(1000), nullable=True)

    # Requested actual class occurrence.
    scheduled_start = db.Column(db.DateTime, nullable=True, index=True)
    scheduled_end = db.Column(db.DateTime, nullable=True, index=True)

    # Duration requested by the student.
    class_duration_minutes = db.Column(
        db.Integer,
        nullable=True,
        default=60,
    )

    # "online" or "home".
    teaching_mode = db.Column(
        db.String(20),
        nullable=True,
    )

    # "walking", "bike", "car", or "online".
    travel_mode = db.Column(
        db.String(20),
        nullable=True,
    )
    status = db.Column(db.Enum(HireStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=HireStatus.PENDING, index=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("StudentProfile", foreign_keys=[student_id])
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])

    __table_args__ = (
        db.UniqueConstraint("student_id", "teacher_id", "status", name="uq_active_hire_per_pair"),
    )

    def __repr__(self):
        return f"<HireRequest student={self.student_id} teacher={self.teacher_id} status={self.status}>"
