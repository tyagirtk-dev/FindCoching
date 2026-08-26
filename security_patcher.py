from pathlib import Path
from datetime import datetime
import shutil
import ast
import re
import sys

ROOT = Path.cwd()

TARGETS = [
    "app/routes/auth.py",
    "app/routes/teacher.py",
    "app/routes/student.py",
    "app/routes/admin.py",
    "app/routes/api.py",
    "app/services/wallet_service.py",
    "app/services/otp_service.py",
    "app/services/email_service.py",
    "app/services/geo_service.py",
    "app/utils/file_upload.py",
    "app/utils/decorators.py",
    "app/models/user.py",
    "app/models/teacher_profile.py",
    "app/models/student_profile.py",
    "app/models/hire_request.py",
    "app/models/payment_transaction.py",
    "app/models/wallet.py",
    "app/models/otp.py",
    "app/models/payment_settings.py",
]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"BACKUP_AUTOMATED_PATCH_{stamp}"
BACKUP.mkdir()

print("=" * 70)
print("LOCAL TUTOR — SAFE AUTOMATED SECURITY PATCHER")
print("=" * 70)
print(f"Backup: {BACKUP}")
print()

# ---------------------------------------------------------------------
# 1. BACKUP
# ---------------------------------------------------------------------

existing = []

for rel in TARGETS:
    src = ROOT / rel
    if src.exists():
        dst = BACKUP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        existing.append(rel)
        print(f"[BACKUP] {rel}")

print()
print(f"Backed up {len(existing)} files.")

# ---------------------------------------------------------------------
# 2. PATCH HELPERS
# ---------------------------------------------------------------------

changed = []
skipped = []

def load(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def save(rel, text):
    p = ROOT / rel

    try:
        ast.parse(text)
    except SyntaxError as e:
        raise RuntimeError(
            f"Syntax error would be introduced into {rel}: {e}"
        )

    p.write_text(text, encoding="utf-8")
    changed.append(rel)

def replace_once(rel, old, new, label):
    text = load(rel)

    if old not in text:
        skipped.append(f"{rel}: {label} (pattern not found)")
        return False

    text2 = text.replace(old, new, 1)
    save(rel, text2)

    print(f"[PATCH] {rel} -> {label}")
    return True

# ---------------------------------------------------------------------
# 3. AUTH: OPEN REDIRECT PROTECTION
# ---------------------------------------------------------------------

auth = "app/routes/auth.py"

text = load(auth)

old = '''        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)
'''

new = '''        # Never redirect to an arbitrary external URL supplied by the client.
        # Only allow local relative paths.
        next_url = request.args.get("next", "").strip()

        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
'''

if old in text:
    save(auth, text.replace(old, new, 1))
    print("[PATCH] auth.py -> open redirect protection")
else:
    skipped.append("auth.py: open redirect protection (pattern not found)")

# ---------------------------------------------------------------------
# 4. AUTH: OTP RESEND MUST NOT USE GET
# ---------------------------------------------------------------------

text = load(auth)

old = '@auth_bp.route("/resend-otp")'
new = '@auth_bp.route("/resend-otp", methods=["POST"])'

if old in text and new not in text:
    save(auth, text.replace(old, new, 1))
    print("[PATCH] auth.py -> OTP resend POST-only")
else:
    skipped.append("auth.py: OTP resend POST-only (pattern not found/already patched)")

# ---------------------------------------------------------------------
# 5. TEACHER: HIRE ACCEPT/REJECT MUST ONLY PROCESS PENDING REQUESTS
# ---------------------------------------------------------------------

teacher = "app/routes/teacher.py"
text = load(teacher)

old = '''    hire = HireRequest.query.filter_by(id=hire_id, teacher_id=profile.id).first_or_404()
    hire.status = HireStatus.ACCEPTED
'''

new = '''    hire = HireRequest.query.filter_by(
        id=hire_id,
        teacher_id=profile.id,
        status=HireStatus.PENDING,
    ).first_or_404()

    hire.status = HireStatus.ACCEPTED
'''

if old in text:
    save(teacher, text.replace(old, new, 1))
    print("[PATCH] teacher.py -> accept only pending hires")
else:
    skipped.append("teacher.py: accept pending validation (pattern not found/already patched)")

text = load(teacher)

old = '''    hire = HireRequest.query.filter_by(id=hire_id, teacher_id=profile.id).first_or_404()
    hire.status = HireStatus.REJECTED
'''

new = '''    hire = HireRequest.query.filter_by(
        id=hire_id,
        teacher_id=profile.id,
        status=HireStatus.PENDING,
    ).first_or_404()

    hire.status = HireStatus.REJECTED
'''

if old in text:
    save(teacher, text.replace(old, new, 1))
    print("[PATCH] teacher.py -> reject only pending hires")
else:
    skipped.append("teacher.py: reject pending validation (pattern not found/already patched)")

# ---------------------------------------------------------------------
# 6. STUDENT: HIRE FORM MUST ACTUALLY VALIDATE
# ---------------------------------------------------------------------

student = "app/routes/student.py"
text = load(student)

old = '''    form = HireRequestForm()
    hire = HireRequest(
        student_id=profile.id,
        teacher_id=teacher.id,
        message=form.message.data if form.message.data else request.form.get("message", "").strip(),
        status=HireStatus.PENDING,
    )
'''

new = '''    form = HireRequestForm()

    if not form.validate_on_submit():
        flash("Invalid hire request.", "danger")
        return redirect(url_for("student.teacher_search"))

    hire = HireRequest(
        student_id=profile.id,
        teacher_id=teacher.id,
        message=(form.message.data or "").strip(),
        status=HireStatus.PENDING,
    )
'''

if old in text:
    save(student, text.replace(old, new, 1))
    print("[PATCH] student.py -> hire form validation")
else:
    skipped.append("student.py: hire form validation (pattern not found/already patched)")

# ---------------------------------------------------------------------
# 7. STUDENT: ONLY APPROVED + AVAILABLE TEACHERS CAN RECEIVE PAYMENT
# ---------------------------------------------------------------------

text = load(student)

old = '''        teacher = TeacherProfile.query.get(form.teacher_id.data)
        if not teacher or teacher.id not in [t.id for t in hired_teachers]:
'''

new = '''        teacher = TeacherProfile.query.get(form.teacher_id.data)
        if (
            not teacher
            or teacher.id not in [t.id for t in hired_teachers]
            or teacher.status != TeacherStatus.APPROVED
            or not teacher.is_available
        ):
'''

if old in text:
    save(student, text.replace(old, new, 1))
    print("[PATCH] student.py -> payment teacher validation")
else:
    skipped.append("student.py: payment teacher validation (pattern not found/already patched)")

# ---------------------------------------------------------------------
# 8. PAYMENT: TRANSACTION ID SHOULD BE NORMALIZED
# ---------------------------------------------------------------------

text = load(student)

old = '''            transaction_id=form.transaction_id.data.strip(),
'''

new = '''            transaction_id=(form.transaction_id.data or "").strip()[:120],
'''

if old in text:
    save(student, text.replace(old, new, 1))
    print("[PATCH] student.py -> transaction ID normalization")
else:
    skipped.append("student.py: transaction ID normalization (pattern not found/already patched)")

# ---------------------------------------------------------------------
# 9. FINAL SYNTAX CHECK
# ---------------------------------------------------------------------

print()
print("=" * 70)
print("FINAL SYNTAX CHECK")
print("=" * 70)

errors = []

for rel in existing:
    p = ROOT / rel

    try:
        ast.parse(p.read_text(encoding="utf-8"))
        print(f"[OK] {rel}")
    except SyntaxError as e:
        errors.append((rel, e))
        print(f"[ERROR] {rel}: {e}")

# ---------------------------------------------------------------------
# 10. ROLLBACK IF ANY SYNTAX ERROR
# ---------------------------------------------------------------------

if errors:
    print()
    print("=" * 70)
    print("SYNTAX ERROR — AUTOMATIC ROLLBACK")
    print("=" * 70)

    for rel, _ in errors:
        src = BACKUP / rel
        dst = ROOT / rel

        if src.exists():
            shutil.copy2(src, dst)
            print(f"[ROLLBACK] {rel}")

    print()
    print("No broken patch has been left in the project.")
    sys.exit(1)

# ---------------------------------------------------------------------
# 11. REPORT
# ---------------------------------------------------------------------

report = ROOT / f"SECURITY_PATCH_REPORT_{stamp}.txt"

with report.open("w", encoding="utf-8") as f:
    f.write("LOCAL TUTOR SECURITY PATCH REPORT\n")
    f.write("=" * 60 + "\n")
    f.write(f"Time: {datetime.now().isoformat()}\n")
    f.write(f"Backup: {BACKUP}\n\n")

    f.write("MODIFIED FILES\n")
    f.write("-" * 60 + "\n")
    for item in changed:
        f.write(f"{item}\n")

    f.write("\nSKIPPED / NOT APPLICABLE\n")
    f.write("-" * 60 + "\n")
    for item in skipped:
        f.write(f"{item}\n")

print()
print("=" * 70)
print("PATCH COMPLETE")
print("=" * 70)
print(f"Modified files : {len(changed)}")
print(f"Skipped items  : {len(skipped)}")
print(f"Backup         : {BACKUP}")
print(f"Report         : {report}")
print()
print("IMPORTANT: Database migrations/tests have NOT been run automatically.")
print("The source tree passed the final Python syntax check.")
