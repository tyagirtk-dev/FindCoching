import enum
from datetime import datetime

import bcrypt
from flask_login import UserMixin

from app import db


class RoleEnum(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    TEACHER = "teacher"
    STUDENT = "student"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    mobile = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)

    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_email_verified = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # Referral system
    referral_code = db.Column(
        db.String(32),
        unique=True,
        nullable=True,
        index=True,
    )

    referred_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    referred_by = db.relationship(
        "User",
        remote_side=[id],
        foreign_keys=[referred_by_user_id],
        backref=db.backref("referrals", lazy="dynamic"),
    )

    teacher_profile = db.relationship(
        "TeacherProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="TeacherProfile.user_id",
    )
    student_profile = db.relationship(
        "StudentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index("ix_users_role_active", "role", "is_active_account"),
    )

    # --- password helpers -------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(raw_password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        try:
            return bcrypt.checkpw(raw_password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except (ValueError, AttributeError):
            return False

    # --- Flask-Login required overrides -----------------------------------
    def get_id(self):
        return str(self.id)

    @property
    def is_active(self):
        # Flask-Login uses this to block login for disabled/unapproved accounts
        if self.role == RoleEnum.TEACHER and self.teacher_profile:
            from app.models.teacher_profile import TeacherStatus
            if self.teacher_profile.status != TeacherStatus.APPROVED:
                return False
        return self.is_active_account

    # --- role helpers -------------------------------------------------------
    @property
    def is_super_admin(self):
        return self.role == RoleEnum.SUPER_ADMIN

    @property
    def is_teacher(self):
        return self.role == RoleEnum.TEACHER

    @property
    def is_student(self):
        return self.role == RoleEnum.STUDENT

    def __repr__(self):
        return f"<User {self.id} {self.email} {self.role}>"
