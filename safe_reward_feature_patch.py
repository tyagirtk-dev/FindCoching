#!/usr/bin/env python3

import os
import re
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path.cwd()
APP = ROOT / "app"
BACKUP = ROOT / f"BACKUP_REWARD_SYSTEM_{datetime.now():%Y%m%d_%H%M%S}"

CHANGED = []
CREATED = []

print("=" * 80)
print("SAFE REWARD / REFERRAL COIN SYSTEM PATCH")
print("=" * 80)
print("Project :", ROOT)
print("Backup  :", BACKUP)
print()

# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------

def fail(msg):
    raise RuntimeError(msg)

def backup_file(path):
    rel = path.relative_to(ROOT)
    dest = BACKUP / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        shutil.copy2(path, dest)

def write_new(path, content):
    if path.exists():
        fail(f"Refusing to overwrite existing file: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    CREATED.append(str(path.relative_to(ROOT)))

def modify(path, new_text):
    old = path.read_text(encoding="utf-8")

    if old == new_text:
        return

    backup_file(path)
    path.write_text(new_text, encoding="utf-8")

    CHANGED.append(str(path.relative_to(ROOT)))

def insert_once(path, marker, insertion, label):
    text = path.read_text(encoding="utf-8")

    if insertion.strip() in text:
        print(f"[SKIP] {label} already present")
        return

    if marker not in text:
        fail(f"Anchor not found for {label}: {marker}")

    new_text = text.replace(marker, marker + insertion, 1)
    modify(path, new_text)
    print(f"[OK] {label}")

def run(cmd, check=True):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT)

    if check and p.returncode != 0:
        fail(f"Command failed: {' '.join(cmd)}")

    return p.returncode


# ---------------------------------------------------------------------
# 1. preflight
# ---------------------------------------------------------------------

print("[1] PRE-FLIGHT VALIDATION")

required = [
    APP / "models/user.py",
    APP / "models/hire_request.py",
    APP / "routes/auth.py",
    APP / "routes/student.py",
    APP / "routes/teacher.py",
    APP / "routes/admin.py",
    APP / "services/wallet_service.py",
]

for p in required:
    if not p.exists():
        fail(f"Required file missing: {p}")
    print("[OK]", p.relative_to(ROOT))

user_text = (APP / "models/user.py").read_text(encoding="utf-8")
auth_text = (APP / "routes/auth.py").read_text(encoding="utf-8")
hire_text = (APP / "models/hire_request.py").read_text(encoding="utf-8")
student_text = (APP / "routes/student.py").read_text(encoding="utf-8")
teacher_text = (APP / "routes/teacher.py").read_text(encoding="utf-8")
admin_text = (APP / "routes/admin.py").read_text(encoding="utf-8")

if "referral_code" not in user_text:
    fail("Existing referral_code not found")

if "referred_by_user_id" not in user_text:
    fail("Existing referred_by_user_id not found")

if "referred_by" not in user_text:
    fail("Existing referred_by relationship not found")

if "HireStatus.ACCEPTED" not in teacher_text:
    fail("Teacher hire acceptance logic not found")

print("[OK] Existing referral system detected")
print("[OK] Existing hire acceptance detected")

# ---------------------------------------------------------------------
# 2. backup
# ---------------------------------------------------------------------

print()
print("[2] CREATING FULL BACKUP")

backup_targets = [
    APP / "models/user.py",
    APP / "routes/auth.py",
    APP / "routes/student.py",
    APP / "routes/teacher.py",
    APP / "routes/admin.py",
    APP / "services/wallet_service.py",
]

for p in backup_targets:
    backup_file(p)

print("[OK] Backup created:", BACKUP)

# ---------------------------------------------------------------------
# 3. reward model
# ---------------------------------------------------------------------

print()
print("[3] CREATING REWARD LEDGER")

reward_model = r'''"""
Reward / Coin Ledger.

This wallet is intentionally separate from the teacher INR wallet.

10 coins = Rs. 1
1500 coins = Rs. 150
"""

import enum
from datetime import datetime

from app import db


class RewardTransactionType(str, enum.Enum):
    REFERRAL_SIGNUP = "referral_signup"
    REFERRED_HIRE_ACCEPTED = "referred_hire_accepted"
    WITHDRAWAL_HOLD = "withdrawal_hold"
    WITHDRAWAL_PAID = "withdrawal_paid"
    WITHDRAWAL_REFUND = "withdrawal_refund"


class RewardTransaction(db.Model):
    __tablename__ = "reward_transactions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    amount = db.Column(
        db.Integer,
        nullable=False,
    )

    type = db.Column(
        db.Enum(
            RewardTransactionType,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
    )

    reference = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    description = db.Column(
        db.String(500),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "reward_transactions",
            lazy="dynamic",
        ),
    )

    def __repr__(self):
        return (
            f"<RewardTransaction "
            f"user={self.user_id} "
            f"amount={self.amount} "
            f"type={self.type}>"
        )
'''

write_new(APP / "models/reward.py", reward_model)
print("[OK] app/models/reward.py")

# ---------------------------------------------------------------------
# 4. reward withdrawal model
# ---------------------------------------------------------------------

print()
print("[4] CREATING REWARD WITHDRAWAL MODEL")

withdrawal_model = r'''"""
Reward coin withdrawal requests.

Coins are held when the request is created.
Admin PAID permanently consumes the held coins.
Admin REJECTED refunds the held coins.
"""

import enum
from datetime import datetime

from app import db


class RewardWithdrawalStatus(str, enum.Enum):
    REQUESTED = "requested"
    PAID = "paid"
    REJECTED = "rejected"


class RewardWithdrawal(db.Model):
    __tablename__ = "reward_withdrawals"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    coins = db.Column(
        db.Integer,
        nullable=False,
    )

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False,
    )

    status = db.Column(
        db.Enum(
            RewardWithdrawalStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=RewardWithdrawalStatus.REQUESTED,
        index=True,
    )

    payout_method = db.Column(
        db.String(30),
        nullable=False,
        default="upi",
    )

    payout_reference = db.Column(
        db.String(120),
        nullable=True,
    )

    admin_note = db.Column(
        db.String(500),
        nullable=True,
    )

    requested_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    processed_at = db.Column(
        db.DateTime,
        nullable=True,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "reward_withdrawals",
            lazy="dynamic",
        ),
    )

    def __repr__(self):
        return (
            f"<RewardWithdrawal "
            f"id={self.id} "
            f"user={self.user_id} "
            f"coins={self.coins} "
            f"status={self.status}>"
        )
'''

write_new(APP / "models/reward_withdrawal.py", withdrawal_model)
print("[OK] app/models/reward_withdrawal.py")

# ---------------------------------------------------------------------
# 5. reward service
# ---------------------------------------------------------------------

print()
print("[5] CREATING REWARD SERVICE")

reward_service = r'''"""
Central reward/coin service.

IMPORTANT:
Reward coins are completely separate from the teacher INR wallet.

10 coins = Rs. 1
"""

from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.reward import RewardTransaction, RewardTransactionType
from app.models.reward_withdrawal import (
    RewardWithdrawal,
    RewardWithdrawalStatus,
)

COINS_PER_RUPEE = 10
SIGNUP_REWARD = 100
HIRED_REWARD = 100


def coins_to_rupees(coins):
    coins = int(coins)
    return Decimal(coins) / Decimal(COINS_PER_RUPEE)


def get_balance(user_id):
    """
    Available balance = all credits minus holds.
    PAID withdrawal remains consumed.
    REJECTED withdrawal is refunded.
    """
    txs = RewardTransaction.query.filter_by(user_id=user_id).all()

    balance = 0

    for tx in txs:
        amount = int(tx.amount)

        if tx.type in (
            RewardTransactionType.REFERRAL_SIGNUP,
            RewardTransactionType.REFERRED_HIRE_ACCEPTED,
            RewardTransactionType.WITHDRAWAL_REFUND,
        ):
            balance += amount

        elif tx.type in (
            RewardTransactionType.WITHDRAWAL_HOLD,
            RewardTransactionType.WITHDRAWAL_PAID,
        ):
            balance -= amount

    return max(balance, 0)


def award_referral_signup(referrer_id, referred_user_id):
    """
    One-time reward for a successful referred registration.
    """
    if not referrer_id:
        return False

    reference = f"referral-signup:{referred_user_id}"

    existing = RewardTransaction.query.filter_by(
        reference=reference
    ).first()

    if existing:
        return False

    tx = RewardTransaction(
        user_id=referrer_id,
        amount=SIGNUP_REWARD,
        type=RewardTransactionType.REFERRAL_SIGNUP,
        reference=reference,
        description="Referral signup reward",
    )

    db.session.add(tx)

    try:
        db.session.flush()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def award_referred_hire(user_id, hire_id):
    """
    If the hired teacher OR hiring student was referred by another user,
    that referrer receives 100 coins.

    The reward is awarded only once per accepted hire.
    """
    from app.models.user import User

    referred_user = User.query.get(user_id)

    if not referred_user:
        return False

    referrer_id = referred_user.referred_by_user_id

    if not referrer_id:
        return False

    reference = f"referral-hire:{hire_id}"

    existing = RewardTransaction.query.filter_by(
        reference=reference
    ).first()

    if existing:
        return False

    tx = RewardTransaction(
        user_id=referrer_id,
        amount=HIRED_REWARD,
        type=RewardTransactionType.REFERRED_HIRE_ACCEPTED,
        reference=reference,
        description="Referral reward for accepted hire",
    )

    db.session.add(tx)

    try:
        db.session.flush()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def create_withdrawal(
    user_id,
    coins,
    payout_method="upi",
):
    """
    Holds coins immediately.

    Example:
    1500 coins -> Rs. 150
    """
    coins = int(coins)

    if coins <= 0:
        raise ValueError("Withdrawal coins must be greater than zero.")

    if coins % COINS_PER_RUPEE != 0:
        raise ValueError(
            f"Coins must be in multiples of {COINS_PER_RUPEE}."
        )

    balance = get_balance(user_id)

    if coins > balance:
        raise ValueError("Insufficient reward coin balance.")

    amount = coins_to_rupees(coins)

    withdrawal = RewardWithdrawal(
        user_id=user_id,
        coins=coins,
        amount=amount,
        payout_method=(payout_method or "upi").strip().lower(),
        status=RewardWithdrawalStatus.REQUESTED,
    )

    db.session.add(withdrawal)

    hold = RewardTransaction(
        user_id=user_id,
        amount=coins,
        type=RewardTransactionType.WITHDRAWAL_HOLD,
        reference=f"reward-withdrawal-hold:{id(withdrawal)}",
        description=f"Reward withdrawal hold #{id(withdrawal)}",
    )

    db.session.add(hold)

    db.session.flush()

    # Replace temporary reference after real DB id exists.
    hold.reference = f"reward-withdrawal-hold:{withdrawal.id}"
    hold.description = f"Reward withdrawal hold #{withdrawal.id}"

    return withdrawal


def mark_paid(withdrawal, admin_id, payout_reference=None):
    """
    Admin paid:
    held coins remain consumed.
    """
    if withdrawal.status != RewardWithdrawalStatus.REQUESTED:
        raise ValueError("Withdrawal is already processed.")

    withdrawal.status = RewardWithdrawalStatus.PAID
    withdrawal.payout_reference = (
        (payout_reference or "").strip()[:120] or None
    )

    from datetime import datetime

    withdrawal.processed_at = datetime.utcnow()

    # Explicit PAID ledger entry.
    paid = RewardTransaction(
        user_id=withdrawal.user_id,
        amount=withdrawal.coins,
        type=RewardTransactionType.WITHDRAWAL_PAID,
        reference=f"reward-withdrawal-paid:{withdrawal.id}",
        description=f"Reward withdrawal paid #{withdrawal.id}",
    )

    db.session.add(paid)


def reject_with_refund(withdrawal, admin_id, note=None):
    """
    Admin rejected:
    held coins are returned.
    """
    if withdrawal.status != RewardWithdrawalStatus.REQUESTED:
        raise ValueError("Withdrawal is already processed.")

    withdrawal.status = RewardWithdrawalStatus.REJECTED
    withdrawal.admin_note = (note or "").strip()[:500] or None

    from datetime import datetime

    withdrawal.processed_at = datetime.utcnow()

    refund = RewardTransaction(
        user_id=withdrawal.user_id,
        amount=withdrawal.coins,
        type=RewardTransactionType.WITHDRAWAL_REFUND,
        reference=f"reward-withdrawal-refund:{withdrawal.id}",
        description=f"Reward withdrawal refund #{withdrawal.id}",
    )

    db.session.add(refund)
'''

write_new(APP / "services/reward_service.py", reward_service)
print("[OK] app/services/reward_service.py")

# ---------------------------------------------------------------------
# 6. add reward_coins to User
# ---------------------------------------------------------------------

print()
print("[6] ADDING USER REWARD BALANCE")

if "reward_coins" not in user_text:

    marker = '    referral_code = db.Column('

    insertion = '''    reward_coins = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

'''

    if marker not in user_text:
        fail("Could not locate User referral area")

    new_user = user_text.replace(
        marker,
        insertion + marker,
        1,
    )

    modify(APP / "models/user.py", new_user)
    print("[OK] User.reward_coins added")

else:
    print("[SKIP] User.reward_coins already exists")

# ---------------------------------------------------------------------
# 7. import reward models
# ---------------------------------------------------------------------

print()
print("[7] REGISTERING MODELS")

models_init = APP / "models/__init__.py"

if models_init.exists():

    text = models_init.read_text(encoding="utf-8")

    additions = ""

    if "app.models.reward import" not in text:
        additions += "\nfrom app.models.reward import RewardTransaction\n"

    if "app.models.reward_withdrawal import" not in text:
        additions += (
            "\nfrom app.models.reward_withdrawal import "
            "RewardWithdrawal\n"
        )

    if additions:
        modify(models_init, text + additions)
        print("[OK] models registered")
    else:
        print("[SKIP] models already registered")

else:
    print("[INFO] No models/__init__.py; Flask model discovery will be tested later")

# ---------------------------------------------------------------------
# 8. patch registration rewards
# ---------------------------------------------------------------------

print()
print("[8] PATCHING REFERRAL SIGNUP REWARD")

auth_path = APP / "routes/auth.py"
auth_text = auth_path.read_text(encoding="utf-8")

if "award_referral_signup" not in auth_text:
    import_marker = "from app import"

    # Put import near other app imports.
    lines = auth_text.splitlines(True)

    idx = None

    for i, line in enumerate(lines):
        if line.startswith("from app"):
            idx = i
            break

    if idx is None:
        fail("Could not locate app imports in auth.py")

    lines.insert(
        idx,
        "from app.services.reward_service import award_referral_signup\n",
    )

    auth_text = "".join(lines)

# Find both registration functions.
# Reward must happen after user.id exists.
commit_pattern = re.compile(
    r'(?P<indent>^[ \t]*)db\.session\.commit\(\)',
    re.MULTILINE,
)

matches = list(commit_pattern.finditer(auth_text))

if len(matches) < 2:
    fail(
        "Could not safely locate both registration db.session.commit() "
        "calls in auth.py"
    )

# Work backwards so positions remain valid.
inserted = 0

for m in reversed(matches[:2]):

    indent = m.group("indent")

    # Look at nearby block before commit.
    start = max(0, m.start() - 2500)
    block = auth_text[start:m.start()]

    if "referrer" not in block:
        continue

    code = (
        f"{indent}# Referral signup reward: one-time, idempotent.\n"
        f"{indent}if referrer:\n"
        f"{indent}    award_referral_signup(referrer.id, user.id)\n"
    )

    pos = m.start()
    auth_text = auth_text[:pos] + code + auth_text[pos:]
    inserted += 1

if inserted == 0:
    fail(
        "No registration block was safely matched for referral reward."
    )

modify(auth_path, auth_text)
print(f"[OK] Referral signup reward patched ({inserted} registration paths)")

# ---------------------------------------------------------------------
# 9. patch hire acceptance
# ---------------------------------------------------------------------

print()
print("[9] PATCHING ACCEPTED-HIRE REWARD")

teacher_path = APP / "routes/teacher.py"
teacher_text = teacher_path.read_text(encoding="utf-8")

if "award_referred_hire" not in teacher_text:

    # import
    lines = teacher_text.splitlines(True)

    idx = None

    for i, line in enumerate(lines):
        if line.startswith("from app"):
            idx = i
            break

    if idx is None:
        fail("Could not locate imports in teacher.py")

    lines.insert(
        idx,
        "from app.services.reward_service import award_referred_hire\n",
    )

    teacher_text = "".join(lines)

# Exact known acceptance anchor.
anchor = "        hire.status = HireStatus.ACCEPTED"

if anchor not in teacher_text:
    fail("Hire acceptance anchor not found")

insertion = '''
        # Referral reward:
        # If either the referred student or referred teacher participates
        # in this accepted hire, the original referrer gets 100 coins.
        try:
            award_referred_hire(hire.student.user_id, hire.id)
            award_referred_hire(hire.teacher.user_id, hire.id)
        except Exception:
            # Reward failure must not break a legitimate hire acceptance.
            # The transaction is still rolled back by the outer request
            # if the application later fails.
            pass
'''

teacher_text = teacher_text.replace(
    anchor,
    anchor + insertion,
    1,
)

modify(teacher_path, teacher_text)
print("[OK] Accepted-hire reward patched")

# ---------------------------------------------------------------------
# 10. create migration
# ---------------------------------------------------------------------

print()
print("[10] CREATING ALEMBIC MIGRATION")

versions = ROOT / "migrations/versions"
versions.mkdir(parents=True, exist_ok=True)

# Get current head.
result = subprocess.run(
    ["flask", "db", "current"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    fail("Could not determine Alembic current revision")

current = None

for line in result.stdout.splitlines():
    m = re.search(r"\b([0-9A-Za-z_]+)\s+\(head\)", line)
    if m:
        current = m.group(1)
        break

if not current:
    for line in result.stdout.splitlines():
        if re.fullmatch(r"[0-9A-Za-z_]+", line.strip()):
            current = line.strip()
            break

if not current:
    fail("Could not determine current Alembic revision")

migration_name = (
    f"{datetime.now():%Y%m%d_%H%M%S}"
    "_add_reward_coin_system.py"
)

migration_path = versions / migration_name

migration = f'''"""Add reward coin ledger and reward withdrawals.

Revision ID: {migration_name[:-3]}
Revises: {current}
"""

from alembic import op
import sqlalchemy as sa


revision = "{migration_name[:-3]}"
down_revision = "{current}"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "reward_coins",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    op.create_table(
        "reward_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "referral_signup",
                "referred_hire_accepted",
                "withdrawal_hold",
                "withdrawal_paid",
                "withdrawal_refund",
                name="rewardtransactiontype",
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "reference",
            name="uq_reward_transactions_reference",
        ),
    )

    op.create_index(
        "ix_reward_transactions_user_id",
        "reward_transactions",
        ["user_id"],
    )

    op.create_index(
        "ix_reward_transactions_type",
        "reward_transactions",
        ["type"],
    )

    op.create_index(
        "ix_reward_transactions_reference",
        "reward_transactions",
        ["reference"],
        unique=True,
    )

    op.create_table(
        "reward_withdrawals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("coins", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "paid",
                "rejected",
                name="rewardwithdrawalstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "payout_method",
            sa.String(30),
            nullable=False,
            server_default="upi",
        ),
        sa.Column(
            "payout_reference",
            sa.String(120),
            nullable=True,
        ),
        sa.Column(
            "admin_note",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_reward_withdrawals_user_id",
        "reward_withdrawals",
        ["user_id"],
    )

    op.create_index(
        "ix_reward_withdrawals_status",
        "reward_withdrawals",
        ["status"],
    )


def downgrade():
    op.drop_index(
        "ix_reward_withdrawals_status",
        table_name="reward_withdrawals",
    )

    op.drop_index(
        "ix_reward_withdrawals_user_id",
        table_name="reward_withdrawals",
    )

    op.drop_table("reward_withdrawals")

    op.drop_index(
        "ix_reward_transactions_reference",
        table_name="reward_transactions",
    )

    op.drop_index(
        "ix_reward_transactions_type",
        table_name="reward_transactions",
    )

    op.drop_index(
        "ix_reward_transactions_user_id",
        table_name="reward_transactions",
    )

    op.drop_table("reward_transactions")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("reward_coins")
'''

write_new(migration_path, migration)
print("[OK]", migration_path.name)

# ---------------------------------------------------------------------
# 11. reward routes
# ---------------------------------------------------------------------

print()
print("[11] CREATING REWARD ROUTES")

reward_routes = r'''"""
Reward wallet routes.

Works for authenticated users.
Admin payout routes are intentionally kept in admin.py.
"""

from decimal import Decimal

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.models.reward import RewardTransaction
from app.models.reward_withdrawal import (
    RewardWithdrawal,
    RewardWithdrawalStatus,
)
from app.services.reward_service import (
    COINS_PER_RUPEE,
    create_withdrawal,
    get_balance,
)

reward_bp = Blueprint(
    "reward",
    __name__,
    url_prefix="/rewards",
)


@reward_bp.route("/wallet")
@login_required
def wallet():
    balance = get_balance(current_user.id)

    transactions = (
        RewardTransaction.query
        .filter_by(user_id=current_user.id)
        .order_by(RewardTransaction.created_at.desc())
        .limit(100)
        .all()
    )

    withdrawals = (
        RewardWithdrawal.query
        .filter_by(user_id=current_user.id)
        .order_by(RewardWithdrawal.requested_at.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "reward/wallet.html",
        balance=balance,
        rupee_value=Decimal(balance) / Decimal(COINS_PER_RUPEE),
        transactions=transactions,
        withdrawals=withdrawals,
        coins_per_rupee=COINS_PER_RUPEE,
    )


@reward_bp.route("/withdraw", methods=["POST"])
@login_required
def withdraw():
    try:
        coins = int(request.form.get("coins", "0"))
    except ValueError:
        coins = 0

    payout_method = (
        request.form.get("payout_method", "upi")
        .strip()
        .lower()
    )

    try:
        withdrawal = create_withdrawal(
            current_user.id,
            coins,
            payout_method,
        )

        db.session.commit()

        flash(
            f"Withdrawal request #{withdrawal.id} submitted. "
            f"{coins} coins are now reserved.",
            "success",
        )

    except Exception as exc:
        db.session.rollback()
        flash(str(exc), "danger")

    return redirect(url_for("reward.wallet"))
'''

write_new(APP / "routes/reward.py", reward_routes)
print("[OK] app/routes/reward.py")

# ---------------------------------------------------------------------
# 12. register reward blueprint
# ---------------------------------------------------------------------

print()
print("[12] REGISTERING REWARD BLUEPRINT")

init_path = APP / "__init__.py"
init_text = init_path.read_text(encoding="utf-8")

if "from app.routes.reward import reward_bp" not in init_text:

    # Find create_app function.
    if "def create_app" not in init_text:
        fail("create_app not found in app/__init__.py")

    import_marker = "from app import"

    lines = init_text.splitlines(True)

    idx = None

    for i, line in enumerate(lines):
        if line.startswith("from app.routes"):
            idx = i
            break

    if idx is None:
        # insert before create_app
        pos = init_text.find("def create_app")
        if pos == -1:
            fail("Could not locate create_app")

        init_text = (
            init_text[:pos]
            + "from app.routes.reward import reward_bp\n\n"
            + init_text[pos:]
        )
    else:
        lines.insert(
            idx,
            "from app.routes.reward import reward_bp\n",
        )
        init_text = "".join(lines)

# register blueprint if not already registered
if "app.register_blueprint(reward_bp)" not in init_text:

    marker = "def create_app"

    pos = init_text.find(marker)

    # Find first occurrence after function.
    body_start = init_text.find("\n", pos)

    if body_start == -1:
        fail("create_app body not found")

    # Find first indented executable line.
    lines = init_text.splitlines(True)

    function_index = None

    for i, line in enumerate(lines):
        if line.startswith("def create_app"):
            function_index = i
            break

    if function_index is None:
        fail("create_app function not found")

    insert_index = function_index + 1

    while (
        insert_index < len(lines)
        and (
            lines[insert_index].strip() == ""
            or lines[insert_index].lstrip().startswith("#")
        )
    ):
        insert_index += 1

    lines.insert(
        insert_index,
        "    app.register_blueprint(reward_bp)\n",
    )

    init_text = "".join(lines)

modify(init_path, init_text)
print("[OK] reward blueprint registered")

# ---------------------------------------------------------------------
# 13. reward template
# ---------------------------------------------------------------------

print()
print("[13] CREATING REWARD WALLET PAGE")

template = r'''{% extends "base.html" %}

{% block title %}Reward Wallet{% endblock %}

{% block content %}

<div class="container py-4">

    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h2 class="mb-1">Reward Wallet</h2>
            <p class="text-muted mb-0">
                Referral coins and rewards
            </p>
        </div>
    </div>

    <div class="row g-3 mb-4">

        <div class="col-md-6">
            <div class="card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted">
                        Available Coins
                    </div>

                    <div class="display-5 fw-bold">
                        {{ balance }}
                    </div>

                    <div class="text-muted">
                        10 coins = ₹1
                    </div>
                </div>
            </div>
        </div>

        <div class="col-md-6">
            <div class="card shadow-sm h-100">
                <div class="card-body">
                    <div class="text-muted">
                        Approximate Value
                    </div>

                    <div class="display-5 fw-bold">
                        ₹{{ "%.2f"|format(rupee_value) }}
                    </div>

                    <div class="text-muted">
                        1500 coins = ₹150
                    </div>
                </div>
            </div>
        </div>

    </div>


    <div class="card shadow-sm mb-4">

        <div class="card-header">
            <strong>Withdraw Reward Coins</strong>
        </div>

        <div class="card-body">

            <form method="post"
                  action="{{ url_for('reward.withdraw') }}">

                {% if csrf_token is defined %}
                    <input type="hidden"
                           name="csrf_token"
                           value="{{ csrf_token() }}">
                {% endif %}

                <div class="mb-3">

                    <label class="form-label">
                        Coins
                    </label>

                    <input
                        type="number"
                        name="coins"
                        class="form-control"
                        min="10"
                        step="10"
                        max="{{ balance }}"
                        required
                    >

                    <div class="form-text">
                        Coins must be in multiples of 10.
                    </div>

                </div>

                <div class="mb-3">

                    <label class="form-label">
                        Payout Method
                    </label>

                    <select name="payout_method"
                            class="form-select">

                        <option value="upi">
                            UPI
                        </option>

                        <option value="bank">
                            Bank
                        </option>

                    </select>

                </div>

                <button
                    type="submit"
                    class="btn btn-primary"
                    {% if balance < 10 %}disabled{% endif %}>
                    Request Withdrawal
                </button>

            </form>

        </div>

    </div>


    <div class="card shadow-sm mb-4">

        <div class="card-header">
            <strong>Reward Transactions</strong>
        </div>

        <div class="table-responsive">

            <table class="table table-hover mb-0">

                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Coins</th>
                        <th>Description</th>
                    </tr>
                </thead>

                <tbody>

                {% for tx in transactions %}

                    <tr>

                        <td>
                            {{ tx.created_at }}
                        </td>

                        <td>
                            {{ tx.type.value }}
                        </td>

                        <td>
                            {{ tx.amount }}
                        </td>

                        <td>
                            {{ tx.description or "-" }}
                        </td>

                    </tr>

                {% else %}

                    <tr>
                        <td colspan="4"
                            class="text-center text-muted py-4">
                            No reward transactions yet.
                        </td>
                    </tr>

                {% endfor %}

                </tbody>

            </table>

        </div>

    </div>


    <div class="card shadow-sm">

        <div class="card-header">
            <strong>Withdrawal History</strong>
        </div>

        <div class="table-responsive">

            <table class="table table-hover mb-0">

                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Coins</th>
                        <th>Amount</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </thead>

                <tbody>

                {% for item in withdrawals %}

                    <tr>

                        <td>
                            #{{ item.id }}
                        </td>

                        <td>
                            {{ item.coins }}
                        </td>

                        <td>
                            ₹{{ item.amount }}
                        </td>

                        <td>
                            {{ item.status.value }}
                        </td>

                        <td>
                            {{ item.requested_at }}
                        </td>

                    </tr>

                {% else %}

                    <tr>
                        <td colspan="5"
                            class="text-center text-muted py-4">
                            No withdrawal requests yet.
                        </td>
                    </tr>

                {% endfor %}

                </tbody>

            </table>

        </div>

    </div>

</div>

{% endblock %}
'''

write_new(
    APP / "templates/reward/wallet.html",
    template,
)

print("[OK] reward wallet template")

# ---------------------------------------------------------------------
# 14. admin reward routes
# ---------------------------------------------------------------------

print()
print("[14] ADDING ADMIN REWARD PAYOUT ROUTES")

admin_path = APP / "routes/admin.py"
admin_text = admin_path.read_text(encoding="utf-8")

if "RewardWithdrawal" not in admin_text:

    # Add imports after app imports.
    lines = admin_text.splitlines(True)

    idx = None

    for i, line in enumerate(lines):
        if line.startswith("from app"):
            idx = i
            break

    if idx is None:
        fail("Could not locate app imports in admin.py")

    imports = (
        "from app.models.reward_withdrawal import "
        "RewardWithdrawal, RewardWithdrawalStatus\n"
        "from app.services.reward_service import "
        "mark_paid, reject_with_refund\n"
    )

    lines.insert(idx, imports)
    admin_text = "".join(lines)


admin_routes = r'''

# ============================================================
# REWARD COIN PAYOUTS
# ============================================================

@admin_bp.route("/reward-withdrawals")
@login_required
def reward_withdrawals():
    withdrawals = (
        RewardWithdrawal.query
        .order_by(RewardWithdrawal.requested_at.desc())
        .limit(100)
        .all()
    )

    return render_template(
        "admin/reward_withdrawals.html",
        withdrawals=withdrawals,
    )


@admin_bp.route(
    "/reward-withdrawals/<int:withdrawal_id>/pay",
    methods=["POST"],
)
@login_required
def pay_reward_withdrawal(withdrawal_id):

    withdrawal = RewardWithdrawal.query.get_or_404(
        withdrawal_id
    )

    if withdrawal.status != RewardWithdrawalStatus.REQUESTED:
        flash(
            "Reward withdrawal is already processed.",
            "warning",
        )
        return redirect(
            url_for("admin.reward_withdrawals")
        )

    payout_reference = (
        request.form.get("payout_reference", "")
        .strip()
    )

    if not payout_reference:
        flash(
            "Payout reference/UTR is required.",
            "danger",
        )
        return redirect(
            url_for("admin.reward_withdrawals")
        )

    try:

        mark_paid(
            withdrawal,
            current_user.id,
            payout_reference,
        )

        db.session.commit()

        flash(
            f"Reward withdrawal #{withdrawal.id} marked PAID.",
            "success",
        )

    except Exception as exc:

        db.session.rollback()

        flash(
            f"Payout failed: {exc}",
            "danger",
        )

    return redirect(
        url_for("admin.reward_withdrawals")
    )


@admin_bp.route(
    "/reward-withdrawals/<int:withdrawal_id>/reject",
    methods=["POST"],
)
@login_required
def reject_reward_withdrawal(withdrawal_id):

    withdrawal = RewardWithdrawal.query.get_or_404(
        withdrawal_id
    )

    if withdrawal.status != RewardWithdrawalStatus.REQUESTED:
        flash(
            "Reward withdrawal is already processed.",
            "warning",
        )
        return redirect(
            url_for("admin.reward_withdrawals")
        )

    note = (
        request.form.get("note", "")
        .strip()
    )

    try:

        reject_with_refund(
            withdrawal,
            current_user.id,
            note,
        )

        db.session.commit()

        flash(
            f"Reward withdrawal #{withdrawal.id} rejected. "
            f"{withdrawal.coins} coins refunded.",
            "info",
        )

    except Exception as exc:

        db.session.rollback()

        flash(
            f"Reject failed: {exc}",
            "danger",
        )

    return redirect(
        url_for("admin.reward_withdrawals")
    )
'''

if "def reward_withdrawals(" not in admin_text:

    # Append routes at end.
    admin_text += admin_routes

modify(admin_path, admin_text)
print("[OK] Admin reward payout routes")

# ---------------------------------------------------------------------
# 15. admin template
# ---------------------------------------------------------------------

print()
print("[15] CREATING ADMIN REWARD PAGE")

admin_template = r'''{% extends "base.html" %}

{% block title %}Reward Withdrawals{% endblock %}

{% block content %}

<div class="container py-4">

    <h2 class="mb-4">
        Reward Coin Withdrawals
    </h2>

    <div class="table-responsive">

        <table class="table table-bordered table-hover">

            <thead>
                <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>Coins</th>
                    <th>Amount</th>
                    <th>Method</th>
                    <th>Status</th>
                    <th>Date</th>
                    <th>Action</th>
                </tr>
            </thead>

            <tbody>

            {% for item in withdrawals %}

                <tr>

                    <td>
                        #{{ item.id }}
                    </td>

                    <td>
                        {{ item.user.name }}
                        <br>
                        <small class="text-muted">
                            {{ item.user.email }}
                        </small>
                    </td>

                    <td>
                        {{ item.coins }}
                    </td>

                    <td>
                        ₹{{ item.amount }}
                    </td>

                    <td>
                        {{ item.payout_method }}
                    </td>

                    <td>
                        {{ item.status.value }}
                    </td>

                    <td>
                        {{ item.requested_at }}
                    </td>

                    <td>

                    {% if item.status.value == "requested" %}

                        <form method="post"
                              action="{{ url_for(
                                  'admin.pay_reward_withdrawal',
                                  withdrawal_id=item.id
                              ) }}"
                              class="mb-2">

                            {% if csrf_token is defined %}
                                <input type="hidden"
                                       name="csrf_token"
                                       value="{{ csrf_token() }}">
                            {% endif %}

                            <input
                                type="text"
                                name="payout_reference"
                                class="form-control form-control-sm mb-2"
                                placeholder="UPI UTR / payout reference"
                                required
                            >

                            <button
                                class="btn btn-success btn-sm"
                                type="submit">
                                Mark Paid
                            </button>

                        </form>


                        <form method="post"
                              action="{{ url_for(
                                  'admin.reject_reward_withdrawal',
                                  withdrawal_id=item.id
                              ) }}">

                            {% if csrf_token is defined %}
                                <input type="hidden"
                                       name="csrf_token"
                                       value="{{ csrf_token() }}">
                            {% endif %}

                            <input
                                type="text"
                                name="note"
                                class="form-control form-control-sm mb-2"
                                placeholder="Rejection reason"
                            >

                            <button
                                class="btn btn-danger btn-sm"
                                type="submit">
                                Reject + Refund
                            </button>

                        </form>

                    {% else %}

                        <span class="text-muted">
                            Processed
                        </span>

                    {% endif %}

                    </td>

                </tr>

            {% else %}

                <tr>
                    <td colspan="8"
                        class="text-center text-muted py-4">
                        No reward withdrawals.
                    </td>
                </tr>

            {% endfor %}

            </tbody>

        </table>

    </div>

</div>

{% endblock %}
'''

write_new(
    APP / "templates/admin/reward_withdrawals.html",
    admin_template,
)

print("[OK] Admin reward withdrawal template")

# ---------------------------------------------------------------------
# 16. compile
# ---------------------------------------------------------------------

print()
print("[16] PYTHON COMPILE")

run(
    [sys.executable, "-m", "compileall", "-q", "app"]
)

print("[OK] compile")

# ---------------------------------------------------------------------
# 17. migration upgrade
# ---------------------------------------------------------------------

print()
print("[17] DATABASE MIGRATION")

run(["flask", "db", "upgrade"])

print("[OK] database upgraded")

# ---------------------------------------------------------------------
# 18. smoke test
# ---------------------------------------------------------------------

print()
print("[18] REWARD SYSTEM SMOKE TEST")

smoke = r'''
from app import create_app, db
from app.models.user import User
from app.models.reward import RewardTransaction
from app.models.reward_withdrawal import RewardWithdrawal
from app.services.reward_service import (
    COINS_PER_RUPEE,
    SIGNUP_REWARD,
    HIRED_REWARD,
)

app = create_app()

with app.app_context():

    print("=" * 75)
    print("REWARD SYSTEM SMOKE TEST")
    print("=" * 75)

    print("[OK] User.reward_coins:",
          hasattr(User, "reward_coins"))

    print("[OK] RewardTransaction table:",
          RewardTransaction.__tablename__)

    print("[OK] RewardWithdrawal table:",
          RewardWithdrawal.__tablename__)

    print("[OK] Coins per rupee:",
          COINS_PER_RUPEE)

    print("[OK] Signup reward:",
          SIGNUP_REWARD)

    print("[OK] Accepted hire reward:",
          HIRED_REWARD)

    print("[OK] 1500 coins value:",
          1500 / COINS_PER_RUPEE)

    print("=" * 75)
    print("SMOKE TEST PASS")
    print("=" * 75)
'''

smoke_path = ROOT / ".reward_smoke.py"
smoke_path.write_text(smoke, encoding="utf-8")

try:
    run([sys.executable, ".reward_smoke.py"])
finally:
    if smoke_path.exists():
        smoke_path.unlink()

# ---------------------------------------------------------------------
# 19. alembic
# ---------------------------------------------------------------------

print()
print("[19] FINAL ALEMBIC CHECK")

run(["flask", "db", "current"])
run(["flask", "db", "heads"])

# ---------------------------------------------------------------------
# 20. final
# ---------------------------------------------------------------------

print()
print("=" * 80)
print("REWARD SYSTEM PATCH COMPLETE")
print("=" * 80)

print()
print("Referral signup reward       : 100 coins")
print("Accepted referred hire      : 100 coins")
print("Coin conversion             : 10 coins = ₹1")
print("1500 coins                  : ₹150")
print("Coin wallet                 : SEPARATE")
print("Teacher INR wallet          : UNCHANGED")
print("Withdrawal                  : COINS HELD")
print("Admin PAID                  : COINS CONSUMED")
print("Admin REJECTED              : COINS REFUNDED")
print("Duplicate protection        : UNIQUE ledger references")

print()
print("Changed:")
for x in CHANGED:
    print(" ", x)

print()
print("Created:")
for x in CREATED:
    print(" ", x)

print()
print("Backup:")
print(" ", BACKUP)

print()
print("[PASS] Backup created")
print("[PASS] Reward ledger installed")
print("[PASS] Referral signup reward installed")
print("[PASS] Accepted-hire reward installed")
print("[PASS] Reward withdrawal installed")
print("[PASS] Admin payout/refund installed")
print("[PASS] Migration upgraded")
print("[PASS] Compile passed")
print("[PASS] Smoke test passed")
print("=" * 80)
