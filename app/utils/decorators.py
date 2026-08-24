from functools import wraps

from flask import abort
from flask_login import current_user

from app.models.user import RoleEnum


def roles_required(*roles):
    """Restrict a view to one or more RoleEnum values. Must be used after @login_required."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(403)
            if current_user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


def super_admin_required(view_func):
    return roles_required(RoleEnum.SUPER_ADMIN)(view_func)


def teacher_required(view_func):
    return roles_required(RoleEnum.TEACHER)(view_func)


def student_required(view_func):
    return roles_required(RoleEnum.STUDENT)(view_func)
