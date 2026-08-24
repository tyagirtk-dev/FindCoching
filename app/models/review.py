from datetime import datetime

from app import db


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)

    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.String(1000), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("StudentProfile", foreign_keys=[student_id])
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        db.UniqueConstraint("student_id", "teacher_id", name="uq_review_per_pair"),
    )
