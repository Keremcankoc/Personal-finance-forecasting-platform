"""
auth.py
=======
Registration, login, and password helpers. Uses bcrypt for password hashing
and reads/writes the `Users` table via parameterised queries.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import bcrypt

from db import execute, execute_returning_id, query_one


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    """Return a bcrypt hash of `plain` as a UTF-8 string suitable for storage."""
    if not plain:
        raise ValueError("Password must not be empty.")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, stored_hash: str) -> bool:
    """Return True if `plain` matches `stored_hash`."""
    if not plain or not stored_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,50}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_registration(username: str, email: str, password: str,
                           first_name: str, last_name: str) -> None:
    if not _USERNAME_RE.match(username or ""):
        raise ValueError("Username must be 3–50 chars: letters, digits, _ . -")
    if not _EMAIL_RE.match(email or ""):
        raise ValueError("Email format is invalid.")
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if not first_name.strip() or not last_name.strip():
        raise ValueError("First and last name are required.")


def username_exists(username: str) -> bool:
    row = query_one("SELECT 1 AS x FROM Users WHERE Username = ?;", (username,))
    return row is not None


def email_exists(email: str) -> bool:
    row = query_one("SELECT 1 AS x FROM Users WHERE Email = ?;", (email,))
    return row is not None


def register_user(*, username: str, email: str, password: str,
                  first_name: str, last_name: str,
                  preferred_currency: str = "TRY",
                  role: str = "User") -> int:
    """
    Insert a new user. Returns the new UserID. Raises ValueError on bad
    input or duplicate username/email.
    """
    _validate_registration(username, email, password, first_name, last_name)
    if role not in ("User", "Admin"):
        raise ValueError("Role must be 'User' or 'Admin'.")
    if username_exists(username):
        raise ValueError("Username is already taken.")
    if email_exists(email):
        raise ValueError("Email is already registered.")

    pw_hash = hash_password(password)
    sql = """
        INSERT INTO Users
            (Username, Email, PasswordHash, FirstName, LastName,
             PreferredCurrency, Role, IsActive, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE());
    """
    new_id = execute_returning_id(sql, (
        username.strip(), email.strip().lower(), pw_hash,
        first_name.strip(), last_name.strip(),
        preferred_currency.upper(), role,
    ))
    return new_id


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login(username_or_email: str, password: str) -> dict[str, Any] | None:
    """
    Try to authenticate. Returns the user dict on success, None on failure.
    On success, updates LastLoginAt.
    """
    if not username_or_email or not password:
        return None

    user = query_one(
        """
        SELECT UserID, Username, Email, PasswordHash, FirstName, LastName,
               PreferredCurrency, Role, IsActive, CreatedAt, LastLoginAt
          FROM Users
         WHERE (Username = ? OR Email = ?) AND IsActive = 1;
        """,
        (username_or_email, username_or_email.lower()),
    )
    if not user:
        return None
    if not verify_password(password, user["PasswordHash"]):
        return None

    execute("UPDATE Users SET LastLoginAt = GETDATE() WHERE UserID = ?;",
            (user["UserID"],))
    user["LastLoginAt"] = datetime.now()
    return user
