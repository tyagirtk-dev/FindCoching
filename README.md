# Hyperlocal Coaching Marketplace — Production v1

A production-structured Flask marketplace connecting students with local, verified
tutors. This package covers the complete implementation across all five phases:
project foundation & auth, radius search & hiring, attendance & payments/wallet,
the full admin operations suite, and real-time-feeling chat, notifications, and
reviews.

## Stack

- Backend: Python Flask (application factory + Blueprints)
- Database: PostgreSQL in production, SQLite for local development
- ORM: SQLAlchemy + Flask-Migrate (Alembic)
- Auth: Flask-Login with bcrypt password hashing
- Frontend: Jinja2, Bootstrap 5, vanilla JS, Leaflet.js + OpenStreetMap
- Email: SMTP, fully configurable from the Admin Panel (no hardcoded credentials)
- Reports: openpyxl (Excel export), reportlab (PDF export)

## Features

### Phase 1 — Foundation, Auth & RBAC
- Student registration (map-based location picker) and Teacher registration
  (photo, ID, and qualification certificate upload)
- Email OTP verification for new accounts; forgot/reset password via emailed OTP
- Teacher approval workflow: Pending → Approved / Rejected / Suspended, enforced
  at login
- Role-Based Access Control for Super Admin, Teacher, and Student
- CSRF protection, rate-limited login, secure file-upload validation, audit logging

### Phase 2 — Radius Search & Hiring
- Haversine-based nearby-teacher search with subject/mode/radius filters
- Admin-configurable default search radius
- Student → Teacher hire requests; Teacher accept/reject; Admin monitoring of all
  hire requests

### Phase 3 — Attendance, Wallet & Payments
- Teacher marks daily attendance per student; students and admin can view history
- UPI-based payment submission with screenshot/UTR proof; admin manual verification
- Commission-aware wallet crediting (pending balance / paid balance / total earned)
- Teacher withdrawal requests; admin approve / reject / mark-paid workflow
- Printable payment receipts

### Phase 4 — Admin Operations Suite
- Payments, withdrawals, and wallet-overview management screens
- Announcements (broadcast to all / teachers / students, with in-app notifications)
- Contact request inbox and status tracking
- Complaint management with admin responses
- Website settings (site name, UPI payee details) and existing SMTP / radius /
  commission settings
- Reports (teacher earnings, student payments, attendance, withdrawals, revenue)
  exportable as Excel (.xlsx) and PDF

### Phase 5 — Chat, Notifications & Reviews
- Private student ↔ teacher chat threads (only after an accepted hire)
- Image and file sharing, emoji picker, in-thread message search
- Read receipts and a lightweight typing indicator (AJAX long-poll based)
- In-app notification center for hire requests, payments, withdrawals, complaints,
  announcements, and new messages, with a live unread-count badge
- Student reviews & star ratings for hired teachers, rolled up into each teacher's
  average rating

## Project Structure

```
coaching_marketplace/
├── app/
│   ├── __init__.py           # Application factory, blueprint & extension registration
│   ├── models/                # SQLAlchemy models (one file per entity, 18 models)
│   ├── routes/                 # Blueprints: main, auth, student, teacher, admin, api, chat
│   ├── services/                 # settings, email(SMTP-from-DB), otp, geo, notification,
│   │                                wallet, report(Excel/PDF export)
│   ├── utils/                     # decorators (RBAC), file_upload
│   ├── forms/                      # WTForms (auth + marketplace forms)
│   ├── templates/                   # Jinja2 templates: base, auth, admin, teacher,
│   │                                    student, chat, errors (50+ templates)
│   └── static/                        # css, js, uploads/{photos,documents,chat}
├── migrations/                # Alembic migration environment + initial schema
├── config.py                  # Environment-based configuration
├── run.py                     # Local dev entry point (flask run / python run.py)
├── wsgi.py                    # Production entry point (gunicorn)
├── seed.py                    # Creates tables + default settings + Super Admin
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

### 1. Clone & create a virtual environment
git clone https://github.com/tyagirtk-dev/FindCoching.git

```bash

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `SECRET_KEY` — any long random string
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — credentials for the initial Super Admin
- `DATABASE_URL` — leave unset for local SQLite, or point to PostgreSQL for production

SMTP is **not** set here — it's configured later from the Admin Panel
(Admin → SMTP Settings) after the app is running, so registration OTP emails work.

### 3. Set the Flask app entry point

```bash
export FLASK_APP=run.py         # Windows (PowerShell): $env:FLASK_APP = "run.py"
export FLASK_ENV=development
```

### 4. Initialize the database

Choose **one** of the two approaches:

**Option A — quick start (SQLite, recommended for local dev):**
```bash
python seed.py
```
This creates all tables directly from the models, seeds default system settings,
and creates the Super Admin account from your `.env` values.

**Option B — via Alembic migrations (recommended before production / PostgreSQL):**
```bash
flask db upgrade
python seed.py
```
`flask db upgrade` applies the migration in `migrations/versions/0001_initial.py`.
`seed.py` is still needed afterwards to seed default settings and the Super Admin
account (it skips table creation if they already exist).

If you change any model later, generate a new revision instead of hand-editing
the schema:
```bash
flask db migrate -m "describe the change"
flask db upgrade
```

### 5. Run the app

```bash
flask run
```
or
```bash
python run.py
```

Visit `http://127.0.0.1:5000`.
Windows Setup

Requirements

Install these first:

- "Visual Studio Code" (https://code.visualstudio.com/download)
- "Python 3.13.x" (https://www.python.org/downloads/windows/)
- "Git for Windows" (https://git-scm.com/download/win)

«Recommended: Use Python 3.13.x for this project.»

Option A — Automatic Windows Setup

Clone the repository:

git clone https://github.com/tyagirtk-dev/FindCoching.git
cd FindCoching

Run the Windows setup script:

powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1

The script automatically:

1. Checks Python
2. Creates ".venv"
3. Activates the virtual environment
4. Upgrades pip
5. Installs "requirements.txt"
6. Creates ".env" from ".env.example"
7. Initializes the local SQLite database
8. Runs "seed.py"
9. Starts the Flask development server

Then open:

http://127.0.0.1:5000

Option B — Manual Windows Setup

Create and activate the virtual environment:

python -m venv .venv
.venv\Scripts\Activate.ps1

If PowerShell blocks script execution:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

Then activate again:

.venv\Scripts\Activate.ps1

Install dependencies:

python -m pip install --upgrade pip
pip install -r requirements.txt

Create ".env":

Copy-Item .env.example .env

Edit ".env" and set:

SECRET_KEY=your-long-random-secret-key
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

For local development, leave "DATABASE_URL" unset. The application will use SQLite.

Initialize the database:

python seed.py

Start Flask:

python run.py

Open:

http://127.0.0.1:5000

Local Development Database

Windows local development uses SQLite by default.

Windows Development → SQLite
Production → PostgreSQL

PostgreSQL is not required for local Windows development.

SMTP Configuration

SMTP credentials are not required in ".env".

After logging into the Super Admin account, configure SMTP from:

Admin → SMTP Settings

This is required for email OTP and password-reset emails.

Windows Upload Directories

Make sure these directories exist:

app/static/uploads/photos/
app/static/uploads/documents/
app/static/uploads/chat/

The application uses these directories for teacher photos, verification documents, and chat attachments.

Default Super Admin

The initial Super Admin is created by:

python seed.py

Credentials are taken from ".env":

ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

Change the default password after the first login.

Troubleshooting

Check Python:

python --version

Check virtual environment:

.venv\Scripts\Activate.ps1

Check installed packages:

pip list

If dependencies need to be reinstalled:

pip install -r requirements.txt

If the database needs to be recreated during local development, stop the application and remove the local SQLite database, then run:

python seed.py
### 6. Configure SMTP

Log in as Super Admin (the account created by `seed.py`) → **Admin → SMTP Settings**,
and fill in your SMTP host/port/username/password/sender details. Until this is
configured, registration will succeed but OTP emails cannot be sent (the app will
tell the user to contact the admin).

### 7. Configure payments (optional but recommended)

Admin → Website Settings → set the UPI Payee ID/Name shown to students on the
payment page. Admin → Commission Settings controls the platform's cut of each
verified payment before it's credited to the teacher's wallet.

## Core Workflows

- **Student registration:** `/auth/register/student` → email OTP → login.
- **Teacher registration:** `/auth/register/teacher` → email OTP → **Admin
  approval required** before the teacher can log in. Rejected/Suspended teachers
  are blocked at login with a clear message.
- **Admin approval:** Admin → Teacher Verification → Approve / Reject.
  Approved teachers can also be suspended later from Admin → Teachers.
- **Password reset:** `/auth/forgot-password` → emailed OTP → `/auth/reset-password`.
- **Find & hire a teacher:** Student → Find Teachers (radius/subject/mode filters)
  → Send Hire Request → Teacher accepts/rejects from Teacher → Requests.
- **Attendance:** Teacher → Attendance → mark present/absent/leave per student/date;
  visible to the student and to Admin.
- **Payment → Wallet:** Student → Payments → submit UPI payment with UTR + screenshot
  → Admin → Payments → Verify (credits the teacher's wallet, minus commission) or Reject.
- **Withdrawals:** Teacher → Wallet → Request Withdrawal → Admin → Withdrawals →
  Approve → Mark Paid (deducts from pending balance, adds to paid balance).
- **Chat:** Available once a hire is accepted, from either dashboard's "Messages"
  link or a hire's "Message" button.
- **Reviews:** Student → My Hires → Leave Review (only for accepted hires); updates
  the teacher's average rating automatically.
- **Reports:** Admin → Reports → export Teacher Earnings / Student Payments /
  Attendance / Withdrawals / Revenue as Excel or PDF.

## Production Notes

- Set `FLASK_ENV=production`, a strong `SECRET_KEY`, and a PostgreSQL `DATABASE_URL`
  — `create_app("production")` will refuse to start otherwise.
- Run behind gunicorn: `gunicorn wsgi:app`
- Use a real rate-limit backend (e.g. Redis) via `RATELIMIT_STORAGE_URI` for
  multi-worker deployments — the default `memory://` is per-process only.
- Uploaded files are validated by extension and size (`app/utils/file_upload.py`);
  serve them from behind your web server/CDN in production rather than Flask's
  static handler if traffic is significant.
- The chat typing indicator is intentionally ephemeral (in-memory, per-process) —
  it is a transient UI signal, not durable data, so it will not work correctly
  across multiple gunicorn workers without moving it to a shared store (e.g. Redis)
  if you scale horizontally. Messages, read receipts, and search are fully
  database-backed and unaffected by this.
- List-heavy admin/teacher/student views use SQLAlchemy `joinedload()` to avoid
  N+1 query patterns.

## Default Super Admin

Created by `seed.py` from your `.env` values (`admin@example.com` / `ChangeMe123!`).
Change the password after first login — there's no in-app UI for that yet, so
update it via a Python shell or a future admin profile page.
