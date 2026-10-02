"""
models/users.py — CRUD on the Users table.
"""
from __future__ import annotations
from typing import Any

from db import execute, query_all, query_one


def get(user_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT UserID, Username, Email, FirstName, LastName,
               PreferredCurrency, Role, IsActive, CreatedAt, LastLoginAt
          FROM Users WHERE UserID = ?;
        """,
        (user_id,),
    )


def list_all(*, only_active: bool = False) -> list[dict[str, Any]]:
    sql = """
        SELECT UserID, Username, Email, FirstName, LastName,
               PreferredCurrency, Role, IsActive, CreatedAt, LastLoginAt
          FROM Users
    """
    if only_active:
        sql += "WHERE IsActive = 1 "
    sql += "ORDER BY UserID;"
    return query_all(sql)


def update_profile(user_id: int, *, first_name: str, last_name: str,
                   email: str, preferred_currency: str) -> None:
    execute(
        """
        UPDATE Users
           SET FirstName = ?, LastName = ?, Email = ?, PreferredCurrency = ?
         WHERE UserID = ?;
        """,
        (first_name, last_name, email.lower(), preferred_currency.upper(), user_id),
    )


def set_active(user_id: int, is_active: bool) -> None:
    execute("UPDATE Users SET IsActive = ? WHERE UserID = ?;",
            (1 if is_active else 0, user_id))


def change_password(user_id: int, new_hash: str) -> None:
    execute("UPDATE Users SET PasswordHash = ? WHERE UserID = ?;",
            (new_hash, user_id))


def platform_stats() -> dict[str, int]:
    """Aggregate totals for the Admin dashboard. No per-user financial data."""
    row = query_one(
        """
        SELECT
          (SELECT COUNT(*) FROM Users)             AS TotalUsers,
          (SELECT COUNT(*) FROM Users WHERE IsActive = 1) AS ActiveUsers,
          (SELECT COUNT(*) FROM Users WHERE Role = 'Admin') AS Admins,
          (SELECT COUNT(*) FROM Accounts)          AS TotalAccounts,
          (SELECT COUNT(*) FROM Transactions)      AS TotalTransactions,
          (SELECT COUNT(*) FROM Categories WHERE UserID IS NULL) AS SystemCategories,
          (SELECT COUNT(*) FROM Categories WHERE UserID IS NOT NULL) AS UserCategories,
          (SELECT COUNT(*) FROM RecurringPayments WHERE IsActive = 1) AS ActiveRecurring,
          (SELECT COUNT(*) FROM Budgets)           AS TotalBudgets;
        """
    )
    return row or {}
