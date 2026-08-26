#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import re
import sys

ROOT = Path.cwd()

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"BACKUP_REFERRAL_SLOTS_{STAMP}"

def die(msg):
    print("\n[ERROR]", msg)
    sys.exit(1)

def backup(path):
    if path.exists():
        dest = BACKUP / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)

def read(path):
    return path.read_text(encoding="utf-8")

def write(path, text):
    path.write_text(text, encoding="utf-8")

def replace_once(path, old, new, label):
    text = read(path)

    if new in text:
        print(f"[SKIP] {label} already present")
        return

    if old not in text:
        die(f"Could not find patch location for: {label}")

    backup(path)
    text = text.replace(old, new, 1)
    write(path, text)
    print(f"[OK] {label}")

print("=" * 70)
print("AUTOMATED REFERRAL + TIME SLOT PATCH")
print("=" * 70)

required = [
    ROOT / "app/forms/auth_forms.py",
    ROOT / "app/routes/auth.py",
    ROOT / "app/models/user.py",
    ROOT / "app/models/teacher_profile.py",
    ROOT / "app/models/student_profile.py",
    ROOT / "app/templates/auth/register_teacher.html",
    ROOT / "app/templates/auth/register_student.html",
]

for p in required:
    if not p.exists():
        die(f"Required file missing: {p}")

BACKUP.mkdir(parents=True, exist_ok=True)

print(f"\n[BACKUP] {BACKUP}")

# ============================================================
# 1. USER MODEL
# ============================================================

user = ROOT / "app/models/user.py"

replace_once(
    user,
    '    last_login_at = db.Column(db.DateTime, nullable=True)\n',
    '''    last_login_at = db.Column(db.DateTime, nullable=True)

    # Referral system
    referral_code = db.Column(
        db.String(32),
        unique=True,
        nullable=True,
        index=True,
    )

    referred_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    referred_by = db.relationship(
        "User",
        remote_side=[id],
        foreign_keys=[referred_by_user_id],
        backref=db.backref("referrals", lazy="dynamic"),
    )
''',
    "User referral fields"
)

# ============================================================
# 2. AVAILABILITY MODELS
# ============================================================

teacher_av = ROOT / "app/models/teacher_availability.py"

if not teacher_av.exists():
    teacher_av.write_text(
'''from app import db


class TeacherAvailabilitySlot(db.Model):
    __tablename__ = "teacher_availability_slots"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teacher_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ISO weekday: 0=Monday ... 6=Sunday
    weekday = db.Column(db.Integer, nullable=False)

    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    teacher = db.relationship(
        "TeacherProfile",
        back_populates="availability_slots",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_teacher_availability_slot",
        ),
        db.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_teacher_availability_weekday",
        ),
    )

    def __repr__(self):
        return (
            f"<TeacherAvailabilitySlot "
            f"teacher={self.teacher_id} "
            f"weekday={self.weekday} "
            f"{self.start_time}-{self.end_time}>"
        )
''',
        encoding="utf-8",
    )
    print("[OK] Created teacher_availability.py")
else:
    print("[SKIP] teacher_availability.py already exists")

student_av = ROOT / "app/models/student_availability.py"

if not student_av.exists():
    student_av.write_text(
'''from app import db


class StudentAvailabilitySlot(db.Model):
    __tablename__ = "student_availability_slots"

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ISO weekday: 0=Monday ... 6=Sunday
    weekday = db.Column(db.Integer, nullable=False)

    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    student = db.relationship(
        "StudentProfile",
        back_populates="availability_slots",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_student_availability_slot",
        ),
        db.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_student_availability_weekday",
        ),
    )

    def __repr__(self):
        return (
            f"<StudentAvailabilitySlot "
            f"student={self.student_id} "
            f"weekday={self.weekday} "
            f"{self.start_time}-{self.end_time}>"
        )
''',
        encoding="utf-8",
    )
    print("[OK] Created student_availability.py")
else:
    print("[SKIP] student_availability.py already exists")

# ============================================================
# 3. PROFILE RELATIONSHIPS
# ============================================================

teacher_profile = ROOT / "app/models/teacher_profile.py"

replace_once(
    teacher_profile,
    '    wallet = db.relationship("Wallet", back_populates="teacher_profile", uselist=False, cascade="all, delete-orphan")\n',
    '''    wallet = db.relationship(
        "Wallet",
        back_populates="teacher_profile",
        uselist=False,
        cascade="all, delete-orphan",
    )

    availability_slots = db.relationship(
        "TeacherAvailabilitySlot",
        back_populates="teacher",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
''',
    "Teacher availability relationship"
)

student_profile = ROOT / "app/models/student_profile.py"

replace_once(
    student_profile,
    '    user = db.relationship("User", back_populates="student_profile", foreign_keys=[user_id])\n',
    '''    user = db.relationship(
        "User",
        back_populates="student_profile",
        foreign_keys=[user_id],
    )

    availability_slots = db.relationship(
        "StudentAvailabilitySlot",
        back_populates="student",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
''',
    "Student availability relationship"
)

# ============================================================
# 4. MODEL IMPORTS
# ============================================================

models_init = ROOT / "app/models/__init__.py"

existing = read(models_init)

imports = [
    "from app.models.teacher_availability import TeacherAvailabilitySlot",
    "from app.models.student_availability import StudentAvailabilitySlot",
]

for imp in imports:
    if imp not in existing:
        backup(models_init)
        existing += "\n" + imp + "\n"

write(models_init, existing)
print("[OK] Registered availability models")

# ============================================================
# 5. FORM HELPERS + FIELDS
# ============================================================

forms = ROOT / "app/forms/auth_forms.py"

replace_once(
    forms,
    'from wtforms.validators import (\n    DataRequired, Email, Length, EqualTo, NumberRange, Regexp, Optional\n)\n',
    '''from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, NumberRange, Regexp, Optional
)

import json
import re


TIME_SLOT_PATTERN = re.compile(
    r"^\\\\d{1,2}:\\\\d{2}-\\\\d{1,2}:\\\\d{2}$"
)


def validate_availability_json(form, field):
    value = (field.data or "").strip()

    if not value:
        return

    try:
        slots = json.loads(value)
    except (TypeError, ValueError):
        raise ValueError("Invalid availability data.")

    if not isinstance(slots, list):
        raise ValueError("Availability must be a list.")

    if len(slots) > 50:
        raise ValueError("Maximum 50 availability slots are allowed.")

    seen = set()

    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError("Invalid availability slot.")

        weekday = slot.get("weekday")
        start = slot.get("start")
        end = slot.get("end")

        if not isinstance(weekday, int) or not 0 <= weekday <= 6:
            raise ValueError("Invalid weekday.")

        if not isinstance(start, str) or not isinstance(end, str):
            raise ValueError("Invalid slot time.")

        if not re.match(r"^([01]\\\\d|2[0-3]):[0-5]\\\\d$", start):
            raise ValueError("Invalid start time.")

        if not re.match(r"^([01]\\\\d|2[0-3]):[0-5]\\\\d$", end):
            raise ValueError("Invalid end time.")

        if start >= end:
            raise ValueError("Slot end time must be after start time.")

        key = (weekday, start, end)

        if key in seen:
            raise ValueError("Duplicate availability slot.")

        seen.add(key)
''',
    "availability validator"
)

replace_once(
    forms,
    '    subjects_required = StringField("Subjects Required (comma separated)", validators=[DataRequired(), Length(max=500)])\n',
    '''    subjects_required = StringField(
        "Subjects Required (comma separated)",
        validators=[DataRequired(), Length(max=500)],
    )

    referral_code = StringField(
        "Referral Code",
        validators=[Optional(), Length(max=32)],
    )

    availability_json = StringField(
        "Preferred Availability",
        validators=[Optional(), validate_availability_json],
    )
''',
    "Student referral and availability fields"
)

replace_once(
    forms,
    '    bank_name = StringField("Bank Name", validators=[Optional(), Length(max=120)])\n',
    '''    bank_name = StringField(
        "Bank Name",
        validators=[Optional(), Length(max=120)],
    )

    referral_code = StringField(
        "Referral Code",
        validators=[Optional(), Length(max=32)],
    )

    availability_json = StringField(
        "Teaching Availability",
        validators=[Optional(), validate_availability_json],
    )
''',
    "Teacher referral and availability fields"
)

# ============================================================
# 6. AUTH ROUTE IMPORTS
# ============================================================

auth = ROOT / "app/routes/auth.py"

replace_once(
    auth,
    'from datetime import datetime\n',
    '''from datetime import datetime
import json
import secrets
import string
''',
    "auth helper imports"
)

replace_once(
    auth,
    'from app.models.audit_log import AuditLog\n',
    '''from app.models.audit_log import AuditLog
from app.models.teacher_availability import TeacherAvailabilitySlot
from app.models.student_availability import StudentAvailabilitySlot
''',
    "availability route imports"
)

# ============================================================
# 7. HELPER FUNCTIONS
# ============================================================

marker = '@auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")'

# actual source contains auth_bp, not auth_bp =? 
marker = 'auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")'

helper = '''
def generate_referral_code():
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(20):
        code = "RTK-" + "".join(secrets.choice(alphabet) for _ in range(8))

        if not User.query.filter_by(referral_code=code).first():
            return code

    raise RuntimeError("Unable to generate a unique referral code.")


def get_referrer(referral_code):
    code = (referral_code or "").strip().upper()

    if not code:
        return None

    return User.query.filter_by(referral_code=code).first()


def save_student_slots(profile, availability_json):
    if not availability_json:
        return

    slots = json.loads(availability_json)

    for slot in slots:
        db.session.add(
            StudentAvailabilitySlot(
                student_id=profile.id,
                weekday=slot["weekday"],
                start_time=slot["start"],
                end_time=slot["end"],
            )
        )


def save_teacher_slots(profile, availability_json):
    if not availability_json:
        return

    slots = json.loads(availability_json)

    for slot in slots:
        db.session.add(
            TeacherAvailabilitySlot(
                teacher_id=profile.id,
                weekday=slot["weekday"],
                start_time=slot["start"],
                end_time=slot["end"],
            )
        )


'''

if helper.strip() not in read(auth):
    text = read(auth)

    if marker not in text:
        die("Could not find auth blueprint declaration")

    backup(auth)
    text = text.replace(marker, marker + "\n" + helper, 1)
    write(auth, text)

    print("[OK] Added referral/slot helpers")
else:
    print("[SKIP] referral/slot helpers already present")

# ============================================================
# 8. STUDENT REGISTRATION PATCH
# ============================================================

auth_text = read(auth)

old = '''        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.STUDENT,
        )
'''

new = '''        referrer = get_referrer(form.referral_code.data)

        if form.referral_code.data and not referrer:
            flash("Invalid referral code.", "danger")
            return render_template("auth/register_student.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.STUDENT,
            referred_by=referrer,
        )
'''

if new not in auth_text:
    if old not in auth_text:
        die("Student User creation block not found")

    backup(auth)
    auth_text = auth_text.replace(old, new, 1)
    write(auth, auth_text)
    print("[OK] Student referral validation")

auth_text = read(auth)

old = '''        profile = StudentProfile(
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
'''

new = '''        profile = StudentProfile(
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

        # Generate the user's own referral code after the ID exists.
        db.session.flush()
        user.referral_code = generate_referral_code()

        save_student_slots(profile, form.availability_json.data)

        db.session.commit()
'''

if new not in auth_text:
    if old not in auth_text:
        die("Student profile block not found")

    backup(auth)
    auth_text = auth_text.replace(old, new, 1)
    write(auth, auth_text)
    print("[OK] Student availability persistence")

# ============================================================
# 9. TEACHER REGISTRATION PATCH
# ============================================================

auth_text = read(auth)

old = '''        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.TEACHER,
        )
'''

new = '''        referrer = get_referrer(form.referral_code.data)

        if form.referral_code.data and not referrer:
            flash("Invalid referral code.", "danger")
            return render_template("auth/register_teacher.html", form=form)

        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            mobile=form.mobile.data.strip(),
            role=RoleEnum.TEACHER,
            referred_by=referrer,
        )
'''

if new not in auth_text:
    if old not in auth_text:
        die("Teacher User creation block not found")

    backup(auth)
    auth_text = auth_text.replace(old, new, 1)
    write(auth, auth_text)
    print("[OK] Teacher referral validation")

auth_text = read(auth)

old = '''        db.session.add(profile)
        db.session.flush()

        wallet = Wallet(teacher_id=profile.id)
'''

new = '''        db.session.add(profile)
        db.session.flush()

        # Generate referral code only after user has a database ID.
        user.referral_code = generate_referral_code()

        save_teacher_slots(profile, form.availability_json.data)

        wallet = Wallet(teacher_id=profile.id)
'''

if new not in auth_text:
    if old not in auth_text:
        die("Teacher profile persistence block not found")

    backup(auth)
    auth_text = auth_text.replace(old, new, 1)
    write(auth, auth_text)
    print("[OK] Teacher availability persistence")

# ============================================================
# 10. MIGRATION
# ============================================================

migration = ROOT / f"migrations/versions/{STAMP}_add_referral_and_availability.py"

if not migration.exists():
    migration.write_text(
f'''"""Add referral system and recurring availability slots.

Revision ID: {STAMP}
Revises: 75364882518b
"""

from alembic import op
import sqlalchemy as sa


revision = "{STAMP}"
down_revision = "75364882518b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "referral_code",
                sa.String(length=32),
                nullable=True,
            )
        )

        batch_op.add_column(
            sa.Column(
                "referred_by_user_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_users_referral_code",
            ["referral_code"],
            unique=True,
        )

        batch_op.create_index(
            "ix_users_referred_by_user_id",
            ["referred_by_user_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_users_referred_by_user_id_users",
            "users",
            ["referred_by_user_id"],
            ["id"],
        )

    op.create_table(
        "teacher_availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["teacher_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "teacher_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_teacher_availability_slot",
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_teacher_availability_weekday",
        ),
    )

    op.create_index(
        "ix_teacher_availability_slots_teacher_id",
        "teacher_availability_slots",
        ["teacher_id"],
    )

    op.create_table(
        "student_availability_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["student_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "student_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_student_availability_slot",
        ),
        sa.CheckConstraint(
            "weekday >= 0 AND weekday <= 6",
            name="ck_student_availability_weekday",
        ),
    )

    op.create_index(
        "ix_student_availability_slots_student_id",
        "student_availability_slots",
        ["student_id"],
    )


def downgrade():
    op.drop_index(
        "ix_student_availability_slots_student_id",
        table_name="student_availability_slots",
    )
    op.drop_table("student_availability_slots")

    op.drop_index(
        "ix_teacher_availability_slots_teacher_id",
        table_name="teacher_availability_slots",
    )
    op.drop_table("teacher_availability_slots")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_users_referred_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_users_referred_by_user_id")
        batch_op.drop_index("ix_users_referral_code")
        batch_op.drop_column("referred_by_user_id")
        batch_op.drop_column("referral_code")
''',
        encoding="utf-8",
    )

    print(f"[OK] Created migration: {migration.name}")
else:
    print("[SKIP] Migration already exists")

# ============================================================
# 11. REGISTRATION FRONTEND COMPONENT
# ============================================================

component = r'''
<!-- Referral + Availability -->
<div class="card border-0 shadow-sm rounded-4 mt-4">
  <div class="card-body p-4">

    <h5 class="fw-bold mb-3">
      <i class="bi bi-people me-2"></i>
      Referral
    </h5>

    <label class="form-label">Referral Code <span class="text-muted">(optional)</span></label>
    {{ form.referral_code(class="form-control", placeholder="Example: RTK-AB12CD34") }}

    <hr class="my-4">

    <h5 class="fw-bold mb-2">
      <i class="bi bi-clock me-2"></i>
      Availability
    </h5>

    <p class="text-muted small mb-3">
      Add the days and times when you are normally available.
      You can add multiple slots.
    </p>

    {{ form.availability_json(type="hidden", id="availability_json") }}

    <div id="availabilityRows"></div>

    <button type="button"
            class="btn btn-outline-primary btn-sm rounded-pill"
            id="addAvailabilitySlot">
      <i class="bi bi-plus-circle me-1"></i>
      Add Time Slot
    </button>

    <div class="small text-muted mt-3">
      Example: Monday 5:00 PM – 6:00 PM
    </div>

  </div>
</div>

<script>
(function () {
  const hidden = document.getElementById("availability_json");
  const rows = document.getElementById("availabilityRows");
  const addBtn = document.getElementById("addAvailabilitySlot");

  if (!hidden || !rows || !addBtn) return;

  const days = [
    ["0", "Monday"],
    ["1", "Tuesday"],
    ["2", "Wednesday"],
    ["3", "Thursday"],
    ["4", "Friday"],
    ["5", "Saturday"],
    ["6", "Sunday"]
  ];

  function createTimeOptions() {
    let html = '<option value="">Time</option>';

    for (let h = 0; h < 24; h++) {
      for (const m of [0, 30]) {
        const hh = String(h).padStart(2, "0");
        const mm = String(m).padStart(2, "0");
        const value = hh + ":" + mm;

        let hour = h % 12 || 12;
        let suffix = h < 12 ? "AM" : "PM";

        html += '<option value="' + value + '">' +
          hour + ":" + mm + " " + suffix +
          "</option>";
      }
    }

    return html;
  }

  function addRow(data) {
    data = data || {};

    const row = document.createElement("div");
    row.className = "row g-2 align-items-end mb-2 availability-row";

    let dayOptions = '<option value="">Day</option>';

    days.forEach(function (day) {
      const selected =
        String(data.weekday) === day[0] ? " selected" : "";

      dayOptions +=
        '<option value="' + day[0] + '"' + selected + '>' +
        day[1] +
        "</option>";
    });

    row.innerHTML = `
      <div class="col-12 col-md-4">
        <label class="form-label small">Day</label>
        <select class="form-select slot-day">
          ${dayOptions}
        </select>
      </div>

      <div class="col-5 col-md-3">
        <label class="form-label small">Start</label>
        <select class="form-select slot-start">
          ${createTimeOptions()}
        </select>
      </div>

      <div class="col-5 col-md-3">
        <label class="form-label small">End</label>
        <select class="form-select slot-end">
          ${createTimeOptions()}
        </select>
      </div>

      <div class="col-2 col-md-2">
        <button type="button"
                class="btn btn-outline-danger w-100 remove-slot"
                aria-label="Remove slot">
          <i class="bi bi-trash"></i>
        </button>
      </div>
    `;

    row.querySelector(".slot-start").value = data.start || "";
    row.querySelector(".slot-end").value = data.end || "";

    row.querySelector(".remove-slot").addEventListener("click", function () {
      row.remove();
      sync();
    });

    ["change", "input"].forEach(function (eventName) {
      row.addEventListener(eventName, sync);
    });

    rows.appendChild(row);
  }

  function sync() {
    const slots = [];

    rows.querySelectorAll(".availability-row").forEach(function (row) {
      const day = row.querySelector(".slot-day").value;
      const start = row.querySelector(".slot-start").value;
      const end = row.querySelector(".slot-end").value;

      if (day !== "" && start !== "" && end !== "") {
        slots.push({
          weekday: Number(day),
          start: start,
          end: end
        });
      }
    });

    hidden.value = JSON.stringify(slots);
  }

  addBtn.addEventListener("click", function () {
    addRow();
  });

  try {
    const existing = JSON.parse(hidden.value || "[]");

    if (Array.isArray(existing)) {
      existing.forEach(addRow);
    }
  } catch (e) {
    console.warn("Could not restore availability slots");
  }
})();
</script>
'''

teacher_template = ROOT / "app/templates/auth/register_teacher.html"
student_template = ROOT / "app/templates/auth/register_student.html"

# Insert before submit button in each template.
for template, label in [
    (teacher_template, "teacher"),
    (student_template, "student"),
]:
    text = read(template)

    if 'id="availabilityRows"' in text:
        print(f"[SKIP] {label} registration availability UI already present")
        continue

    backup(template)

    submit_marker = '<button type="submit"'
    pos = text.find(submit_marker)

    if pos == -1:
        die(f"Submit button not found in {template}")

    text = text[:pos] + component + "\n" + text[pos:]

    write(template, text)

    print(f"[OK] {label} registration referral + availability UI")

# ============================================================
# FINISH
# ============================================================

print("\n" + "=" * 70)
print("PATCH COMPLETE")
print("=" * 70)

print(f"""
Backup:
  {BACKUP}

Next commands:

  python -m compileall -q app

  flask db upgrade

  flask db current

  flask db heads

Then run:

  pytest -q

If pytest says 'no tests ran', that means this repository currently
contains no pytest-discoverable tests; the application itself is not
automatically proven correct by that result.
""")
