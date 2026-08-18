import os

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import current_user

from app import db
from app.models.contact_request import ContactRequest
from app.models.user import RoleEnum

main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/sw.js")
def service_worker():
    """
    Served from the root (not /static/) so its scope covers the whole app,
    letting the PWA cache and serve pages when offline.
    """
    response = send_from_directory(
        os.path.join(current_app.root_path, "static"), "sw.js", mimetype="application/javascript"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@main_bp.route("/offline")
def offline():
    return render_template("offline.html")


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == RoleEnum.SUPER_ADMIN:
            return redirect(url_for("admin.dashboard"))
        if current_user.role == RoleEnum.TEACHER:
            return redirect(url_for("teacher.dashboard"))
        return redirect(url_for("student.dashboard"))
    return render_template("index.html")


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        cr = ContactRequest(
            name=request.form.get("name", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
            subject=request.form.get("subject", "").strip(),
            message=request.form.get("message", "").strip(),
        )
        if cr.name and cr.email and cr.subject and cr.message:
            db.session.add(cr)
            db.session.commit()
            flash("Thanks for reaching out — we'll get back to you soon.", "success")
        else:
            flash("Please fill in all required fields.", "danger")
        return redirect(url_for("main.contact"))
    return render_template("contact.html")
