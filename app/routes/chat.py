import time

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user

from app import db
from app.models.chat import ChatThread, ChatMessage, MessageType
from app.models.hire_request import HireRequest, HireStatus
from app.models.teacher_profile import TeacherProfile
from app.services.notification_service import notify
from app.utils.file_upload import save_upload, InvalidFileError

chat_bp = Blueprint("chat", __name__, template_folder="../templates/chat")

# Ephemeral in-memory typing-indicator state: { thread_id: {user_id: last_typed_ts} }
# Not persisted to DB by design -- it is a transient UI signal, not durable data.
_typing_state = {}
TYPING_TIMEOUT_SECONDS = 4


def _get_thread_or_404(thread_id):
    thread = ChatThread.query.get_or_404(thread_id)
    if current_user.is_student:
        if not current_user.student_profile or thread.student_id != current_user.student_profile.id:
            abort(403)
    elif current_user.is_teacher:
        if not current_user.teacher_profile or thread.teacher_id != current_user.teacher_profile.id:
            abort(403)
    else:
        abort(403)
    return thread


@chat_bp.route("/")
@login_required
def inbox():
    if current_user.is_student:
        profile = current_user.student_profile
        threads = ChatThread.query.filter_by(student_id=profile.id).order_by(ChatThread.last_message_at.desc()).all() if profile else []
    elif current_user.is_teacher:
        profile = current_user.teacher_profile
        threads = ChatThread.query.filter_by(teacher_id=profile.id).order_by(ChatThread.last_message_at.desc()).all() if profile else []
    else:
        abort(403)

    unread_by_thread = {}
    for t in threads:
        unread_by_thread[t.id] = ChatMessage.query.filter(
            ChatMessage.thread_id == t.id,
            ChatMessage.sender_id != current_user.id,
            ChatMessage.is_read.is_(False),
        ).count()

    return render_template("chat/inbox.html", threads=threads, unread_by_thread=unread_by_thread)


@chat_bp.route("/start/<int:teacher_id>")
@login_required
def start_thread(teacher_id):
    if not current_user.is_student:
        abort(403)
    profile = current_user.student_profile
    teacher = TeacherProfile.query.get_or_404(teacher_id)

    was_hired = HireRequest.query.filter_by(
        student_id=profile.id, teacher_id=teacher.id, status=HireStatus.ACCEPTED
    ).first()
    if not was_hired:
        flash("You can only chat with teachers you have hired.", "danger")
        return redirect(url_for("student.my_hires"))

    thread = ChatThread.query.filter_by(student_id=profile.id, teacher_id=teacher.id).first()
    if not thread:
        thread = ChatThread(student_id=profile.id, teacher_id=teacher.id)
        db.session.add(thread)
        db.session.commit()

    return redirect(url_for("chat.view_thread", thread_id=thread.id))


@chat_bp.route("/<int:thread_id>")
@login_required
def view_thread(thread_id):
    thread = _get_thread_or_404(thread_id)
    messages = ChatMessage.query.filter_by(thread_id=thread.id).order_by(ChatMessage.created_at.asc()).all()

    unread = [m for m in messages if m.sender_id != current_user.id and not m.is_read]
    for m in unread:
        m.is_read = True
        from datetime import datetime
        m.read_at = datetime.utcnow()
    if unread:
        db.session.commit()

    other_name = thread.teacher.user.name if current_user.is_student else thread.student.user.name
    return render_template("chat/thread.html", thread=thread, messages=messages, other_name=other_name)


@chat_bp.route("/<int:thread_id>/messages")
@login_required
def poll_messages(thread_id):
    thread = _get_thread_or_404(thread_id)
    after_id = request.args.get("after_id", 0, type=int)
    messages = ChatMessage.query.filter(
        ChatMessage.thread_id == thread.id, ChatMessage.id > after_id
    ).order_by(ChatMessage.created_at.asc()).all()

    unread = [m for m in messages if m.sender_id != current_user.id and not m.is_read]
    for m in unread:
        m.is_read = True
        from datetime import datetime
        m.read_at = datetime.utcnow()
    if unread:
        db.session.commit()

    typing_users = _typing_state.get(thread.id, {})
    now = time.time()
    other_typing = any(
        uid != current_user.id and (now - ts) < TYPING_TIMEOUT_SECONDS
        for uid, ts in typing_users.items()
    )

    return jsonify({
        "messages": [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                "is_mine": m.sender_id == current_user.id,
                "type": m.message_type.value,
                "body": m.body,
                "file_url": url_for("static", filename="uploads/" + m.file_path) if m.file_path else None,
                "is_read": m.is_read,
                "created_at": m.created_at.strftime("%H:%M"),
            }
            for m in messages
        ],
        "other_typing": other_typing,
    })


@chat_bp.route("/<int:thread_id>/send", methods=["POST"])
@login_required
def send_message(thread_id):
    thread = _get_thread_or_404(thread_id)

    body = request.form.get("body", "").strip()
    file_storage = request.files.get("file")

    if not body and not file_storage:
        return jsonify({"error": "Message cannot be empty."}), 400

    message_type = MessageType.TEXT
    file_path = None

    if file_storage and file_storage.filename:
        ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
        try:
            if ext in {"png", "jpg", "jpeg", "webp"}:
                file_path = save_upload(file_storage, "chat", {"png", "jpg", "jpeg", "webp"})
                message_type = MessageType.IMAGE
            else:
                file_path = save_upload(file_storage, "chat", {"pdf", "doc", "docx", "png", "jpg", "jpeg"})
                message_type = MessageType.FILE
        except InvalidFileError as e:
            return jsonify({"error": str(e)}), 400

    msg = ChatMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        message_type=message_type,
        body=body or None,
        file_path=file_path,
    )
    db.session.add(msg)

    from datetime import datetime
    thread.last_message_at = datetime.utcnow()

    recipient_id = thread.teacher.user_id if current_user.id == thread.student.user_id else thread.student.user_id
    notify(recipient_id, "New Message", f"{current_user.name} sent you a message.",
           link=url_for("chat.view_thread", thread_id=thread.id))

    db.session.commit()

    _typing_state.get(thread.id, {}).pop(current_user.id, None)

    return jsonify({"status": "sent", "message_id": msg.id})


@chat_bp.route("/<int:thread_id>/typing", methods=["POST"])
@login_required
def typing(thread_id):
    thread = _get_thread_or_404(thread_id)
    _typing_state.setdefault(thread.id, {})[current_user.id] = time.time()
    return jsonify({"status": "ok"})


@chat_bp.route("/<int:thread_id>/search")
@login_required
def search_messages(thread_id):
    thread = _get_thread_or_404(thread_id)
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    matches = ChatMessage.query.filter(
        ChatMessage.thread_id == thread.id,
        ChatMessage.body.ilike(f"%{q}%"),
    ).order_by(ChatMessage.created_at.asc()).all()

    return jsonify({
        "results": [
            {"id": m.id, "body": m.body, "created_at": m.created_at.strftime("%d %b %Y %H:%M")}
            for m in matches
        ]
    })
