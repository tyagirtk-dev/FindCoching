"""
Database initialization / seed script.

Usage:
    python seed.py

Creates all tables (for a fresh SQLite dev DB — in production use Alembic
migrations instead: `flask db upgrade`), seeds default SystemSetting rows,
and creates the initial Super Admin account from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models.user import User, RoleEnum
from app.models.payment_settings import PaymentSettings
from app.services.settings_service import seed_defaults


def run():
    app = create_app(os.environ.get("FLASK_ENV", "development"))

    with app.app_context():
        db.create_all()
        print("[seed] Tables created (or already exist).")

        seed_defaults()
        print("[seed] Default system settings seeded.")

        PaymentSettings.get_solo()
        print("[seed] Payment settings row ensured.")

        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower().strip()
        admin_mobile = os.environ.get("ADMIN_MOBILE", "9999999999").strip()
        admin_name = os.environ.get("ADMIN_NAME", "Super Admin").strip()
        admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

        existing = User.query.filter_by(email=admin_email).first()
        if existing:
            print(f"[seed] Super Admin '{admin_email}' already exists — skipping.")
        else:
            admin = User(
                name=admin_name,
                email=admin_email,
                mobile=admin_mobile,
                role=RoleEnum.SUPER_ADMIN,
                is_active_account=True,
                is_email_verified=True,
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(f"[seed] Super Admin created: {admin_email} / (password from ADMIN_PASSWORD env var)")

        print("[seed] Done.")


if __name__ == "__main__":
    run()
