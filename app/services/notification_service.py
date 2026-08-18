from app import db
from app.models.notification import Notification


def notify(user_id, title, message, link=None):
    n = Notification(user_id=user_id, title=title, message=message, link=link)
    db.session.add(n)
    return n


def notify_many(user_ids, title, message, link=None):
    for uid in user_ids:
        notify(uid, title, message, link)
