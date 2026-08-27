from app.services.google_oauth import init_google_oauth
"""
Application factory.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)


def create_app(config_name=None):
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    from config import config_by_name
    app.config.from_object(config_by_name[config_name])

    if config_name == "production":
        if not app.config.get("SQLALCHEMY_DATABASE_URI") or not os.environ.get("DATABASE_URL"):
            raise RuntimeError("DATABASE_URL must be set in production")
        if app.config.get("SECRET_KEY") == "dev-secret-key-change-in-production":
            raise RuntimeError("SECRET_KEY must be set to a secure value in production")

    # Ensure required directories exist
    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    for sub in ("photos", "documents", "chat", "qr_codes"):
        os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], sub), exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"
    csrf.init_app(app)
    limiter.init_app(app)

    configure_logging(app)

    # Models must be imported so SQLAlchemy/Flask-Migrate see them
    from app.models import user, teacher_profile, student_profile, otp, hire_request  # noqa
    from app.models import attendance, wallet, withdrawal, system_setting  # noqa
    from app.models import payment_settings, payment_transaction, payment_verification, refund  # noqa
    from app.models import notification, review, complaint, chat, audit_log, announcement, contact_request  # noqa

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.student import student_bp
    from app.routes.teacher import teacher_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.chat import chat_bp
    from app.services.google_oauth_routes import google_auth_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(google_auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/chat")

    register_error_handlers(app)

    @app.context_processor
    def inject_globals():
        from app.services.settings_service import get_setting
        return {
            "site_name": get_setting("SITE_NAME", "LocalTutor"),
        }

    init_google_oauth(app)

    return app


def configure_logging(app):
    if not app.debug and not app.testing:
        handler = RotatingFileHandler(
            os.path.join(app.config["LOG_DIR"], "app.log"), maxBytes=1_000_000, backupCount=5
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s [in %(pathname)s:%(lineno)d]"
        ))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Server error")
        return render_template("errors/500.html"), 500
