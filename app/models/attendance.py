import enum
from datetime import datetime

from app import db


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LEAVE = "leave"


class Attendance(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)

    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.Enum(AttendanceStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=AttendanceStatus.PRESENT)
    remarks = db.Column(db.String(500), nullable=True)

    marked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])
    student = db.relationship("StudentProfile", foreign_keys=[student_id])

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "student_id", "date", name="uq_attendance_per_day"),
    )
