from pathlib import Path
from datetime import datetime
import shutil
import re

ROOT = Path(".")
USER_FILE = ROOT / "app/models/user.py"
AUTH_FILE = ROOT / "app/routes/auth.py"
VERSIONS = ROOT / "migrations/versions"
BACKUP = ROOT / f"BACKUP_REFERRAL_RELATIONSHIP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print("=" * 75)
print("AUTOMATIC REFERRAL RELATIONSHIP PATCH")
print("=" * 75)

if not USER_FILE.exists():
    raise SystemExit("[ERROR] app/models/user.py not found")

if not AUTH_FILE.exists():
    raise SystemExit("[ERROR] app/routes/auth.py not found")

BACKUP.mkdir(parents=True)

# ------------------------------------------------------------
# BACKUP
# ------------------------------------------------------------
for src in [USER_FILE, AUTH_FILE]:
    dst = BACKUP / src
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

print(f"[BACKUP] {BACKUP}")

# ------------------------------------------------------------
# USER MODEL
# ------------------------------------------------------------
text = USER_FILE.read_text()

# Find referral_code field robustly
ref_match = re.search(
    r'(?m)^\s*referral_code\s*=\s*db\.Column\([^\n]+\)\s*$',
    text
)

if "referred_by_id = db.Column(" not in text:
    if not ref_match:
        raise SystemExit(
            "[ERROR] Could not locate referral_code field in User model"
        )

    line = ref_match.group(0)

    addition = line + """

    # Optional self-referencing referral relationship.
    # NULL means the account was registered without a referral.
    referred_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    referred_by = db.relationship(
        "User",
        remote_side="User.id",
        foreign_keys=[referred_by_id],
        backref=db.backref(
            "referred_users",
            lazy="dynamic",
        ),
    )
"""

    text = text[:ref_match.start()] + addition + text[ref_match.end():]
    USER_FILE.write_text(text)

    print("[OK] User.referred_by_id added")
    print("[OK] User.referred_by added")
    print("[OK] User.referred_users added")
else:
    print("[OK] User referral relationship already present")

# ------------------------------------------------------------
# AUTH REGISTRATION LINK
# ------------------------------------------------------------
auth = AUTH_FILE.read_text()

# We need both registration functions to actually save the referrer.
# Detect places where get_referrer() is called.

changed_auth = False

# Student:
# Existing pattern normally:
# referrer = get_referrer(form.referral_code.data)
# if form.referral_code.data and not referrer:
# ...
#
# Add referred_by_id assignment after validation.

student_pattern = re.compile(
    r'(referrer\s*=\s*get_referrer\(form\.referral_code\.data\)\s*\n'
    r'\s*if\s+form\.referral_code\.data\s+and\s+not\s+referrer:\s*\n'
    r'\s*flash\("Invalid referral code\.",\s*"danger"\)\s*\n'
    r'\s*return\s+render_template\([^\n]+\)\s*)',
    re.MULTILINE
)

# We do not blindly modify because render_template arguments can differ.
# Instead ensure assignment exists after user object creation.

if "user.referred_by_id = referrer.id" not in auth:
    # Find first occurrence of a user creation block followed by referral_code.
    matches = list(re.finditer(
        r'(?s)(user\s*=\s*User\(\s*.*?\n\s*\))',
        auth
    ))

    if matches:
        # We need to distinguish student and teacher.
        # Insert after referral_code generation for each user.
        occurrences = [
            m for m in re.finditer(
                r'(?m)^\s*user\.referral_code\s*=\s*generate_referral_code\(\)\s*$',
                auth
            )
        ]

        if occurrences:
            # Work backwards so offsets remain valid.
            for m in reversed(occurrences):
                after = auth[m.end():]

                # Only add if this registration block has a referrer variable.
                # Stop before next route.
                next_route = re.search(
                    r'\n@auth_bp\.route',
                    after
                )
                block = after[:next_route.start()] if next_route else after

                if "referrer" in block:
                    insertion = """

        # Persist the referral relationship when a valid referral
        # code was supplied.
        if referrer:
            user.referred_by_id = referrer.id
"""
                    auth = auth[:m.end()] + insertion + auth[m.end():]
                    changed_auth = True

if changed_auth:
    AUTH_FILE.write_text(auth)
    print("[OK] Registration now persists referred_by_id")
else:
    if "user.referred_by_id = referrer.id" in auth:
        print("[OK] Registration referral linkage already present")
    else:
        print("[WARN] Could not safely auto-insert referral linkage")
        print("       Model/database patch will still be applied.")

# ------------------------------------------------------------
# CREATE MIGRATION
# ------------------------------------------------------------
existing = []

for f in VERSIONS.glob("*.py"):
    if f.name.startswith("__"):
        continue

    t = f.read_text(errors="ignore")
    m = re.search(
        r'(?m)^\s*revision\s*=\s*[\'"]([^\'"]+)[\'"]',
        t
    )
    if m:
        existing.append((m.group(1), f))

# Current known head
down_revision = "20260827_004132"

# Avoid duplicate migration
already = False

for rev, f in existing:
    if "referred_by_id" in f.read_text(errors="ignore"):
        already = True
        print(f"[OK] Referral relationship migration already exists: {f.name}")

if not already:
    revision = datetime.now().strftime("%Y%m%d_%H%M%S") + "_add_user_referral_relationship"
    migration = VERSIONS / f"{revision}.py"

    migration.write_text(f'''"""add user referral relationship

Revision ID: {revision}
Revises: {down_revision}
"""

from alembic import op
import sqlalchemy as sa


revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite requires batch_alter_table for safe table alteration.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "referred_by_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_users_referred_by_id",
            ["referred_by_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_users_referred_by_id_users",
            "users",
            ["referred_by_id"],
            ["users.id"],
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_users_referred_by_id_users",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_users_referred_by_id",
        )

        batch_op.drop_column("referred_by_id")
''')

    print(f"[OK] Created migration: {migration}")

print()
print("=" * 75)
print("PATCH COMPLETE")
print("=" * 75)
print(f"Backup: {BACKUP}")
