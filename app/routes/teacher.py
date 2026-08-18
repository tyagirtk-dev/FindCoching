from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash
from sqlalchemy.orm import joinedload
from flask_login import login_required, current_user

from app import db
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
    hire = HireRequest.query.filter_by(id=hire_id, teacher_id=profile.id).first_or_404()
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
    hire = HireRequest.query.filter_by(id=hire_id, teacher_id=profile.id).first_or_404()
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

        db.session.add(WithdrawalRequest(
            teacher_id=profile.id,
            amount=form.amount.data,
            payout_method=form.payout_method.data,
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
