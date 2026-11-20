
import sqlite3
import hashlib
import secrets
import hmac


# ---------------- CONFIGURATION ----------------

DB_NAME = "dfip_users.db"
ITERATIONS = 600_000


# ---------------- DATABASE SETUP ----------------

def setup_database():
    with sqlite3.connect(DB_NAME) as connection:

        # Users table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)

        # Remember Me tokens table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS remember_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE,
                token_hash TEXT NOT NULL UNIQUE,
                FOREIGN KEY (username)
                    REFERENCES users(username)
                    ON DELETE CASCADE
            )
        """)

        # Cases table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id INTEGER PRIMARY KEY,
                case_title TEXT NOT NULL,
                client_name TEXT NOT NULL,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL
                    CHECK (priority BETWEEN 1 AND 3),
                status TEXT NOT NULL DEFAULT 'Open'
            )
        """)


def save_case(case_data):
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("""
            INSERT INTO cases (
                case_id,
                case_title,
                client_name,
                description,
                priority,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            case_data["case_id"],
            case_data["case_title"],
            case_data["client_name"],
            case_data["description"],
            case_data["priority"],
            case_data["status"]
        ))


def get_all_cases():
    with sqlite3.connect(DB_NAME) as connection:
        connection.row_factory = sqlite3.Row

        cursor = connection.execute("""
            SELECT
                case_id,
                case_title,
                client_name,
                description,
                priority,
                status
            FROM cases
        """)

        cases = [dict(row) for row in cursor.fetchall()]

    return cases

# ---------------- PASSWORD HASHING ----------------

def hash_password(password):
    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        ITERATIONS
    )

    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(password, stored_hash):
    try:
        salt_hex, hash_hex = stored_hash.split(":")

        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            ITERATIONS
        )

        return hmac.compare_digest(
            new_hash.hex(),
            hash_hex
        )

    except (ValueError, TypeError):
        return False


# ---------------- REGISTER USER ----------------

def register_user(username, password):
    username = username.strip()

    if not username or not password:
        return False, "Please fill in all fields!"

    if len(username) > 50:
        return False, "Username must be 50 characters or less!"

    if len(password) < 8:
        return False, "Password must be at least 8 characters!"

    password_hash = hash_password(password)

    try:
        with sqlite3.connect(DB_NAME) as connection:

            connection.execute(
                """
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
                """,
                (username, password_hash)
            )

        return True, "Account created successfully!"

    except sqlite3.IntegrityError:
        return False, "That username is already taken!"


# ---------------- LOGIN USER ----------------

def login_user(username, password):
    username = username.strip()

    if not username or not password:
        return False

    with sqlite3.connect(DB_NAME) as connection:

        result = connection.execute(
            """
            SELECT password_hash
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

    if result and verify_password(password, result[0]):
        return True

    return False

def create_remember_token(username):
    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    with sqlite3.connect(DB_NAME) as connection:
        connection.execute(
            """
            INSERT INTO remember_tokens (username, token_hash)
            VALUES (?, ?)
            """,
            (username, token_hash)
        )

    return token


def login_with_remember_token(token):
    if not token:
        return None

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    with sqlite3.connect(DB_NAME) as connection:
        result = connection.execute(
            """
            SELECT username
            FROM remember_tokens
            WHERE token_hash = ?
            """,
            (token_hash,)
        ).fetchone()

    return result[0] if result else None


def revoke_remember_token(token):
    if not token:
        return

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    with sqlite3.connect(DB_NAME) as connection:
        connection.execute(
            """
            DELETE FROM remember_tokens
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

# ---------------- INITIALISE DATABASE ----------------

setup_database()

print("DATABASE.PY HAS LOADED")

print("create_remember_token exists:",
      "create_remember_token" in globals())

print("login_with_remember_token exists:",
      "login_with_remember_token" in globals())

print("revoke_remember_token exists:",
      "revoke_remember_token" in globals())
