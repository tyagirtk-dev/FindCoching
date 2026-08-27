import enum
from datetime import datetime

from app import db


class ClassSessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    TRAVELLING = "travelling"
    ARRIVED = "arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"


class TravelMode(str, enum.Enum):
    WALKING = "walking"
    BIKE = "bike"
    CAR = "car"
    ONLINE = "online"


class SessionTeachingMode(str, enum.Enum):
    ONLINE = "online"
    HOME = "home"


class SessionAttendanceStatus(str, enum.Enum):
    PENDING = "pending"
    PRESENT = "present"
    ABSENT = "absent"


class ClassSession(db.Model):
    """
    A single scheduled tuition session.

    This is intentionally separate from HireRequest:
    HireRequest = relationship/request to hire a teacher.
    ClassSession = an actual scheduled class occurrence.
    """

    __tablename__ = "class_sessions"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    hire_request_id = db.Column(
        db.Integer,
        db.ForeignKey("hire_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    scheduled_start = db.Column(db.DateTime, nullable=False, index=True)
    scheduled_end = db.Column(db.DateTime, nullable=False)

    actual_started_at = db.Column(db.DateTime, nullable=True)
    actual_completed_at = db.Column(db.DateTime, nullable=True)

    teaching_mode = db.Column(
        db.Enum(
            SessionTeachingMode,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )

    travel_mode = db.Column(
        db.Enum(
            TravelMode,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=TravelMode.ONLINE,
    )

    status = db.Column(
        db.Enum(
            ClassSessionStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ClassSessionStatus.SCHEDULED,
        index=True,
    )

    attendance_status = db.Column(
        db.Enum(
            SessionAttendanceStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=SessionAttendanceStatus.PENDING,
    )

    # Route snapshot at booking time.
    origin_latitude = db.Column(db.Float, nullable=True)
    origin_longitude = db.Column(db.Float, nullable=True)

    destination_latitude = db.Column(db.Float, nullable=True)
    destination_longitude = db.Column(db.Float, nullable=True)

    distance_km = db.Column(db.Float, nullable=True)
    estimated_travel_minutes = db.Column(db.Integer, nullable=True)
    travel_buffer_minutes = db.Column(db.Integer, nullable=False, default=10)

    # Live teacher location during active travel.
    current_teacher_latitude = db.Column(db.Float, nullable=True)
    current_teacher_longitude = db.Column(db.Float, nullable=True)
    location_updated_at = db.Column(db.DateTime, nullable=True)

    teacher_started_travel_at = db.Column(db.DateTime, nullable=True)
    teacher_arrived_at = db.Column(db.DateTime, nullable=True)

    # Server-authoritative session timing.
    timer_started_at = db.Column(db.DateTime, nullable=True)
    timer_duration_seconds = db.Column(db.Integer, nullable=False, default=3600)

    notes = db.Column(db.String(1000), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    teacher = db.relationship(
        "TeacherProfile",
        foreign_keys=[teacher_id],
        backref=db.backref("class_sessions", lazy="dynamic"),
    )

    student = db.relationship(
        "StudentProfile",
        foreign_keys=[student_id],
        backref=db.backref("class_sessions", lazy="dynamic"),
    )

    hire_request = db.relationship(
        "HireRequest",
        foreign_keys=[hire_request_id],
    )

    __table_args__ = (
        db.Index(
            "ix_class_session_teacher_schedule",
            "teacher_id",
            "scheduled_start",
            "scheduled_end",
        ),
        db.Index(
            "ix_class_session_student_schedule",
            "student_id",
            "scheduled_start",
            "scheduled_end",
        ),
        db.CheckConstraint(
            "scheduled_end > scheduled_start",
            name="ck_class_session_valid_schedule",
        ),
        db.CheckConstraint(
            "timer_duration_seconds > 0",
            name="ck_class_session_positive_timer",
        ),
        db.CheckConstraint(
            "travel_buffer_minutes >= 0",
            name="ck_class_session_nonnegative_buffer",
        ),
    )

    @property
    def duration_seconds(self):
        """Actual elapsed session duration, calculated server-side."""
        if not self.timer_started_at:
            return 0

        end = self.actual_completed_at or datetime.utcnow()
        elapsed = int((end - self.timer_started_at).total_seconds())

        return max(0, min(elapsed, self.timer_duration_seconds))

    @property
    def remaining_seconds(self):
        """Never exceeds the configured session duration."""
        return max(0, self.timer_duration_seconds - self.duration_seconds)

    @property
    def is_timer_finished(self):
        return bool(
            self.timer_started_at
            and self.duration_seconds >= self.timer_duration_seconds
        )

    def __repr__(self):
        return (
            f"<ClassSession teacher={self.teacher_id} "
            f"student={self.student_id} "
            f"date={self.scheduled_date} "
            f"status={self.status}>"
        )
