from pathlib import Path
import re
from datetime import datetime

ROOT = Path(__file__).resolve().parent

user_file = ROOT / "app/models/user.py"
migration_file = ROOT / "migrations/versions/20260827_004132_add_referral_and_availability.py"

print("=" * 70)
print("AUTOMATIC REFERRAL RELATIONSHIP FIX")
print("=" * 70)

# ------------------------------------------------------------
# USER MODEL
# ------------------------------------------------------------

text = user_file.read_text()

if "referred_by_id" not in text:
    marker = '    referral_code = db.Column(db.String(32), unique=True, nullable=True, index=True)\n'

    if marker not in text:
        raise SystemExit("[ERROR] referral_code model field not found")

    replacement = marker + '''
    # User who referred this account.
    # Self-reference is nullable because registration without
    # a referral code is allowed.
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
'''

    text = text.replace(marker, replacement, 1)
    user_file.write_text(text)
    print("[OK] User.referred_by_id added")
else:
    print("[OK] User.referred_by_id already exists")


# ------------------------------------------------------------
# MIGRATION
# ------------------------------------------------------------

mtext = migration_file.read_text()

if "referred_by_id" not in mtext:
    # Add column operation after referral_code creation.
    pattern = r'(\bop\.add_column\(\s*[\'"]users[\'"],\s*sa\.Column\([^\n]+referral_code[^\n]+\)\s*\))'

    match = re.search(pattern, mtext)

    if match:
        insertion = match.group(1) + '''

    op.add_column(
        "users",
        sa.Column(
            "referred_by_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_users_referred_by_id",
        "users",
        ["referred_by_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_referred_by_id_users",
        "users",
        "users",
        ["referred_by_id"],
        ["id"],
    )
'''
        mtext = mtext[:match.start()] + insertion + mtext[match.end():]

        # Downgrade additions.
        downgrade_marker = "\ndef downgrade():"
        if downgrade_marker in mtext:
            idx = mtext.index(downgrade_marker)

            downgrade_code = '''
    op.drop_constraint(
        "fk_users_referred_by_id_users",
        "users",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_users_referred_by_id",
        table_name="users",
    )

    op.drop_column("users", "referred_by_id")

'''

            mtext = mtext[:idx] + "\n" + downgrade_code + mtext[idx:]

        migration_file.write_text(mtext)
        print("[OK] Migration updated")
    else:
        print("[WARNING] Could not automatically locate referral_code migration")
        print("[ACTION] Migration may need manual inspection")
else:
    print("[OK] Migration already contains referred_by_id")


print()
print("=" * 70)
print("FIX COMPLETE")
print("=" * 70)
print()
print("Next:")
print("  python -m compileall -q app")
print("  flask db upgrade")
print("  flask db current")
