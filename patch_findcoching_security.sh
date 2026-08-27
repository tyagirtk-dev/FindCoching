#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$ROOT/.patch_backup_$STAMP"

echo "=========================================="
echo " FindCoching Security + UX Hardening"
echo "=========================================="
echo "[INFO] Root: $ROOT"
echo "[INFO] Backup: $BACKUP"

# ------------------------------------------------------------
# 0. Basic validation
# ------------------------------------------------------------

if [[ ! -d "$ROOT/app" ]]; then
    echo "[ERROR] app/ directory not found."
    exit 1
fi

if [[ ! -f "$ROOT/app/__init__.py" ]]; then
    echo "[ERROR] app/__init__.py not found."
    exit 1
fi

mkdir -p "$BACKUP"

echo
echo "===== BACKUP ====="

for f in \
    app/__init__.py \
    app/routes/auth.py \
    app/services/google_auth_flow.py \
    app/services/google_oauth_routes.py \
    app/services/google_oauth.py \
    config.py
do
    if [[ -f "$f" ]]; then
        mkdir -p "$BACKUP/$(dirname "$f")"
        cp -a "$f" "$BACKUP/$f"
        echo "[BACKUP] $f"
    fi
done

# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------

python - <<'PY'
from pathlib import Path

print("[OK] Python available")
print("[INFO] Applying targeted source patches...")
PY

# ------------------------------------------------------------
# 1. Create security utility
# ------------------------------------------------------------

mkdir -p app/security

cat > app/security/__init__.py <<'PY'
"""Security helpers for FindCoching."""
PY

cat > app/security/url.py <<'PY'
from __future__ import annotations

from urllib.parse import urlparse

from flask import request


def safe_next_url(target: str | None, fallback: str = "/") -> str:
    """
    Return a local relative URL only.

    Prevents open redirects such as:
        https://evil.example/
        //evil.example/
        javascript:...
    """
    if not target:
        return fallback

    target = target.strip()

    if not target:
        return fallback

    parsed = urlparse(target)

    # Reject absolute URLs.
    if parsed.scheme or parsed.netloc:
        return fallback

    # Reject protocol-relative URLs.
    if target.startswith("//"):
        return fallback

    # Only allow application-local paths.
    if not target.startswith("/"):
        return fallback

    # Reject control characters.
    if any(ord(ch) < 32 for ch in target):
        return fallback

    return target


def request_next_url(fallback: str = "/") -> str:
    return safe_next_url(request.args.get("next"), fallback)
PY

echo "[OK] Created app/security/url.py"

# ------------------------------------------------------------
# 2. Patch auth.py dangerous next redirect
# ------------------------------------------------------------

python - <<'PY'
from pathlib import Path

p = Path("app/routes/auth.py")
s = p.read_text()

marker = "from app.security.url import safe_next_url"

if marker not in s:
    lines = s.splitlines()

    # Find a stable import location.
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i
            break

    lines.insert(insert_at, marker)
    s = "\n".join(lines) + ("\n" if s.endswith("\n") else "")

old = '''next_url = request.args.get("next", "").strip()
        if next_url:
            return redirect(next_url)
'''

new = '''next_url = safe_next_url(
            request.args.get("next"),
            fallback=""
        )
        if next_url:
            return redirect(next_url)
'''

if old in s:
    s = s.replace(old, new)
    print("[PATCH] Fixed auth open redirect")
elif "redirect(next_url)" in s:
    # Conservative fallback: replace only the redirect target.
    s = s.replace(
        "return redirect(next_url)",
        "return redirect(safe_next_url(next_url, fallback=url_for('main.index')))"
    )
    print("[PATCH] Hardened existing next_url redirect")
else:
    print("[INFO] No matching dangerous redirect found in auth.py")

p.write_text(s)
PY

# ------------------------------------------------------------
# 3. Harden Google OAuth redirect handling
# ------------------------------------------------------------

python - <<'PY'
from pathlib import Path

p = Path("app/services/google_oauth_routes.py")
s = p.read_text()

marker = "from app.security.url import safe_next_url"

if marker not in s:
    lines = s.splitlines()

    # Put helper import after normal imports.
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from ") or line.startswith("import "):
            insert_at = i
            break

    lines.insert(insert_at, marker)
    s = "\n".join(lines) + ("\n" if s.endswith("\n") else "")

# Existing code already appears to call _safe_next_url().
# Make sure helper implementation is not permissive.

needle = "def _safe_next_url"
if needle in s:
    start = s.index(needle)
    next_def = s.find("\ndef ", start + len(needle))

    if next_def == -1:
        block_end = len(s)
    else:
        block_end = next_def

    block = s[start:block_end]

    replacement = '''def _safe_next_url(target):
    return safe_next_url(target, fallback=url_for("main.index"))
'''

    s = s[:start] + replacement + s[block_end:]
    print("[PATCH] Hardened Google OAuth next URL")
else:
    # If helper is absent, add one before first route.
    route_pos = s.find("@google_auth_bp")
    if route_pos != -1:
        helper = '''def _safe_next_url(target):
    return safe_next_url(target, fallback=url_for("main.index"))


'''
        s = s[:route_pos] + helper + s[route_pos:]
        print("[PATCH] Added Google OAuth safe URL helper")
    else:
        print("[WARN] Could not locate Google OAuth route marker")

p.write_text(s)
PY

# ------------------------------------------------------------
# 4. Add secure Flask headers
# ------------------------------------------------------------

python - <<'PY'
from pathlib import Path

p = Path("app/__init__.py")
s = p.read_text()

if "after_request" not in s or "X-Content-Type-Options" not in s:

    marker = "def create_app"

    pos = s.find(marker)

    if pos == -1:
        raise SystemExit("[ERROR] create_app not found")

    # Find function body indentation point.
    insert = '''
def _apply_security_headers(response):
    """Apply baseline browser security headers."""

    response.headers.setdefault(
        "X-Content-Type-Options",
        "nosniff",
    )

    response.headers.setdefault(
        "X-Frame-Options",
        "SAMEORIGIN",
    )

    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )

    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(self)",
    )

    # Conservative CSP compatible with the existing Bootstrap/Leaflet UI.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'; "
        "object-src 'none'; "
        "img-src 'self' data: blob: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' data: https:; "
        "connect-src 'self' https: wss:;",
    )

    return response


'''

    s = s[:pos] + insert + s[pos:]

    # Register once inside create_app.
    needle = "app = Flask(__name__"

    if needle in s:
        # Find end of the Flask assignment line.
        line_end = s.find("\n", s.find(needle))

        registration = '''
    app.after_request(_apply_security_headers)
'''

        s = s[:line_end + 1] + registration + s[line_end + 1:]
        print("[PATCH] Added browser security headers")
    else:
        print("[WARN] Flask initialization line not found; header helper created but not registered")
else:
    print("[INFO] Security headers already appear to exist")

p.write_text(s)
PY

# ------------------------------------------------------------
# 5. Add secure cookie defaults without breaking local HTTP
# ------------------------------------------------------------

python - <<'PY'
from pathlib import Path

p = Path("config.py")
s = p.read_text()

settings = {
    "SESSION_COOKIE_HTTPONLY": "True",
    "SESSION_COOKIE_SAMESITE": '"Lax"',
}

for key, value in settings.items():
    if key not in s:
        # Add after SECRET_KEY definition.
        needle = 'SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")'

        if needle in s:
            s = s.replace(
                needle,
                needle + f'''
    {key} = {value}''',
                1,
            )
            print(f"[PATCH] Added {key}")

# Secure cookie should be configurable for HTTPS deployments.
if "SESSION_COOKIE_SECURE" not in s:
    needle = 'SESSION_COOKIE_SAMESITE = "Lax"'

    if needle in s:
        s = s.replace(
            needle,
            needle + '''
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE",
        "false",
    ).lower() in {"1", "true", "yes", "on"}''',
            1,
        )
        print("[PATCH] Added configurable SESSION_COOKIE_SECURE")

p.write_text(s)
PY

# ------------------------------------------------------------
# 6. Add tests
# ------------------------------------------------------------

mkdir -p tests

cat > tests/test_security.py <<'PY'
from app.security.url import safe_next_url


def test_safe_relative_url():
    assert safe_next_url("/student/dashboard") == "/student/dashboard"


def test_reject_absolute_url():
    assert safe_next_url("https://evil.example/") == "/"


def test_reject_protocol_relative_url():
    assert safe_next_url("//evil.example/") == "/"


def test_reject_non_relative_url():
    assert safe_next_url("evil.example/path") == "/"


def test_empty_uses_fallback():
    assert safe_next_url("", "/auth/login") == "/auth/login"


def test_control_character_rejected():
    assert safe_next_url("/foo\nbar") == "/"
PY

cat > tests/conftest.py <<'PY'
import os

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-findcoching")
PY

echo "[OK] Security tests created"

# ------------------------------------------------------------
# 7. Static upload safety check
# ------------------------------------------------------------

echo
echo "===== UPLOAD AUDIT ====="

python - <<'PY'
from pathlib import Path

root = Path("app/static/uploads")

if not root.exists():
    print("[INFO] Upload directory does not exist")
    raise SystemExit(0)

bad = []

allowed = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
}

for p in root.rglob("*"):
    if p.is_file() and p.name != ".gitkeep":
        if p.suffix.lower() not in allowed:
            bad.append(str(p))

if bad:
    print("[WARN] Unexpected upload extensions:")
    for item in bad:
        print("  ", item)
else:
    print("[OK] No unexpected upload extensions found")
PY

# ------------------------------------------------------------
# 8. Detect remaining dangerous redirect patterns
# ------------------------------------------------------------

echo
echo "===== REDIRECT RE-AUDIT ====="

grep -RInE \
    'redirect\((request\.(args|form)\.get|request\.referrer)' \
    app/routes app/services \
    --include='*.py' \
    || true

echo
echo "[INFO] Direct redirect audit complete."

# ------------------------------------------------------------
# 9. Python compile check
# ------------------------------------------------------------

echo
echo "===== COMPILEALL ====="

python -m compileall -q app tests
echo "[OK] compileall"

# ------------------------------------------------------------
# 10. Import check
# ------------------------------------------------------------

echo
echo "===== FLASK IMPORT ====="

python - <<'PY'
from app import create_app

app = create_app()

print("[OK] Flask app imported")

print()
print("===== SECURITY HEADERS =====")

with app.test_client() as client:
    response = client.get("/")

    for name in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ):
        value = response.headers.get(name)
        print(f"[{'OK' if value else 'WARN'}] {name}: {value or 'MISSING'}")
PY

# ------------------------------------------------------------
# 11. Run tests if pytest exists
# ------------------------------------------------------------

echo
echo "===== TESTS ====="

if command -v pytest >/dev/null 2>&1; then
    pytest -q
else
    echo "[WARN] pytest is not installed."
    echo "[INFO] Install with: pip install pytest"
fi

# ------------------------------------------------------------
# 12. Git diff
# ------------------------------------------------------------

echo
echo "===== DIFF STAT ====="

git diff --stat || true

echo
echo "===== CHANGED FILES ====="

git status --short || true

echo
echo "=========================================="
echo " PATCH COMPLETE"
echo "=========================================="
echo
echo "[OK] Backup:"
echo "     $BACKUP"
echo
echo "[NEXT] Review:"
echo "     git diff"
echo
echo "[NEXT] If everything is correct:"
echo "     git add app config.py tests"
echo "     git commit -m 'security: harden redirects sessions and browser headers'"
echo
