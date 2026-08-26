import enum
from datetime import datetime

from app import db


class TeacherStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class TeachingMode(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BOTH = "both"


class TeacherProfile(db.Model):
    __tablename__ = "teacher_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    photo_path = db.Column(db.String(255), nullable=True)
    aadhaar_path = db.Column(db.String(255), nullable=True)  # ID document file, stored securely
    qualification_certificate_path = db.Column(db.String(255), nullable=True)

    experience_years = db.Column(db.Numeric(4, 1), nullable=False, default=0)
    subjects = db.Column(db.String(500), nullable=False)   # comma-separated for simplicity; see SubjectTag for filters
    classes = db.Column(db.String(255), nullable=False)    # e.g. "6,7,8,9,10"
    teaching_mode = db.Column(db.Enum(TeachingMode, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=TeachingMode.BOTH)
    monthly_fees = db.Column(db.Numeric(10, 2), nullable=False)

    address = db.Column(db.String(500), nullable=False)
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)

    upi_id = db.Column(db.String(120), nullable=True)
    bank_account_holder = db.Column(db.String(120), nullable=True)
    bank_account_number = db.Column(db.String(40), nullable=True)
    bank_ifsc = db.Column(db.String(20), nullable=True)
    bank_name = db.Column(db.String(120), nullable=True)

    status = db.Column(db.Enum(TeacherStatus, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=TeacherStatus.PENDING, index=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    average_rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)

    is_available = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="teacher_profile", foreign_keys=[user_id])
    wallet = db.relationship(
        "Wallet",
        back_populates="teacher_profile",
        uselist=False,
        cascade="all, delete-orphan",
    )

    availability_slots = db.relationship(
        "TeacherAvailabilitySlot",
        back_populates="teacher",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        db.Index("ix_teacher_lat_lng", "latitude", "longitude"),
        db.CheckConstraint("monthly_fees >= 0", name="ck_teacher_fees_nonneg"),
    )

    def subjects_list(self):
        return [s.strip() for s in self.subjects.split(",") if s.strip()]

    def classes_list(self):
        return [c.strip() for c in self.classes.split(",") if c.strip()]

    def __repr__(self):
        return f"<TeacherProfile user_id={self.user_id} status={self.status}>"
