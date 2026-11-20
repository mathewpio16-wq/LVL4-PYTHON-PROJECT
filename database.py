"""Database layer for DFIP.

Handles user accounts, password hashing, "Remember Me" tokens and reports.
Every function opens its own short-lived connection, so it is safe to
call from background threads.
"""

import hashlib
import os
import shutil
from pathlib import Path
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

# ---------------- CONFIGURATION ----------------

# Use a stable per-user folder, not the current working directory or an
# extracted ZIP folder. Updating or moving the application keeps its data.
APP_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".local" / "share")) / "DFIP_Case_Management"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_NAME = str(USER_DATA_DIR / "dfip_users.db")

# One-time migration: copy an existing database from the application folder.
# Never overwrite the persistent database with an empty packaged database.
legacy_db = APP_DIR / "dfip_users.db"
if not Path(DB_NAME).exists() and legacy_db.is_file():
    shutil.copy2(legacy_db, DB_NAME)

ITERATIONS = 600_000
MAX_USERNAME_LENGTH = 50
MAX_NAME_LENGTH = 100
MAX_PHONE_LENGTH = 20
TEMP_PASSWORD_LENGTH = 12
# No look-alike characters (0/O, 1/l/I) so it is easy to read out.
TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
TOKEN_LIFETIME_SECONDS = 30 * 24 * 60 * 60  # 30 days

ROLES = ("user", "expert", "admin")
MAX_REPORT_TITLE_LENGTH = 100
MAX_REPORT_TEXT_LENGTH = 5000
DATE_FORMAT = "%Y-%m-%d"


# ---------------- CONNECTION HELPER ----------------

@contextmanager
def get_connection():
    """Yield a connection that commits on success and always closes."""
    connection = sqlite3.connect(DB_NAME)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


# ---------------- DATABASE SETUP ----------------

def setup_database():
    """Create the tables if they do not exist yet."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Older versions had no forced password change.
        present = [row[1] for row in connection.execute(
            "PRAGMA table_info(users)")]
        if "must_change_password" not in present:
            connection.execute(
                "ALTER TABLE users ADD COLUMN must_change_password "
                "INTEGER NOT NULL DEFAULT 0")

        # Older versions had no contact details. Existing accounts get
        # blank values (shown as "-" in the app).
        for column in ("full_name", "phone"):
            present = [row[1] for row in connection.execute(
                "PRAGMA table_info(users)")]
            if column not in present:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {column} "
                    "TEXT NOT NULL DEFAULT ''")

        # Older versions had no roles. Add the column, and make sure
        # there is always at least one admin (the oldest account).
        user_columns = [row[1] for row in connection.execute(
            "PRAGMA table_info(users)")]
        if "role" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL "
                "DEFAULT 'user'")
        has_admin = connection.execute(
            "SELECT 1 FROM users WHERE role = 'admin'").fetchone()
        if not has_admin:
            connection.execute(
                "UPDATE users SET role = 'admin' "
                "WHERE id = (SELECT MIN(id) FROM users)")

        # Older versions had no expiry column. Tokens are disposable,
        # so rebuild the table (users simply have to log in again).
        columns = [row[1] for row in connection.execute(
            "PRAGMA table_info(remember_tokens)")]
        if columns and "expires_at" not in columns:
            connection.execute("DROP TABLE remember_tokens")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (username)
                    REFERENCES users(username)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT NOT NULL COLLATE NOCASE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                outcome TEXT,
                completed_date TEXT,
                completed_by TEXT,
                assigned_to TEXT COLLATE NOCASE,
                FOREIGN KEY (author)
                    REFERENCES users(username)
                    ON DELETE CASCADE
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY,
                case_title TEXT NOT NULL,
                client_name TEXT NOT NULL,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 3),
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)

        # Every new report belongs to a registered investigation case.
        # Existing reports are preserved with NULL case_id (legacy reports).
        report_columns = [row[1] for row in connection.execute(
            "PRAGMA table_info(reports)")]
        if "case_id" not in report_columns:
            connection.execute(
                "ALTER TABLE reports ADD COLUMN case_id INTEGER "
                "REFERENCES cases(case_id) ON DELETE RESTRICT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_case_id "
            "ON reports(case_id)")

        # Older versions had no assignment. Existing reports start
        # unassigned until an admin assigns them to an expert.
        report_columns = [row[1] for row in connection.execute(
            "PRAGMA table_info(reports)")]
        if "assigned_to" not in report_columns:
            connection.execute(
                "ALTER TABLE reports ADD COLUMN assigned_to TEXT")

        # Report titles and descriptions are permanent once submitted.
        # No role (admins included) may change them, and this trigger
        # enforces that inside SQLite itself, so even a future coding
        # mistake cannot bypass it. Outcomes, assignment and deletion
        # are not affected.
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS reports_text_is_locked
            BEFORE UPDATE OF title, description ON reports
            BEGIN
                SELECT RAISE(ABORT,
                    'Report titles and descriptions cannot be changed.');
            END
        """)


# ---------------- PASSWORD HASHING ----------------

def _derive_key(password, salt, iterations):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations)


def hash_password(password):
    """Return 'iterations$salt$hash' so the cost can be raised later."""
    salt = secrets.token_bytes(16)
    digest = _derive_key(password, salt, ITERATIONS)
    return f"{ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    """Check a password. Also accepts the old 'salt:hash' format."""
    try:
        if "$" in stored_hash:
            iterations_text, salt_hex, hash_hex = stored_hash.split("$")
            iterations = int(iterations_text)
        else:
            salt_hex, hash_hex = stored_hash.split(":")
            iterations = ITERATIONS

        new_hash = _derive_key(
            password, bytes.fromhex(salt_hex), iterations)
        return hmac.compare_digest(new_hash.hex(), hash_hex)

    except (ValueError, TypeError, AttributeError):
        return False


_dummy_hash = None


def _burn_time(password):
    """Hash against a fake record so unknown usernames take equally long."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("dummy-password")
    verify_password(password, _dummy_hash)


# ---------------- PASSWORD RULES ----------------

def _check_password_rules(password):
    """Return an error message, or None if the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return (f"Password must be at least "
                f"{MIN_PASSWORD_LENGTH} characters!")
    if len(password) > MAX_PASSWORD_LENGTH:
        return (f"Password must be {MAX_PASSWORD_LENGTH} "
                f"characters or less!")
    return None


# ---------------- CONTACT DETAILS ----------------

_NAME_EXTRA_CHARACTERS = " -'."
_PHONE_EXTRA_CHARACTERS = " +-()"
_DIGITS = "0123456789"


def _check_contact_details(full_name, phone):
    """Return an error message, or None if both values are acceptable."""
    if not full_name or not phone:
        return "Please fill in all fields!"

    if len(full_name) < 2 or len(full_name) > MAX_NAME_LENGTH:
        return (f"Full name must be between 2 and "
                f"{MAX_NAME_LENGTH} characters!")

    if (not any(ch.isalpha() for ch in full_name)
            or not all(ch.isalpha() or ch in _NAME_EXTRA_CHARACTERS
                       for ch in full_name)):
        return ("Full name can only contain letters, spaces, "
                "hyphens, apostrophes and full stops!")

    if len(phone) > MAX_PHONE_LENGTH:
        return f"Phone number must be {MAX_PHONE_LENGTH} characters or less!"

    if not all(ch in _DIGITS or ch in _PHONE_EXTRA_CHARACTERS
               for ch in phone):
        return "Phone number can only contain digits, spaces, + - ( )!"

    digit_count = sum(1 for ch in phone if ch in _DIGITS)
    if not 7 <= digit_count <= 15:
        return "Phone number must contain 7 to 15 digits!"

    return None


def get_profile(username):
    """Return the user's details as a dict, or None if not found.

    Keys: username, full_name, phone, role, must_change_password.
    """
    with get_connection() as connection:
        row = connection.execute(
            "SELECT username, full_name, phone, role, must_change_password "
            "FROM users WHERE username = ?", (username,)).fetchone()
    if row is None:
        return None
    profile = dict(zip(
        ("username", "full_name", "phone", "role", "must_change_password"),
        row))
    profile["must_change_password"] = bool(profile["must_change_password"])
    return profile


# ---------------- REGISTER / LOGIN ----------------

def register_user(username, password, full_name, phone):
    """Create an account. Returns (success, message)."""
    username = username.strip()
    full_name = " ".join(full_name.split())  # tidy up extra spaces
    phone = phone.strip()

    if not username or not password:
        return False, "Please fill in all fields!"

    if len(username) > MAX_USERNAME_LENGTH:
        return False, (f"Username must be {MAX_USERNAME_LENGTH} "
                       f"characters or less!")

    problem = _check_password_rules(password)
    if problem:
        return False, problem

    problem = _check_contact_details(full_name, phone)
    if problem:
        return False, problem

    password_hash = hash_password(password)

    try:
        with get_connection() as connection:
            # The very first account becomes the administrator.
            user_count = connection.execute(
                "SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if user_count == 0 else "user"
            connection.execute(
                "INSERT INTO users "
                "(username, password_hash, full_name, phone, role) "
                "VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, full_name, phone, role))
        if role == "admin":
            return True, ("Account created successfully!\n"
                          "You are the first user, so you are the admin.")
        return True, "Account created successfully!"

    except sqlite3.IntegrityError:
        return False, "That username is already taken!"


def login_user(username, password):
    """Return the stored (correctly cased) username, or None on failure."""
    username = username.strip()

    if not username or not password or len(password) > MAX_PASSWORD_LENGTH:
        return None

    with get_connection() as connection:
        row = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (username,)).fetchone()

    if row is None:
        _burn_time(password)
        return None

    stored_username, stored_hash = row
    if verify_password(password, stored_hash):
        return stored_username
    return None


def change_password(username, current_password, new_password):
    """Change a password and sign out all remembered sessions."""
    if login_user(username, current_password) is None:
        return False, "Current password is incorrect!"

    problem = _check_password_rules(new_password)
    if problem:
        return False, problem

    if new_password == current_password:
        return False, "Your new password must be different from the old one!"

    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 "
            "WHERE username = ?",
            (hash_password(new_password), username))

    revoke_all_tokens(username)
    return True, "Password changed successfully!"


# ---------------- REMEMBER ME TOKENS ----------------

def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_remember_token(username):
    """Create a token valid for 30 days and return the raw value."""
    token = secrets.token_urlsafe(32)
    now = int(time.time())

    with get_connection() as connection:
        connection.execute(
            "DELETE FROM remember_tokens WHERE expires_at < ?", (now,))
        connection.execute(
            "INSERT INTO remember_tokens (username, token_hash, expires_at) "
            "VALUES (?, ?, ?)",
            (username, _hash_token(token), now + TOKEN_LIFETIME_SECONDS))

    return token


def redeem_remember_token(token):
    """Use a token to log in.

    The token is single-use: on success it is deleted and a fresh one is
    issued. Returns (username, new_token), or None if invalid/expired.
    """
    if not token:
        return None

    with get_connection() as connection:
        row = connection.execute(
            "SELECT u.username, t.expires_at, u.must_change_password "
            "FROM remember_tokens t "
            "JOIN users u ON u.username = t.username "
            "WHERE t.token_hash = ?",
            (_hash_token(token),)).fetchone()

        connection.execute(
            "DELETE FROM remember_tokens WHERE token_hash = ?",
            (_hash_token(token),))

    if row is None or row[1] < time.time() or row[2]:
        return None

    username = row[0]
    return username, create_remember_token(username)


def revoke_remember_token(token):
    """Delete one token (used on sign out)."""
    if not token:
        return
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM remember_tokens WHERE token_hash = ?",
            (_hash_token(token),))


def revoke_all_tokens(username):
    """Delete every remembered session for a user."""
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM remember_tokens WHERE username = ?", (username,))


# ---------------- ROLES AND PERMISSIONS ----------------
#
# Every function below takes the acting username and checks that user's
# role in the database itself. The GUI hiding a button is a convenience;
# these checks are what actually enforce the rules.
#
#   user   - submit reports, view ONLY their own reports
#   expert - view ONLY reports assigned to them, record and update
#            their outcome + completed date
#   admin  - view every report, assign/reopen/delete them, edit outcomes,
#            manage users
#
# Nobody - not even an admin - can change a report's title or description
# after it has been submitted.

def _get_role(connection, username):
    row = connection.execute(
        "SELECT role, must_change_password FROM users WHERE username = ?",
        (username,)).fetchone()
    if row is None:
        raise PermissionError("Your account no longer exists.")
    if row[1]:
        # Accounts with a temporary password can do nothing but change it.
        raise PermissionError(
            "You must change your temporary password before continuing.")
    return row[0]


def get_role(username):
    """Return a user's role, or None if the user does not exist."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT role FROM users WHERE username = ?",
            (username,)).fetchone()
    return row[0] if row else None


def _require_role(connection, username, allowed_roles):
    role = _get_role(connection, username)
    if role not in allowed_roles:
        raise PermissionError("You do not have permission to do that.")
    return role


# ---------------- REPORTS ----------------

_REPORT_FIELDS = ("id", "author", "title", "description", "created_at",
                  "outcome", "completed_date", "completed_by",
                  "assigned_to", "case_id")
_REPORT_COLUMNS = ", ".join(_REPORT_FIELDS)


def _row_to_report(row):
    return dict(zip(_REPORT_FIELDS, row))


def _fetch_visible_report(connection, actor, role, report_id):
    """Fetch a report, hiding other users' reports from plain users."""
    row = connection.execute(
        f"SELECT {_REPORT_COLUMNS} FROM reports WHERE id = ?",
        (report_id,)).fetchone()

    if row is None:
        raise PermissionError("Report not found.")

    report = _row_to_report(row)
    assigned = (report["assigned_to"] or "").lower()
    hidden = (
        (role == "user" and report["author"].lower() != actor.lower())
        or (role == "expert" and assigned != actor.lower())
    )
    if hidden:
        # Same message as "missing" so existence is not revealed.
        raise PermissionError("Report not found.")
    return report


def _check_report_text(title, description):
    if not title or not description:
        return "Please fill in the title and description!"
    if len(title) > MAX_REPORT_TITLE_LENGTH:
        return (f"Title must be {MAX_REPORT_TITLE_LENGTH} "
                f"characters or less!")
    if len(description) > MAX_REPORT_TEXT_LENGTH:
        return (f"Description must be {MAX_REPORT_TEXT_LENGTH} "
                f"characters or less!")
    return None


def _check_outcome(outcome, completed_date):
    if not outcome:
        return "Please enter an outcome!"
    if len(outcome) > MAX_REPORT_TEXT_LENGTH:
        return (f"Outcome must be {MAX_REPORT_TEXT_LENGTH} "
                f"characters or less!")
    try:
        datetime.strptime(completed_date, DATE_FORMAT)
    except ValueError:
        return "Date completed must look like YYYY-MM-DD!"
    return None


def submit_report(actor, title, description, case_id=None):
    """Submit a report tied to an existing case; return success and message."""
    title = title.strip()
    description = description.strip()
    problem = _check_report_text(title, description)
    if problem:
        return False, problem
    try:
        case_id = int(case_id)
        if case_id <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return False, "Select a valid case before submitting the report."

    with get_connection() as connection:
        _get_role(connection, actor)
        exists = connection.execute(
            "SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not exists:
            return False, "The selected case no longer exists."
        connection.execute(
            "INSERT INTO reports (author, title, description, created_at, case_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (actor, title, description, int(time.time()), case_id))
    return True, f"Report submitted for Case #{case_id}!"


def list_case_choices():
    """Cases available when creating a report (ID and title)."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT case_id, case_title FROM cases ORDER BY case_id DESC"
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def list_reports(actor):
    """Users: their own. Experts: those assigned to them. Admins: all."""
    with get_connection() as connection:
        role = _get_role(connection, actor)
        query = f"SELECT {_REPORT_COLUMNS} FROM reports"
        if role == "user":
            rows = connection.execute(
                query + " WHERE author = ? ORDER BY created_at DESC, id DESC",
                (actor,)).fetchall()
        elif role == "expert":
            rows = connection.execute(
                query + " WHERE assigned_to = ? "
                "ORDER BY created_at DESC, id DESC",
                (actor,)).fetchall()
        else:
            rows = connection.execute(
                query + " ORDER BY created_at DESC, id DESC").fetchall()
    return [_row_to_report(row) for row in rows]


def get_report(actor, report_id):
    """Return one report the actor is allowed to see."""
    with get_connection() as connection:
        role = _get_role(connection, actor)
        return _fetch_visible_report(connection, actor, role, report_id)


def complete_report(actor, report_id, outcome, completed_date):
    """Experts/admins record or change an outcome and its date.

    Experts can change an outcome on their assigned reports at any time
    (for example, after finding something new out). Only the outcome and
    date change; titles and descriptions stay locked.
    """
    outcome = outcome.strip()
    completed_date = completed_date.strip()

    with get_connection() as connection:
        role = _require_role(connection, actor, ("expert", "admin"))
        _fetch_visible_report(connection, actor, role, report_id)

        problem = _check_outcome(outcome, completed_date)
        if problem:
            return False, problem

        connection.execute(
            "UPDATE reports SET outcome = ?, completed_date = ?, "
            "completed_by = ? WHERE id = ?",
            (outcome, completed_date, actor, report_id))
    return True, "Outcome saved!"


def update_outcome(actor, report_id, outcome, completed_date):
    """Admin only: set, change or clear a report's outcome.

    Titles and descriptions are deliberately NOT editable here (or
    anywhere). Blank outcome + blank date reopens the report.
    """
    outcome = outcome.strip()
    completed_date = completed_date.strip()

    with get_connection() as connection:
        role = _require_role(connection, actor, ("admin",))
        _fetch_visible_report(connection, actor, role, report_id)

        if outcome or completed_date:
            problem = _check_outcome(outcome, completed_date)
            if problem:
                return False, problem
            completed_by = actor
        else:
            outcome = completed_date = completed_by = None

        connection.execute(
            "UPDATE reports SET outcome = ?, completed_date = ?, "
            "completed_by = ? WHERE id = ?",
            (outcome, completed_date, completed_by, report_id))

    if outcome is None:
        return True, "Report reopened."
    return True, "Outcome updated!"


def list_experts(actor):
    """Admin only. Returns the usernames of all experts."""
    with get_connection() as connection:
        _require_role(connection, actor, ("admin",))
        rows = connection.execute(
            "SELECT username FROM users WHERE role = 'expert' "
            "ORDER BY username").fetchall()
    return [row[0] for row in rows]


def assign_report(actor, report_id, expert):
    """Admin only. Assign a report to an expert, or None to unassign."""
    with get_connection() as connection:
        role = _require_role(connection, actor, ("admin",))
        _fetch_visible_report(connection, actor, role, report_id)

        if expert is None:
            connection.execute(
                "UPDATE reports SET assigned_to = NULL WHERE id = ?",
                (report_id,))
            return True, "Report unassigned."

        row = connection.execute(
            "SELECT username, role FROM users WHERE username = ?",
            (expert,)).fetchone()
        if row is None or row[1] != "expert":
            return False, "Reports can only be assigned to experts!"

        connection.execute(
            "UPDATE reports SET assigned_to = ? WHERE id = ?",
            (row[0], report_id))
    return True, f"Report assigned to {row[0]}."


def delete_report(actor, report_id):
    """Admin only."""
    with get_connection() as connection:
        _require_role(connection, actor, ("admin",))
        connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    return True, "Report deleted."


# ---------------- USER MANAGEMENT (ADMIN) ----------------

def _admin_count(connection):
    return connection.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]


def _generate_temporary_password():
    return "".join(secrets.choice(TEMP_PASSWORD_ALPHABET)
                   for _ in range(TEMP_PASSWORD_LENGTH))


def create_expert_account(actor, username, full_name, phone):
    """Admin only. Create an expert with a one-time temporary password.

    The expert must change that password the first time they sign in.
    Returns (success, message, temporary_password). The password is only
    stored hashed, so this is the one chance to read it.
    """
    username = username.strip()
    full_name = " ".join(full_name.split())
    phone = phone.strip()

    try:
        with get_connection() as connection:
            _require_role(connection, actor, ("admin",))

            if not username:
                return False, "Please fill in all fields!", None
            if len(username) > MAX_USERNAME_LENGTH:
                return False, (f"Username must be {MAX_USERNAME_LENGTH} "
                               f"characters or less!"), None

            problem = _check_contact_details(full_name, phone)
            if problem:
                return False, problem, None

            temporary_password = _generate_temporary_password()
            connection.execute(
                "INSERT INTO users (username, password_hash, full_name, "
                "phone, role, must_change_password) "
                "VALUES (?, ?, ?, ?, 'expert', 1)",
                (username, hash_password(temporary_password),
                 full_name, phone))

    except sqlite3.IntegrityError:
        return False, "That username is already taken!", None

    return True, f"Expert account created for {username}.", temporary_password


def list_users(actor):
    """Admin only. Returns (username, full_name, phone, role, must_change)."""
    with get_connection() as connection:
        _require_role(connection, actor, ("admin",))
        return connection.execute(
            "SELECT username, full_name, phone, role, must_change_password "
            "FROM users ORDER BY username").fetchall()


def set_role(actor, target, new_role):
    """Admin only. Cannot remove the last admin."""
    if new_role not in ROLES:
        return False, "Unknown role!"

    with get_connection() as connection:
        _require_role(connection, actor, ("admin",))

        row = connection.execute(
            "SELECT username, role FROM users WHERE username = ?",
            (target,)).fetchone()
        if row is None:
            return False, "That user does not exist!"

        if (row[1] == "admin" and new_role != "admin"
                and _admin_count(connection) <= 1):
            return False, "There must always be at least one admin!"

        connection.execute(
            "UPDATE users SET role = ? WHERE username = ?",
            (new_role, target))

        if new_role != "expert":
            # A non-expert cannot hold assignments.
            connection.execute(
                "UPDATE reports SET assigned_to = NULL "
                "WHERE assigned_to = ?", (target,))
    return True, f"{row[0]} is now {new_role}."


def delete_user(actor, target):
    """Admin only. Also deletes the user's reports and tokens."""
    with get_connection() as connection:
        _require_role(connection, actor, ("admin",))

        if target.lower() == actor.lower():
            return False, "You cannot delete your own account here!"

        row = connection.execute(
            "SELECT role FROM users WHERE username = ?",
            (target,)).fetchone()
        if row is None:
            return False, "That user does not exist!"

        if row[0] == "admin" and _admin_count(connection) <= 1:
            return False, "There must always be at least one admin!"

        connection.execute(
            "UPDATE reports SET assigned_to = NULL WHERE assigned_to = ?",
            (target,))
        connection.execute(
            "DELETE FROM users WHERE username = ?", (target,))
    return True, f"Deleted {target}."


# ---------------- INITIALISE DATABASE ----------------

setup_database()


# ---------------- CASE MANAGEMENT ----------------
def save_case(case_data):
    """Atomically insert a case and return its SQLite-generated Case ID.

    SQLite assigns the ID, avoiding duplicates when multiple users add cases.
    """
    with get_connection() as connection:
        cursor = connection.execute("""INSERT INTO cases
            (case_title, client_name, description, priority, status)
            VALUES (?, ?, ?, ?, ?)""", (
            case_data["case_title"], case_data["client_name"],
            case_data["description"], case_data["priority"],
            case_data.get("status", "Open")))
        return cursor.lastrowid


def get_all_cases():
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""SELECT case_id, case_title, client_name,
            description, priority, status FROM cases ORDER BY case_id""").fetchall()
        return [dict(row) for row in rows]


# ---------------- CASE LIFECYCLE & REPORT LINKS ----------------

def get_case_reports(actor, case_id):
    """Return reports linked to a case, respecting the existing report permissions."""
    case_id = int(case_id)
    return [report for report in list_reports(actor)
            if report["case_id"] == case_id]


def change_case_status(actor, case_id, new_status):
    """Move a case through Open -> In Progress -> Closed.

    Closing requires at least one report and all linked reports to have
    recorded outcomes. Reopening is possible for further investigation.
    """
    allowed = ("Open", "In Progress", "Closed")
    if new_status not in allowed:
        return False, "Invalid case status."
    with get_connection() as connection:
        role = _get_role(connection, actor)
        if role not in ("admin", "expert"):
            return False, "Only administrators or experts can change case status."
        case = connection.execute(
            "SELECT status FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if case is None:
            return False, "Case not found."
        current = case[0]
        transitions = {
            "Open": ("In Progress",),
            "In Progress": ("Open", "Closed"),
            "Closed": ("In Progress",),
        }
        if new_status == current:
            return False, "Case already has this status."
        if new_status not in transitions.get(current, ()):
            return False, "Move the case to In Progress before closing it."
        if new_status == "Closed":
            counts = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN outcome IS NULL OR "
                "TRIM(outcome) = '' THEN 1 ELSE 0 END) "
                "FROM reports WHERE case_id = ?", (case_id,)).fetchone()
            if counts[0] == 0:
                return False, "Add and complete at least one report before closing the case."
            if counts[1]:
                return False, "Complete all linked reports before closing the case."
        connection.execute("UPDATE cases SET status = ? WHERE case_id = ?",
                           (new_status, case_id))
    return True, f"Case #{case_id} changed to {new_status}."
