from app import db


class TeacherAvailabilitySlot(db.Model):
    __tablename__ = "teacher_availability_slots"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ISO weekday: 0=Monday ... 6=Sunday
    weekday = db.Column(db.Integer, nullable=False)

    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    teacher = db.relationship(
        "TeacherProfile",
        back_populates="availability_slots",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_teacher_availability_slot",
        ),
        db.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_teacher_availability_weekday",
        ),
    )

    def __repr__(self):
        return (
            f"<TeacherAvailabilitySlot "
            f"teacher={self.teacher_id} "
            f"weekday={self.weekday} "
            f"{self.start_time}-{self.end_time}>"
        )
