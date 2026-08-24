from datetime import datetime

from app import db


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    address = db.Column(db.String(500), nullable=False)
    state = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False, index=True)
    pincode = db.Column(db.String(12), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False, index=True)
    longitude = db.Column(db.Float, nullable=False, index=True)

    student_class = db.Column(db.String(40), nullable=False)
    subjects_required = db.Column(db.String(500), nullable=False)  # comma-separated

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="student_profile", foreign_keys=[user_id])

    __table_args__ = (
        db.Index("ix_student_lat_lng", "latitude", "longitude"),
    )

    def subjects_list(self):
        return [s.strip() for s in self.subjects_required.split(",") if s.strip()]

    def __repr__(self):
        return f"<StudentProfile user_id={self.user_id}>"
