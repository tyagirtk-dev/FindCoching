from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from app import db
from app.models.notification import Notification

api_bp = Blueprint("api", __name__)


@api_bp.route("/notifications/unread-count")
@login_required
def unread_notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"count": count})


@api_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({"status": "ok"})
