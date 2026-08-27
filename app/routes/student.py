import re
from decimal import Decimal
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy.orm import joinedload
from flask_login import login_required, current_user

from app import db
from app.utils.decorators import student_required
from app.utils.file_upload import save_upload, InvalidFileError
from app.models.hire_request import HireRequest, HireStatus
from app.models.teacher_profile import TeacherProfile, TeacherStatus, TeachingMode
from app.models.payment_transaction import PaymentTransaction, PaymentStatus
from app.models.payment_settings import PaymentSettings
from app.models.attendance import Attendance
from app.models.review import Review
from app.models.complaint import Complaint
from app.models.notification import Notification
from app.forms.marketplace_forms import (
    HireRequestForm, PaymentSubmitForm, ReviewForm, ComplaintForm,
)
from app.services.geo_service import bounding_box, find_within_radius, subject_match_score
from app.services.settings_service import get_search_radius_km
from app.services.notification_service import notify
from app.services.scheduling_service import create_class_session
from app.services.availability_service import (
    get_teacher_availability_for_date,
    get_real_available_slots,
)
from app.services.slot_service import (
    is_teacher_slot_free,
)
from app.models.class_session import (
    ClassSession,
    ClassSessionStatus,
    SessionTeachingMode,
    TravelMode,
)

student_bp = Blueprint("student", __name__, template_folder="../templates/student")


@student_bp.route("/dashboard")
@login_required
@student_required
def dashboard():
    profile = current_user.student_profile
    active_hires = (
        HireRequest.query.filter_by(student_id=profile.id, status=HireStatus.ACCEPTED).count()
        if profile else 0
    )
    pending_hires = (
        HireRequest.query.filter_by(student_id=profile.id, status=HireStatus.PENDING).count()
        if profile else 0
    )
    recent_payments = (
        PaymentTransaction.query.filter_by(student_id=profile.id).order_by(PaymentTransaction.created_at.desc()).limit(5).all()
        if profile else []
    )
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template(
        "student/dashboard.html",
        profile=profile,
        active_hires=active_hires,
        pending_hires=pending_hires,
        recent_payments=recent_payments,
        unread_count=unread_count,
    )


@student_bp.route("/profile")
@login_required
@student_required
def profile():
    return render_template("student/profile.html", profile=current_user.student_profile)


# --------------------------------------------------------------------------
# Teacher search (radius / Haversine)
# --------------------------------------------------------------------------
@student_bp.route("/teachers")
def teacher_search():
    """Public nearby-teacher search; hiring still requires student login."""
    profile = current_user.student_profile if current_user.is_authenticated and current_user.is_student else None
    radius_km = request.args.get("radius_km", type=float) or get_search_radius_km()
    radius_km = min(max(radius_km, 0.5), 50.0)
    subject = (request.args.get("subject") or request.args.get("q") or "").strip()
    mode = request.args.get("mode", "").strip().lower()

    latitude = request.args.get("latitude", type=float)
    longitude = request.args.get("longitude", type=float)
    if latitude is None or longitude is None:
        if profile and profile.latitude is not None and profile.longitude is not None:
            latitude, longitude = profile.latitude, profile.longitude

    valid_coords = (
        latitude is not None and longitude is not None
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    )
    results = []
    existing_requests = {}

    if valid_coords:
        lat_min, lat_max, lon_min, lon_max = bounding_box(latitude, longitude, radius_km)
        query = TeacherProfile.query.options(joinedload(TeacherProfile.user)).filter(
            TeacherProfile.status == TeacherStatus.APPROVED,
            TeacherProfile.is_available.is_(True),
            TeacherProfile.latitude.between(lat_min, lat_max),
            TeacherProfile.longitude.between(lon_min, lon_max),
        )
        if mode in ("online", "offline", "both"):
            query = query.filter(TeacherProfile.teaching_mode == TeachingMode(mode))

        candidates = query.all()
        nearby = find_within_radius(candidates, latitude, longitude, radius_km)

        if subject:
            scored = [(teacher, distance, subject_match_score(subject, teacher)) for teacher, distance in nearby]
            scored = [item for item in scored if item[2] > 0]
            # Subject relevance first, then distance. This keeps a relevant teacher at 3 km
            # ahead of an unrelated teacher at 0.8 km.
            scored.sort(key=lambda item: (-item[2], item[1]))
            results = [(teacher, distance) for teacher, distance, _score in scored]
        else:
            results = nearby

        if profile:
            existing_requests = {
                hr.teacher_id: hr.status
                for hr in HireRequest.query.filter_by(student_id=profile.id).all()
            }

    return render_template(
        "student/teacher_search.html",
        results=results,
        radius_km=radius_km,
        subject=subject,
        mode=mode,
        existing_requests=existing_requests,
        latitude=latitude,
        longitude=longitude,
        location_ready=valid_coords,
        is_student=current_user.is_authenticated and current_user.is_student,
    )


@student_bp.route("/teachers/<int:teacher_id>/available-slots")
@login_required
@student_required
def teacher_available_slots(teacher_id):
    """
    Return real bookable slots for a teacher.

    The teacher's recurring availability is intersected with already
    scheduled ClassSession records, so students only see slots that
    can actually be booked.
    """
    teacher = TeacherProfile.query.get_or_404(teacher_id)

    if teacher.status != TeacherStatus.APPROVED or not teacher.is_available:
        return {"slots": [], "message": "Teacher is not currently available."}, 200

    date_text = (request.args.get("date") or "").strip()

    try:
        requested_date = (
            datetime.strptime(date_text, "%Y-%m-%d").date()
            if date_text
            else datetime.utcnow().date()
        )
    except ValueError:
        return {"error": "Invalid date. Use YYYY-MM-DD."}, 400

    duration = request.args.get("duration", 60, type=int)
    step = request.args.get("step", 15, type=int)

    duration = min(max(duration, 15), 240)
    step = min(max(step, 5), 60)

    slots = get_real_available_slots(
        teacher_id=teacher.id,
        requested_date=requested_date,
        duration_minutes=duration,
        step_minutes=step,
    )

    return {
        "teacher_id": teacher.id,
        "date": requested_date.isoformat(),
        "duration_minutes": duration,
        "step_minutes": step,
        "slots": [
            {
                "start": slot["start"].isoformat(),
                "end": slot["end"].isoformat(),
                "start_time": slot["start"].strftime("%H:%M"),
                "end_time": slot["end"].strftime("%H:%M"),
            }
            for slot in slots
        ],
    }


@student_bp.route("/teachers/<int:teacher_id>/book-slot", methods=["POST"])
@login_required
@student_required
def book_teacher_slot(teacher_id):
    """
    Atomically validate the requested occurrence and create a ClassSession.

    A recurring teacher availability window is NOT itself a booking.
    ClassSession is the actual occurrence that blocks the teacher.
    """
    profile = current_user.student_profile
    teacher = TeacherProfile.query.get_or_404(teacher_id)

    if teacher.status != TeacherStatus.APPROVED or not teacher.is_available:
        return {"error": "Teacher is not currently available."}, 400

    payload = request.get_json(silent=True) or {}

    start_text = str(payload.get("scheduled_start") or "").strip()
    end_text = str(payload.get("scheduled_end") or "").strip()

    if not start_text or not end_text:
        return {"error": "scheduled_start and scheduled_end are required."}, 400

    try:
        scheduled_start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        scheduled_end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))

        if scheduled_start.tzinfo:
            scheduled_start = scheduled_start.replace(tzinfo=None)

        if scheduled_end.tzinfo:
            scheduled_end = scheduled_end.replace(tzinfo=None)
    except ValueError:
        return {"error": "Invalid datetime format."}, 400

    if scheduled_end <= scheduled_start:
        return {"error": "scheduled_end must be after scheduled_start."}, 400

    duration_minutes = int(
        (scheduled_end - scheduled_start).total_seconds() / 60
    )

    if duration_minutes < 15 or duration_minutes > 240:
        return {"error": "Class duration must be between 15 and 240 minutes."}, 400

    teaching_mode = str(
        payload.get("teaching_mode") or "home"
    ).strip().lower()

    if teaching_mode not in ("home", "online"):
        return {"error": "Invalid teaching_mode."}, 400

    travel_mode = str(
        payload.get("travel_mode") or (
            "online" if teaching_mode == "online" else "bike"
        )
    ).strip().lower()

    if travel_mode not in ("walking", "bike", "car", "online"):
        return {"error": "Invalid travel_mode."}, 400

    if teaching_mode == "online":
        travel_mode = "online"

    try:
        # If a hire request is supplied, it MUST belong to the current
        # student + selected teacher and must already be accepted.
        hire_request_id = payload.get("hire_request_id")

        if hire_request_id is not None:
            try:
                hire_request_id = int(hire_request_id)
            except (TypeError, ValueError):
                return {"error": "Invalid hire_request_id."}, 400

            hire = HireRequest.query.filter_by(
                id=hire_request_id,
                student_id=profile.id,
                teacher_id=teacher.id,
            ).first()

            if hire is None:
                return {"error": "Invalid hire request."}, 403

            if hire.status != HireStatus.ACCEPTED:
                return {
                    "error": "The hire request must be accepted before booking a class."
                }, 409

        if not is_teacher_slot_free(
            teacher.id,
            scheduled_start,
            scheduled_end,
            travel_buffer_minutes=0,
        ):
            return {
                "error": "This teacher has already been booked for this time."
            }, 409

        session = create_class_session(
            teacher_id=teacher.id,
            student_id=profile.id,
            hire_request_id=hire_request_id,
            scheduled_start=scheduled_start,
            duration_minutes=duration_minutes,
            teaching_mode=teaching_mode,
            travel_mode=travel_mode,
            origin_latitude=payload.get("origin_latitude"),
            origin_longitude=payload.get("origin_longitude"),
            destination_latitude=payload.get("destination_latitude"),
            destination_longitude=payload.get("destination_longitude"),
            travel_buffer_minutes=int(
                payload.get("travel_buffer_minutes") or 0
            ),
            notes=str(payload.get("notes") or "").strip()[:1000] or None,
        )

        db.session.commit()

    except ValueError as exc:
        db.session.rollback()
        return {"error": str(exc)}, 409

    except Exception:
        db.session.rollback()
        raise

    return {
        "success": True,
        "session_id": session.id,
        "status": session.status.value,
        "scheduled_start": session.scheduled_start.isoformat(),
        "scheduled_end": session.scheduled_end.isoformat(),
        "teaching_mode": session.teaching_mode.value
        if hasattr(session.teaching_mode, "value")
        else session.teaching_mode,
        "travel_mode": session.travel_mode.value
        if hasattr(session.travel_mode, "value")
        else session.travel_mode,
    }, 201

@student_bp.route("/teachers/<int:teacher_id>/hire", methods=["POST"])
@login_required
@student_required
def hire_teacher(teacher_id):
    profile = current_user.student_profile
    teacher = TeacherProfile.query.get_or_404(teacher_id)
    if teacher.status != TeacherStatus.APPROVED:
        flash("This teacher is not currently available for hire.", "danger")
        return redirect(url_for("student.teacher_search"))

    existing = HireRequest.query.filter_by(
        student_id=profile.id, teacher_id=teacher.id, status=HireStatus.PENDING
    ).first()
    if existing:
        flash("You already have a pending request with this teacher.", "warning")
        return redirect(url_for("student.teacher_search"))

    form = HireRequestForm()

    if not form.validate_on_submit():
        flash("Invalid hire request.", "danger")
        return redirect(url_for("student.teacher_search"))

    hire = HireRequest(
        student_id=profile.id,
        teacher_id=teacher.id,
        message=(form.message.data or "").strip(),
        status=HireStatus.PENDING,
    )
    db.session.add(hire)
    db.session.commit()

    notify(
        teacher.user_id, "New Hire Request",
        f"{current_user.name} sent you a hire request.",
        link=url_for("teacher.hire_requests"),
    )
    db.session.commit()

    flash("Hire request sent!", "success")
    return redirect(url_for("student.my_hires"))


@student_bp.route("/hires")
@login_required
@student_required
def my_hires():
    profile = current_user.student_profile
    hires = (
        HireRequest.query.options(joinedload(HireRequest.teacher).joinedload(TeacherProfile.user))
        .filter_by(student_id=profile.id)
        .order_by(HireRequest.created_at.desc()).all()
    )
    reviewed_teacher_ids = {
        r.teacher_id for r in Review.query.filter_by(student_id=profile.id).all()
    }
    return render_template("student/my_hires.html", hires=hires, reviewed_teacher_ids=reviewed_teacher_ids)


@student_bp.route("/hires/<int:hire_id>/cancel", methods=["POST"])
@login_required
@student_required
def cancel_hire(hire_id):
    profile = current_user.student_profile
    hire = HireRequest.query.filter_by(id=hire_id, student_id=profile.id).first_or_404()
    if hire.status == HireStatus.PENDING:
        hire.status = HireStatus.CANCELLED
        db.session.commit()
        flash("Hire request cancelled.", "info")
    return redirect(url_for("student.my_hires"))


# --------------------------------------------------------------------------
# Attendance (view only for students)
# --------------------------------------------------------------------------
@student_bp.route("/attendance")
@login_required
@student_required
def attendance_history():
    profile = current_user.student_profile
    records = (
        Attendance.query.options(joinedload(Attendance.teacher).joinedload(TeacherProfile.user))
        .filter_by(student_id=profile.id)
        .order_by(Attendance.date.desc()).all()
    )
    return render_template("student/attendance.html", records=records)


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------
@student_bp.route("/payments", methods=["GET", "POST"])
@login_required
@student_required
def payments():
    profile = current_user.student_profile
    settings = PaymentSettings.get_solo()

    if settings.maintenance_mode:
        flash("Payments are temporarily under maintenance. Please try again shortly.", "warning")

    hired_teachers = (
        db.session.query(TeacherProfile)
        .options(joinedload(TeacherProfile.user))
        .join(HireRequest, HireRequest.teacher_id == TeacherProfile.id)
        .filter(HireRequest.student_id == profile.id, HireRequest.status == HireStatus.ACCEPTED)
        .all()
    )

    form = PaymentSubmitForm()
    form.teacher_id.choices = [(t.id, f"{t.user.name} ({t.subjects})") for t in hired_teachers]

    if form.validate_on_submit():
        if settings.maintenance_mode:
            flash("Payments are temporarily disabled by the admin.", "danger")
            return redirect(url_for("student.payments"))

        teacher = TeacherProfile.query.get(form.teacher_id.data)
        if (
            not teacher
            or teacher.id not in [t.id for t in hired_teachers]
            or teacher.status != TeacherStatus.APPROVED
            or not teacher.is_available
        ):
            flash("Invalid teacher selection.", "danger")
            return redirect(url_for("student.payments"))

        try:
            screenshot_path = save_upload(form.proof_screenshot.data, "documents", {"png", "jpg", "jpeg"})
        except InvalidFileError as e:
            flash(str(e), "danger")
            return redirect(url_for("student.payments"))

        commission_percent = settings.commission_percent
        amount = form.amount.data
        commission_amount = (amount * commission_percent) / Decimal("100")
        net_to_teacher = amount - commission_amount

        initial_status = PaymentStatus.VERIFIED if settings.auto_approval else PaymentStatus.PENDING

        payment = PaymentTransaction(
            student_id=profile.id,
            teacher_id=teacher.id,
            amount=amount,
            commission_percent=commission_percent,
            commission_amount=commission_amount,
            net_to_teacher=net_to_teacher,
            transaction_id=(form.transaction_id.data or "").strip()[:120],
            screenshot_path=screenshot_path,
            billing_period=form.billing_period.data,
            status=initial_status,
        )
        db.session.add(payment)
        db.session.flush()

        if settings.auto_approval:
            from app.services.wallet_service import credit_payment
            payment.verified_at = datetime.utcnow()
            credit_payment(teacher.id, net_to_teacher, reference=f"payment#{payment.id}")
            notify(teacher.user_id, "Payment Received",
                   f"Rs. {net_to_teacher} auto-credited to your wallet (payment #{payment.id}).",
                   link=url_for("teacher.wallet"))
            flash("Payment submitted and auto-verified.", "success")
        else:
            notify(
                teacher.user_id, "Payment Submitted",
                f"{current_user.name} submitted a payment of Rs. {amount} for admin verification.",
            )
            flash("Payment submitted. It will be verified by the admin shortly.", "success")

        db.session.commit()
        return redirect(url_for("student.payments"))

    history = (
        PaymentTransaction.query
        .options(joinedload(PaymentTransaction.teacher).joinedload(TeacherProfile.user))
        .filter_by(student_id=profile.id)
        .order_by(PaymentTransaction.created_at.desc())
        .all()
    )
    return render_template(
        "student/payments.html", form=form, history=history,
        settings=settings, has_teachers=bool(hired_teachers),
    )


@student_bp.route("/payments/<int:payment_id>/receipt")
@login_required
@student_required
def payment_receipt(payment_id):
    profile = current_user.student_profile
    payment = PaymentTransaction.query.filter_by(id=payment_id, student_id=profile.id).first_or_404()
    return render_template("student/receipt.html", payment=payment)


# --------------------------------------------------------------------------
# Reviews
# --------------------------------------------------------------------------
@student_bp.route("/teachers/<int:teacher_id>/review", methods=["GET", "POST"])
@login_required
@student_required
def leave_review(teacher_id):
    profile = current_user.student_profile
    teacher = TeacherProfile.query.get_or_404(teacher_id)

    was_hired = HireRequest.query.filter_by(
        student_id=profile.id, teacher_id=teacher.id, status=HireStatus.ACCEPTED
    ).first()
    if not was_hired:
        flash("You can only review teachers you have hired.", "danger")
        return redirect(url_for("student.my_hires"))

    existing_review = Review.query.filter_by(student_id=profile.id, teacher_id=teacher.id).first()

    form = ReviewForm(obj=existing_review)
    if form.validate_on_submit():
        if existing_review:
            existing_review.rating = form.rating.data
            existing_review.comment = form.comment.data
        else:
            db.session.add(Review(
                student_id=profile.id, teacher_id=teacher.id,
                rating=form.rating.data, comment=form.comment.data,
            ))
        db.session.flush()

        all_ratings = Review.query.filter_by(teacher_id=teacher.id).all()
        teacher.rating_count = len(all_ratings)
        teacher.average_rating = sum(r.rating for r in all_ratings) / len(all_ratings) if all_ratings else 0
        db.session.commit()

        flash("Thanks for your review!", "success")
        return redirect(url_for("student.my_hires"))

    return render_template("student/review_form.html", form=form, teacher=teacher, existing_review=existing_review)


# --------------------------------------------------------------------------
# Complaints
# --------------------------------------------------------------------------
@student_bp.route("/complaints", methods=["GET", "POST"])
@login_required
@student_required
def complaints():
    profile = current_user.student_profile
    hired_teachers = (
        db.session.query(TeacherProfile)
        .options(joinedload(TeacherProfile.user))
        .join(HireRequest, HireRequest.teacher_id == TeacherProfile.id)
        .filter(HireRequest.student_id == profile.id, HireRequest.status == HireStatus.ACCEPTED)
        .all()
    )

    form = ComplaintForm()
    form.teacher_id.choices = [(0, "General / Not teacher-specific")] + [
        (t.id, f"{t.user.name}") for t in hired_teachers
    ]

    if form.validate_on_submit():
        db.session.add(Complaint(
            student_id=profile.id,
            teacher_id=form.teacher_id.data if form.teacher_id.data else None,
            subject=form.subject.data.strip(),
            description=form.description.data.strip(),
        ))
        db.session.commit()
        flash("Complaint submitted. Our team will review it shortly.", "success")
        return redirect(url_for("student.complaints"))

    history = Complaint.query.filter_by(student_id=profile.id).order_by(Complaint.created_at.desc()).all()
    return render_template("student/complaints.html", form=form, history=history)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@student_bp.route("/notifications")
@login_required
@student_required
def notifications():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("student/notifications.html", items=items)




# ============================================================
# STUDENT CLASS SESSION UI
# ============================================================

@student_bp.route("/sessions")
@login_required
@student_required
def student_sessions():
    profile = current_user.student_profile

    sessions = (
        ClassSession.query
        .filter_by(student_id=profile.id)
        .order_by(ClassSession.scheduled_start.asc())
        .limit(100)
        .all()
    )

    return render_template(
        "student/sessions.html",
        sessions=sessions,
    )


@student_bp.route("/sessions/<int:session_id>")
@login_required
@student_required
def student_session_detail(session_id):
    profile = current_user.student_profile

    session = ClassSession.query.filter_by(
        id=session_id,
        student_id=profile.id,
    ).first_or_404()

    return render_template(
        "student/session_detail.html",
        session=session,
    )


# ============================================================
# STUDENT LIVE CLASS / TEACHER LOCATION
# ============================================================

@student_bp.route("/sessions/<int:session_id>/status")
@login_required
@student_required
def student_session_status(session_id):
    """
    Student can see only their own class session.

    This endpoint exposes:
      - teacher travel state
      - live teacher coordinates
      - arrival state
      - server-authoritative class timer
    """
    profile = current_user.student_profile

    session = ClassSession.query.filter_by(
        id=session_id,
        student_id=profile.id,
    ).first_or_404()

    # Server-authoritative timer enforcement.
    # Never trust the student's browser countdown.
    if (
        session.status == ClassSessionStatus.IN_PROGRESS
        and session.timer_started_at
        and session.is_timer_finished
    ):
        session.status = ClassSessionStatus.COMPLETED

        if session.actual_completed_at is None:
            session.actual_completed_at = datetime.utcnow()

        db.session.commit()

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
            "teacher_id": session.teacher_id,
            "student_id": session.student_id,
            "status": status,

            "scheduled_date": (
                session.scheduled_date.isoformat()
                if session.scheduled_date else None
            ),
            "scheduled_start": session.scheduled_start.isoformat(),
            "scheduled_end": session.scheduled_end.isoformat(),

            "teaching_mode": teaching_mode,
            "travel_mode": travel_mode,

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
