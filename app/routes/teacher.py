from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy.orm import joinedload
from flask_login import login_required, current_user

from app import db
from app.models.class_session import (
    ClassSession,
    ClassSessionStatus,
)
from app.utils.decorators import teacher_required
from app.models.hire_request import HireRequest, HireStatus
from app.models.student_profile import StudentProfile
from app.models.attendance import Attendance
from app.models.wallet import WalletTransaction
from app.models.withdrawal import WithdrawalRequest
from app.models.review import Review
from app.models.notification import Notification
from app.forms.marketplace_forms import AttendanceForm, WithdrawalRequestForm
from app.services.notification_service import notify

teacher_bp = Blueprint("teacher", __name__, template_folder="../templates/teacher")


@teacher_bp.route("/dashboard")
@login_required
@teacher_required
def dashboard():
    profile = current_user.teacher_profile
    pending_requests = (
        HireRequest.query.filter_by(teacher_id=profile.id, status=HireStatus.PENDING).count()
        if profile else 0
    )
    active_students = (
        HireRequest.query.filter_by(teacher_id=profile.id, status=HireStatus.ACCEPTED).count()
        if profile else 0
    )
    wallet = profile.wallet if profile else None
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template(
        "teacher/dashboard.html",
        profile=profile,
        pending_requests=pending_requests,
        active_students=active_students,
        wallet=wallet,
        unread_count=unread_count,
    )


@teacher_bp.route("/profile")
@login_required
@teacher_required
def profile():
    return render_template("teacher/profile.html", profile=current_user.teacher_profile)


# --------------------------------------------------------------------------
# Hire request management
# --------------------------------------------------------------------------
@teacher_bp.route("/hires")
@login_required
@teacher_required
def hire_requests():
    profile = current_user.teacher_profile
    pending = HireRequest.query.options(joinedload(HireRequest.student).joinedload(StudentProfile.user)).filter_by(teacher_id=profile.id, status=HireStatus.PENDING).order_by(HireRequest.created_at.desc()).all()
    history = HireRequest.query.options(joinedload(HireRequest.student).joinedload(StudentProfile.user)).filter(
        HireRequest.teacher_id == profile.id, HireRequest.status != HireStatus.PENDING
    ).order_by(HireRequest.updated_at.desc()).limit(30).all()
    return render_template("teacher/hire_requests.html", pending=pending, history=history)


@teacher_bp.route("/hires/<int:hire_id>/accept", methods=["POST"])
@login_required
@teacher_required
def accept_hire(hire_id):
    profile = current_user.teacher_profile
    hire = HireRequest.query.filter_by(
        id=hire_id,
        teacher_id=profile.id,
        status=HireStatus.PENDING,
    ).first_or_404()

    hire.status = HireStatus.ACCEPTED
    hire.responded_at = datetime.utcnow()
    db.session.commit()

    notify(hire.student.user_id, "Hire Request Accepted", f"{current_user.name} accepted your hire request.",
           link=url_for("student.my_hires"))
    db.session.commit()

    flash("Hire request accepted.", "success")
    return redirect(url_for("teacher.hire_requests"))


@teacher_bp.route("/hires/<int:hire_id>/reject", methods=["POST"])
@login_required
@teacher_required
def reject_hire(hire_id):
    profile = current_user.teacher_profile
    hire = HireRequest.query.filter_by(
        id=hire_id,
        teacher_id=profile.id,
        status=HireStatus.PENDING,
    ).first_or_404()

    hire.status = HireStatus.REJECTED
    hire.responded_at = datetime.utcnow()
    db.session.commit()

    notify(hire.student.user_id, "Hire Request Declined", f"{current_user.name} declined your hire request.",
           link=url_for("student.my_hires"))
    db.session.commit()

    flash("Hire request rejected.", "info")
    return redirect(url_for("teacher.hire_requests"))


@teacher_bp.route("/students")
@login_required
@teacher_required
def my_students():
    profile = current_user.teacher_profile
    hires = HireRequest.query.options(joinedload(HireRequest.student).joinedload(StudentProfile.user)).filter_by(teacher_id=profile.id, status=HireStatus.ACCEPTED).order_by(HireRequest.responded_at.desc()).all()
    return render_template("teacher/my_students.html", hires=hires)


# --------------------------------------------------------------------------
# Attendance
# --------------------------------------------------------------------------
@teacher_bp.route("/attendance", methods=["GET", "POST"])
@login_required
@teacher_required
def mark_attendance():
    profile = current_user.teacher_profile
    active_hires = HireRequest.query.filter_by(teacher_id=profile.id, status=HireStatus.ACCEPTED).all()
    student_choices = [(h.student.id, h.student.user.name) for h in active_hires]

    form = AttendanceForm()
    form.student_id.choices = student_choices

    if form.validate_on_submit():
        existing = Attendance.query.filter_by(
            teacher_id=profile.id, student_id=form.student_id.data, date=form.date.data
        ).first()
        if existing:
            existing.status = form.status.data
            existing.remarks = form.remarks.data
        else:
            db.session.add(Attendance(
                teacher_id=profile.id,
                student_id=form.student_id.data,
                date=form.date.data,
                status=form.status.data,
                remarks=form.remarks.data,
            ))
        db.session.commit()
        flash("Attendance recorded.", "success")
        return redirect(url_for("teacher.mark_attendance"))

    records = (
        Attendance.query.options(joinedload(Attendance.student).joinedload(StudentProfile.user))
        .filter_by(teacher_id=profile.id)
        .order_by(Attendance.date.desc()).limit(50).all()
    )
    return render_template("teacher/attendance.html", form=form, records=records, has_students=bool(student_choices))


# --------------------------------------------------------------------------
# Wallet & Withdrawals
# --------------------------------------------------------------------------
@teacher_bp.route("/wallet")
@login_required
@teacher_required
def wallet():
    profile = current_user.teacher_profile
    w = profile.wallet
    transactions = (
        WalletTransaction.query.filter_by(wallet_id=w.id).order_by(WalletTransaction.created_at.desc()).limit(50).all()
        if w else []
    )
    withdrawals = WithdrawalRequest.query.filter_by(teacher_id=profile.id).order_by(WithdrawalRequest.requested_at.desc()).all()
    return render_template("teacher/wallet.html", wallet=w, transactions=transactions, withdrawals=withdrawals)


@teacher_bp.route("/withdraw", methods=["GET", "POST"])
@login_required
@teacher_required
def request_withdrawal():
    profile = current_user.teacher_profile
    w = profile.wallet

    form = WithdrawalRequestForm()
    if form.validate_on_submit():
        if not w or form.amount.data > w.pending_balance:
            flash("Withdrawal amount exceeds your available pending balance.", "danger")
            return redirect(url_for("teacher.request_withdrawal"))

        method = (form.payout_method.data or "").strip().lower()

        db.session.add(WithdrawalRequest(
            teacher_id=profile.id,
            amount=form.amount.data,
            payout_method=method,
            account_holder_name=(form.account_holder_name.data or "").strip() or None,
            upi_id=(form.upi_id.data or "").strip() or None,
            bank_account_number=(form.bank_account_number.data or "").strip() or None,
            ifsc_code=(form.ifsc_code.data or "").strip().upper() or None,
        ))
        db.session.commit()
        flash("Withdrawal request submitted for admin review.", "success")
        return redirect(url_for("teacher.wallet"))

    return render_template("teacher/withdraw.html", form=form, wallet=w)


# --------------------------------------------------------------------------
# Reviews received
# --------------------------------------------------------------------------
@teacher_bp.route("/reviews")
@login_required
@teacher_required
def reviews():
    profile = current_user.teacher_profile
    items = Review.query.options(joinedload(Review.student).joinedload(StudentProfile.user)).filter_by(teacher_id=profile.id).order_by(Review.created_at.desc()).all()
    return render_template("teacher/reviews.html", items=items, profile=profile)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@teacher_bp.route("/notifications")
@login_required
@teacher_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("teacher/notifications.html", items=items)


# ============================================================
# CLASS SESSION CONTROL / LIVE TRAVEL
# ============================================================

def _teacher_owned_session(session_id):
    """
    Security boundary: a teacher may control only their own session.
    """
    profile = current_user.teacher_profile

    return ClassSession.query.filter_by(
        id=session_id,
        teacher_id=profile.id,
    ).first_or_404()


def _auto_complete_expired_session(session):
    """
    Server-authoritative timer enforcement.

    If an IN_PROGRESS session has reached its configured duration,
    automatically mark it COMPLETED. Client-side timers are never trusted.
    """
    if session.status != ClassSessionStatus.IN_PROGRESS:
        return False

    if not session.timer_started_at:
        return False

    if not session.is_timer_finished:
        return False

    now = datetime.utcnow()

    session.status = ClassSessionStatus.COMPLETED

    if session.actual_completed_at is None:
        session.actual_completed_at = now

    db.session.commit()
    return True


@teacher_bp.route("/sessions/<int:session_id>/start-travel", methods=["POST"])
@login_required
@teacher_required
def teacher_start_travel(session_id):
    """
    scheduled -> travelling

    Starts server-side travel tracking for the teacher.
    """
    session = _teacher_owned_session(session_id)

    if session.status != ClassSessionStatus.SCHEDULED:
        return {
            "error": "Session must be scheduled before travel can start.",
            "status": session.status.value,
        }, 409

    now = datetime.utcnow()

    session.status = ClassSessionStatus.TRAVELLING
    session.teacher_started_travel_at = now

    db.session.commit()

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "teacher_started_travel_at": now.isoformat(),
    }, 200


@teacher_bp.route("/sessions/<int:session_id>/location", methods=["POST"])
@login_required
@teacher_required
def teacher_update_session_location(session_id):
    """
    Update the teacher's live location for an active travelling session.
    """
    session = _teacher_owned_session(session_id)

    if session.status not in (
        ClassSessionStatus.TRAVELLING,
        ClassSessionStatus.ARRIVED,
    ):
        return {
            "error": "Location can only be updated while travelling or arrived.",
            "status": session.status.value,
        }, 409

    payload = request.get_json(silent=True) or {}

    try:
        latitude = float(payload.get("latitude"))
        longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return {
            "error": "Valid latitude and longitude are required."
        }, 400

    if not (-90 <= latitude <= 90):
        return {"error": "Invalid latitude."}, 400

    if not (-180 <= longitude <= 180):
        return {"error": "Invalid longitude."}, 400

    now = datetime.utcnow()

    session.current_teacher_latitude = latitude
    session.current_teacher_longitude = longitude
    session.location_updated_at = now

    db.session.commit()

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "latitude": latitude,
        "longitude": longitude,
        "location_updated_at": now.isoformat(),
    }, 200


@teacher_bp.route("/sessions/<int:session_id>/arrived", methods=["POST"])
@login_required
@teacher_required
def teacher_mark_arrived(session_id):
    """
    travelling -> arrived
    """
    session = _teacher_owned_session(session_id)

    if session.status != ClassSessionStatus.TRAVELLING:
        return {
            "error": "Session must be travelling before marking arrival.",
            "status": session.status.value,
        }, 409

    now = datetime.utcnow()

    session.status = ClassSessionStatus.ARRIVED
    session.teacher_arrived_at = now

    db.session.commit()

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "teacher_arrived_at": now.isoformat(),
    }, 200


@teacher_bp.route("/sessions/<int:session_id>/start", methods=["POST"])
@login_required
@teacher_required
def teacher_start_class(session_id):
    """
    arrived -> in_progress

    The server starts the authoritative class timer.
    """
    session = _teacher_owned_session(session_id)

    if session.status != ClassSessionStatus.ARRIVED:
        return {
            "error": "Teacher must arrive before starting the class.",
            "status": session.status.value,
        }, 409

    now = datetime.utcnow()

    session.status = ClassSessionStatus.IN_PROGRESS
    session.actual_started_at = now
    session.timer_started_at = now

    # Use the scheduled duration, never client supplied timer values.
    duration = int(
        (session.scheduled_end - session.scheduled_start).total_seconds()
    )

    if duration <= 0:
        return {"error": "Invalid session duration."}, 409

    session.timer_duration_seconds = duration

    db.session.commit()

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "timer_started_at": now.isoformat(),
        "timer_duration_seconds": session.timer_duration_seconds,
        "remaining_seconds": session.remaining_seconds,
    }, 200


@teacher_bp.route("/sessions/<int:session_id>/complete", methods=["POST"])
@login_required
@teacher_required
def teacher_complete_class(session_id):
    """
    in_progress -> completed

    Completion time is always generated by the server.
    """
    session = _teacher_owned_session(session_id)

    if session.status != ClassSessionStatus.IN_PROGRESS:
        return {
            "error": "Only an in-progress class can be completed.",
            "status": session.status.value,
        }, 409

    now = datetime.utcnow()

    # Completion is server-authoritative.
    session.status = ClassSessionStatus.COMPLETED
    session.actual_completed_at = now

    db.session.commit()

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "actual_completed_at": now.isoformat(),
        "duration_seconds": session.duration_seconds,
        "remaining_seconds": session.remaining_seconds,
    }, 200


# ============================================================
# TEACHER CLASS SESSION UI
# ============================================================

@teacher_bp.route("/sessions")
@login_required
@teacher_required
def teacher_sessions():
    profile = current_user.teacher_profile

    sessions = (
        ClassSession.query
        .filter_by(teacher_id=profile.id)
        .order_by(ClassSession.scheduled_start.asc())
        .limit(100)
        .all()
    )

    return render_template(
        "teacher/sessions.html",
        sessions=sessions,
    )


@teacher_bp.route("/sessions/<int:session_id>")
@login_required
@teacher_required
def teacher_session_detail(session_id):
    session = _teacher_owned_session(session_id)

    return render_template(
        "teacher/session_detail.html",
        session=session,
    )


@teacher_bp.route("/sessions/<int:session_id>/status")
@login_required
@teacher_required
def teacher_session_status(session_id):
    session = _teacher_owned_session(session_id)

    status = (
        session.status.value
        if hasattr(session.status, "value")
        else str(session.status)
    )

    teaching_mode = (
        session.teaching_mode.value
        if hasattr(session.teaching_mode, "value")
        else str(session.teaching_mode)
    )

    travel_mode = (
        session.travel_mode.value
        if hasattr(session.travel_mode, "value")
        else str(session.travel_mode)
    )

    return {
        "success": True,
        "session": {
            "id": session.id,
            "status": status,
            "teaching_mode": teaching_mode,
            "travel_mode": travel_mode,

            "scheduled_start": (
                session.scheduled_start.isoformat()
                if session.scheduled_start else None
            ),

            "scheduled_end": (
                session.scheduled_end.isoformat()
                if session.scheduled_end else None
            ),

            "teacher_started_travel_at": (
                session.teacher_started_travel_at.isoformat()
                if session.teacher_started_travel_at else None
            ),

            "teacher_arrived_at": (
                session.teacher_arrived_at.isoformat()
                if session.teacher_arrived_at else None
            ),

            "current_teacher_latitude":
                session.current_teacher_latitude,

            "current_teacher_longitude":
                session.current_teacher_longitude,

            "location_updated_at": (
                session.location_updated_at.isoformat()
                if session.location_updated_at else None
            ),

            "timer_started_at": (
                session.timer_started_at.isoformat()
                if session.timer_started_at else None
            ),

            "timer_duration_seconds":
                session.timer_duration_seconds,

            "duration_seconds":
                session.duration_seconds,

            "remaining_seconds":
                session.remaining_seconds,

            "is_timer_finished":
                session.is_timer_finished,

            "actual_started_at": (
                session.actual_started_at.isoformat()
                if session.actual_started_at else None
            ),

            "actual_completed_at": (
                session.actual_completed_at.isoformat()
                if session.actual_completed_at else None
            ),
        }
    }, 200
