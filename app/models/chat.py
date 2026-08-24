import enum
from datetime import datetime

from app import db


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"


class ChatThread(db.Model):
    __tablename__ = "chat_threads"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profiles.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher_profiles.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship("StudentProfile", foreign_keys=[student_id])
    teacher = db.relationship("TeacherProfile", foreign_keys=[teacher_id])
    messages = db.relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan",
                                order_by="ChatMessage.created_at")

    __table_args__ = (
        db.UniqueConstraint("student_id", "teacher_id", name="uq_thread_per_pair"),
    )


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("chat_threads.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    message_type = db.Column(db.Enum(MessageType, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=MessageType.TEXT)
    body = db.Column(db.Text, nullable=True)         # text content or emoji
    file_path = db.Column(db.String(255), nullable=True)  # for image/file messages

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    thread = db.relationship("ChatThread", back_populates="messages")
    sender = db.relationship("User")
