"""
models/accounts.py — CRUD on the Accounts table.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from db import execute, execute_returning_id, query_all, query_one


VALID_TYPES = ("Cash", "Bank", "CreditCard", "Savings", "Investment")


def list_for_user(user_id: int, *, only_active: bool = True) -> list[dict[str, Any]]:
    sql = """
        SELECT AccountID, UserID, AccountName, AccountType, Balance,
               Currency, IsActive, CreatedAt
          FROM Accounts
         WHERE UserID = ?
    """
    if only_active:
        sql += " AND IsActive = 1"
    sql += " ORDER BY AccountName;"
    return query_all(sql, (user_id,))


def get(account_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT AccountID, UserID, AccountName, AccountType, Balance,
               Currency, IsActive, CreatedAt
          FROM Accounts WHERE AccountID = ?;
        """,
        (account_id,),
    )


def create(*, user_id: int, name: str, account_type: str,
           initial_balance: Decimal | float = 0,
           currency: str = "TRY") -> int:
    if account_type not in VALID_TYPES:
        raise ValueError(f"AccountType must be one of {VALID_TYPES}")
    return execute_returning_id(
        """
        INSERT INTO Accounts (UserID, AccountName, AccountType, Balance,
                              Currency, IsActive, CreatedAt)
        VALUES (?, ?, ?, ?, ?, 1, GETDATE());
        """,
        (user_id, name, account_type, Decimal(str(initial_balance)), currency.upper()),
    )


def update(account_id: int, *, name: str, account_type: str,
           currency: str) -> None:
    if account_type not in VALID_TYPES:
        raise ValueError(f"AccountType must be one of {VALID_TYPES}")
    execute(
        """
        UPDATE Accounts
           SET AccountName = ?, AccountType = ?, Currency = ?
         WHERE AccountID = ?;
        """,
        (name, account_type, currency.upper(), account_id),
    )


def soft_delete(account_id: int) -> None:
    execute("UPDATE Accounts SET IsActive = 0 WHERE AccountID = ?;", (account_id,))


def adjust_balance(account_id: int, delta: Decimal) -> None:
    """Add `delta` (can be negative) to Balance. Used by the transactions layer."""
    execute("UPDATE Accounts SET Balance = Balance + ? WHERE AccountID = ?;",
            (Decimal(str(delta)), account_id))


def total_balance_for_user(user_id: int) -> Decimal:
    row = query_one(
        """
        SELECT COALESCE(SUM(Balance), 0) AS Total
          FROM Accounts WHERE UserID = ? AND IsActive = 1;
        """,
        (user_id,),
    )
    return Decimal(str(row["Total"])) if row else Decimal("0")
