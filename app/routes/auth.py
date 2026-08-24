from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app import db, limiter
from app.forms.auth_forms import (
    LoginForm, StudentRegistrationForm, TeacherRegistrationForm,
    OtpVerifyForm, ForgotPasswordForm, ResetPasswordForm,
)
from app.models.user import User, RoleEnum
from app.models.student_profile import StudentProfile
from app.models.teacher_profile import TeacherProfile, TeacherStatus
from app.models.wallet import Wallet
from app.models.otp import OtpPurpose
from app.models.audit_log import AuditLog
from app.services.otp_service import issue_otp, verify_otp
from app.services.email_service import EmailNotConfigured
from app.utils.file_upload import save_upload, InvalidFileError

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = StudentRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter((User.email == form.email.data) | (User.mobile == form.mobile.data)).first():
            flash("An account with this email or mobile number already exists.", "danger")
            return render_template("auth/register_student.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.STUDENT,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        profile = StudentProfile(
            user_id=user.id,
            address=form.address.data.strip(),
            state=form.state.data.strip(),
            city=form.city.data.strip(),
            pincode=form.pincode.data.strip(),
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            student_class=form.student_class.data.strip(),
            subjects_required=form.subjects_required.data.strip(),
        )
        db.session.add(profile)
        db.session.commit()

        AuditLog.log(user.id, "student_registered", ip_address=request.remote_addr)
        db.session.commit()

        try:
            issue_otp(user, OtpPurpose.EMAIL_VERIFICATION)
        except EmailNotConfigured:
            flash("Account created, but email OTP could not be sent because SMTP is not configured yet. Contact admin.", "warning")
            return redirect(url_for("auth.login"))

        session["pending_verification_user_id"] = user.id
        flash("Account created! We emailed you a verification code.", "success")
        return redirect(url_for("auth.verify_email"))

    return render_template("auth/register_student.html", form=form)


@auth_bp.route("/register/teacher", methods=["GET", "POST"])
def register_teacher():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = TeacherRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter((User.email == form.email.data) | (User.mobile == form.mobile.data)).first():
            flash("An account with this email or mobile number already exists.", "danger")
            return render_template("auth/register_teacher.html", form=form)

        try:
            photo_path = save_upload(form.photo.data, "photos", {"png", "jpg", "jpeg", "webp"})
            aadhaar_path = save_upload(form.aadhaar.data, "documents", {"pdf", "png", "jpg", "jpeg"})
            cert_path = save_upload(form.qualification_certificate.data, "documents", {"pdf", "png", "jpg", "jpeg"})
        except InvalidFileError as e:
            flash(str(e), "danger")
            return render_template("auth/register_teacher.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.TEACHER,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        profile = TeacherProfile(
            user_id=user.id,
            photo_path=photo_path,
            aadhaar_path=aadhaar_path,
            qualification_certificate_path=cert_path,
            experience_years=form.experience_years.data,
            subjects=form.subjects.data.strip(),
            classes=form.classes.data.strip(),
            teaching_mode=form.teaching_mode.data,
            monthly_fees=form.monthly_fees.data,
            address=form.address.data.strip(),
            latitude=form.latitude.data,
            longitude=form.longitude.data,
            upi_id=form.upi_id.data,
            bank_account_holder=form.bank_account_holder.data,
            bank_account_number=form.bank_account_number.data,
            bank_ifsc=form.bank_ifsc.data,
            bank_name=form.bank_name.data,
            status=TeacherStatus.PENDING,
        )
        db.session.add(profile)
        db.session.flush()

        wallet = Wallet(teacher_id=profile.id)
        db.session.add(wallet)
        db.session.commit()

        AuditLog.log(user.id, "teacher_registered", ip_address=request.remote_addr)
        db.session.commit()

        try:
            issue_otp(user, OtpPurpose.EMAIL_VERIFICATION)
            session["pending_verification_user_id"] = user.id
            return redirect(url_for("auth.verify_email"))
        except EmailNotConfigured:
            pass

        flash(
            "Registration submitted! Your profile is pending Admin approval. "
            "You will be able to log in once approved.", "success"
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register_teacher.html", form=form)


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    user_id = session.get("pending_verification_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    form = OtpVerifyForm()
    if form.validate_on_submit():
        if verify_otp(user, OtpPurpose.EMAIL_VERIFICATION, form.code.data.strip()):
            user.is_email_verified = True
            db.session.commit()
            session.pop("pending_verification_user_id", None)

            if user.role == RoleEnum.TEACHER:
                flash("Email verified! Your profile is now pending Admin approval.", "success")
                return redirect(url_for("auth.login"))

            flash("Email verified successfully. You can now log in.", "success")
            return redirect(url_for("auth.login"))

        flash("Invalid or expired code. Please try again.", "danger")

    return render_template("auth/verify_email.html", form=form, email=user.email)


@auth_bp.route("/resend-otp")
def resend_otp():
    user_id = session.get("pending_verification_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    user = User.query.get(user_id)
    try:
        issue_otp(user, OtpPurpose.EMAIL_VERIFICATION)
        flash("A new verification code has been sent.", "info")
    except EmailNotConfigured:
        flash("Email is not configured yet. Contact admin.", "danger")
    return redirect(url_for("auth.verify_email"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if not user or not user.check_password(form.password.data):
            AuditLog.log(user.id if user else None, "login_failed", ip_address=request.remote_addr)
            db.session.commit()
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_email_verified:
            session["pending_verification_user_id"] = user.id
            flash("Please verify your email before logging in.", "warning")
            return redirect(url_for("auth.verify_email"))

        if user.role == RoleEnum.TEACHER and user.teacher_profile:
            status = user.teacher_profile.status
            if status == TeacherStatus.PENDING:
                flash("Your account is pending Admin approval.", "warning")
                return render_template("auth/login.html", form=form)
            if status == TeacherStatus.REJECTED:
                flash("Your teacher application was rejected. Contact support for details.", "danger")
                return render_template("auth/login.html", form=form)
            if status == TeacherStatus.SUSPENDED:
                flash("Your account has been suspended. Contact support.", "danger")
                return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("Your account has been deactivated. Contact support.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=True)
        user.last_login_at = datetime.utcnow()
        AuditLog.log(user.id, "login_success", ip_address=request.remote_addr)
        db.session.commit()

        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)
        if user.role == RoleEnum.SUPER_ADMIN:
            return redirect(url_for("admin.dashboard"))
        if user.role == RoleEnum.TEACHER:
            return redirect(url_for("teacher.dashboard"))
        return redirect(url_for("student.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    AuditLog.log(current_user.id, "logout", ip_address=request.remote_addr)
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        # Always show the same message to avoid leaking which emails are registered
        if user:
            try:
                issue_otp(user, OtpPurpose.PASSWORD_RESET)
                session["password_reset_user_id"] = user.id
            except EmailNotConfigured:
                flash("Email is not configured on this server yet. Contact admin.", "danger")
                return render_template("auth/forgot_password.html", form=form)
        flash("If that email is registered, a reset code has been sent.", "info")
        return redirect(url_for("auth.reset_password"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("password_reset_user_id")
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(user_id) if user_id else None
        if not user or not verify_otp(user, OtpPurpose.PASSWORD_RESET, form.code.data.strip()):
            flash("Invalid or expired code.", "danger")
            return render_template("auth/reset_password.html", form=form)

        user.set_password(form.password.data)
        db.session.commit()
        session.pop("password_reset_user_id", None)
        AuditLog.log(user.id, "password_reset", ip_address=request.remote_addr)
        db.session.commit()
        flash("Password updated. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
