from pathlib import Path
from app import create_app, db
from sqlalchemy import inspect
from app.models.user import User
from app.models.student_profile import StudentProfile
from app.models.teacher_profile import TeacherProfile
from app.models.student_availability import StudentAvailabilitySlot
from app.models.teacher_availability import TeacherAvailabilitySlot

ROOT = Path(".")
app = create_app()

OK = 0
BAD = 0
WARN = 0

def ok(msg):
    global OK
    OK += 1
    print("[OK]     " + msg)

def bad(msg):
    global BAD
    BAD += 1
    print("[MISSING] " + msg)

def warn(msg):
    global WARN
    WARN += 1
    print("[WARN]   " + msg)

print("=" * 75)
print("FINAL REFERRAL + TIME SLOT AUDIT")
print("=" * 75)

with app.app_context():

    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("DATABASE")
    print("=" * 75)

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    required_tables = [
        "users",
        "student_profiles",
        "teacher_profiles",
        "student_availability_slots",
        "teacher_availability_slots",
    ]

    for table in required_tables:
        if table in tables:
            ok("table: " + table)
        else:
            bad("table: " + table)

    # ---------------------------------------------------------
    # USERS COLUMNS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("USER REFERRAL DATABASE COLUMNS")
    print("=" * 75)

    user_columns = {
        c["name"]
        for c in inspector.get_columns("users")
    }

    for col in ["referral_code", "referred_by_id"]:
        if col in user_columns:
            ok("users." + col)
        else:
            bad("users." + col)

    # ---------------------------------------------------------
    # USER MODEL
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("USER MODEL")
    print("=" * 75)

    for attr in [
        "referral_code",
        "referred_by_id",
        "referred_by",
        "referred_users",
    ]:
        if hasattr(User, attr):
            ok("User." + attr)
        else:
            bad("User." + attr)

    # ---------------------------------------------------------
    # PROFILE RELATIONSHIPS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("PROFILE AVAILABILITY RELATIONSHIPS")
    print("=" * 75)

    if hasattr(StudentProfile, "availability_slots"):
        ok("StudentProfile.availability_slots")
    else:
        bad("StudentProfile.availability_slots")

    if hasattr(TeacherProfile, "availability_slots"):
        ok("TeacherProfile.availability_slots")
    else:
        bad("TeacherProfile.availability_slots")

    # ---------------------------------------------------------
    # AVAILABILITY MODELS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("AVAILABILITY MODELS")
    print("=" * 75)

    for model, fields in [
        (
            StudentAvailabilitySlot,
            ["student_id", "weekday", "start_time", "end_time", "is_active"],
        ),
        (
            TeacherAvailabilitySlot,
            ["teacher_id", "weekday", "start_time", "end_time", "is_active"],
        ),
    ]:
        print("\n" + model.__name__)

        for field in fields:
            if hasattr(model, field):
                ok(field)
            else:
                bad(field)

    # ---------------------------------------------------------
    # DATABASE AVAILABILITY COLUMNS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("AVAILABILITY DATABASE COLUMNS")
    print("=" * 75)

    for table, fields in [
        (
            "student_availability_slots",
            ["student_id", "weekday", "start_time", "end_time", "is_active"],
        ),
        (
            "teacher_availability_slots",
            ["teacher_id", "weekday", "start_time", "end_time", "is_active"],
        ),
    ]:
        print("\n" + table)

        cols = {
            c["name"]
            for c in inspector.get_columns(table)
        }

        for field in fields:
            if field in cols:
                ok(field)
            else:
                bad(field)

    # ---------------------------------------------------------
    # ROUTES
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("REGISTRATION ROUTES")
    print("=" * 75)

    rules = {
        str(rule): rule.endpoint
        for rule in app.url_map.iter_rules()
    }

    for route, endpoint in [
        ("/auth/register/student", "auth.register_student"),
        ("/auth/register/teacher", "auth.register_teacher"),
    ]:
        if route in rules and rules[route] == endpoint:
            ok(route + " -> " + endpoint)
        else:
            bad(route + " -> " + endpoint)

    # ---------------------------------------------------------
    # FORM FIELDS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("AUTH FORM FIELDS")
    print("=" * 75)

    from app.forms.auth_forms import (
        StudentRegistrationForm,
        TeacherRegistrationForm,
    )

    for form, fields in [
        (
            StudentRegistrationForm,
            ["referral_code", "availability_json"],
        ),
        (
            TeacherRegistrationForm,
            ["referral_code", "availability_json"],
        ),
    ]:
        print("\n" + form.__name__)

        for field in fields:
            if hasattr(form, field):
                ok(field)
            else:
                bad(field)

    # ---------------------------------------------------------
    # FILE CONTENT CHECK
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("APPLICATION CODE")
    print("=" * 75)

    auth = (ROOT / "app/routes/auth.py").read_text(errors="ignore")

    checks = [
        ("referral validation", "Invalid referral code"),
        ("referral lookup", "get_referrer"),
        ("referral code generation", "generate_referral_code"),
        ("student availability persistence", "StudentAvailabilitySlot"),
        ("teacher availability persistence", "TeacherAvailabilitySlot"),
    ]

    for name, needle in checks:
        if needle in auth:
            ok(name)
        else:
            bad(name)

    # ---------------------------------------------------------
    # TEMPLATES
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("REGISTRATION TEMPLATES")
    print("=" * 75)

    for file in [
        "app/templates/auth/register_student.html",
        "app/templates/auth/register_teacher.html",
    ]:
        text = Path(file).read_text(errors="ignore")

        print("\n" + file)

        for needle in [
            "form.referral_code",
            "form.availability_json",
            "availabilityRows",
            "addAvailabilitySlot",
        ]:
            if needle in text:
                ok(needle)
            else:
                bad(needle)

    # ---------------------------------------------------------
    # MIGRATION STATUS
    # ---------------------------------------------------------
    print("\n" + "=" * 75)
    print("ALEMBIC")
    print("=" * 75)

    import subprocess

    current = subprocess.run(
        ["flask", "db", "current"],
        capture_output=True,
        text=True,
    )

    heads = subprocess.run(
        ["flask", "db", "heads"],
        capture_output=True,
        text=True,
    )

    print("\nCURRENT:")
    print(current.stdout.strip())

    if current.returncode == 0:
        ok("flask db current")

    print("\nHEADS:")
    print(heads.stdout.strip())

    if heads.returncode == 0:
        ok("flask db heads")

print("\n" + "=" * 75)
print("FINAL RESULT")
print("=" * 75)

print(f"OK      : {OK}")
print(f"MISSING : {BAD}")
print(f"WARN    : {WARN}")

if BAD == 0:
    print("\n[PASS] Referral + availability structural audit passed.")
else:
    print("\n[FAIL] Some components are still missing.")

print("=" * 75)
