"""
models/transactions.py — CRUD on the Transactions table.

Every create/update/delete keeps Accounts.Balance in sync so the dashboard
displays the correct denormalised balance (Phase 1 design decision §2.3).
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Any

from db import cursor_scope, query_all, query_one


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def list_for_user(user_id: int, *,
                  date_from: date | None = None,
                  date_to: date | None = None,
                  account_id: int | None = None,
                  category_id: int | None = None,
                  ttype: str | None = None,
                  limit: int = 500) -> list[dict[str, Any]]:
    """Return transactions for the user, with optional filters."""
    where = ["t.UserID = ?"]
    params: list[Any] = [user_id]
    if date_from:
        where.append("t.TransactionDate >= ?")
        params.append(date_from)
    if date_to:
        where.append("t.TransactionDate <= ?")
        params.append(date_to)
    if account_id:
        where.append("t.AccountID = ?")
        params.append(account_id)
    if category_id:
        where.append("t.CategoryID = ?")
        params.append(category_id)
    if ttype in ("Income", "Expense"):
        where.append("t.TransactionType = ?")
        params.append(ttype)

    sql = f"""
        SELECT TOP ({int(limit)})
               t.TransactionID, t.UserID, t.AccountID, t.CategoryID,
               t.Amount, t.TransactionType, t.TransactionDate,
               t.Description, t.Notes, t.IsRecurring, t.CreatedAt,
               a.AccountName, c.CategoryName
          FROM Transactions t
          JOIN Accounts a   ON a.AccountID = t.AccountID
          JOIN Categories c ON c.CategoryID = t.CategoryID
         WHERE {' AND '.join(where)}
         ORDER BY t.TransactionDate DESC, t.TransactionID DESC;
    """
    return query_all(sql, params)


def get(transaction_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT TransactionID, UserID, AccountID, CategoryID, Amount,
               TransactionType, TransactionDate, Description, Notes,
               IsRecurring, CreatedAt
          FROM Transactions WHERE TransactionID = ?;
        """,
        (transaction_id,),
    )


# ---------------------------------------------------------------------------
# Mutations (use a single transaction so balance + insert stay consistent)
# ---------------------------------------------------------------------------
def _signed_delta(amount: Decimal, ttype: str) -> Decimal:
    return amount if ttype == "Income" else -amount


def create(*, user_id: int, account_id: int, category_id: int,
           amount: Decimal | float, ttype: str, txn_date: date,
           description: str | None = None, notes: str | None = None,
           is_recurring: bool = False) -> int:
    if ttype not in ("Income", "Expense"):
        raise ValueError("TransactionType must be 'Income' or 'Expense'.")
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Amount must be > 0.")

    with cursor_scope() as cur:
        cur.execute(
            """
            INSERT INTO Transactions
                (UserID, AccountID, CategoryID, Amount, TransactionType,
                 TransactionDate, Description, Notes, IsRecurring, CreatedAt)
            OUTPUT INSERTED.TransactionID
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE());
            """,
            (user_id, account_id, category_id, amt, ttype, txn_date,
             description, notes, 1 if is_recurring else 0),
        )
        row = cur.fetchone()
        new_id = int(row[0]) if row and row[0] is not None else 0
        cur.execute(
            "UPDATE Accounts SET Balance = Balance + ? WHERE AccountID = ?;",
            (_signed_delta(amt, ttype), account_id),
        )
        return new_id


def update(transaction_id: int, *, account_id: int, category_id: int,
           amount: Decimal | float, ttype: str, txn_date: date,
           description: str | None, notes: str | None) -> None:
    if ttype not in ("Income", "Expense"):
        raise ValueError("TransactionType must be 'Income' or 'Expense'.")
    new_amt = Decimal(str(amount))
    if new_amt <= 0:
        raise ValueError("Amount must be > 0.")

    with cursor_scope() as cur:
        cur.execute(
            """
            SELECT AccountID, Amount, TransactionType
              FROM Transactions WHERE TransactionID = ?;
            """,
            (transaction_id,),
        )
        old = cur.fetchone()
        if not old:
            raise ValueError("Transaction not found.")
        old_account_id, old_amount, old_ttype = int(old[0]), Decimal(str(old[1])), old[2]

        # Reverse old effect on the old account
        cur.execute(
            "UPDATE Accounts SET Balance = Balance - ? WHERE AccountID = ?;",
            (_signed_delta(old_amount, old_ttype), old_account_id),
        )
        # Apply new effect on the (possibly new) account
        cur.execute(
            "UPDATE Accounts SET Balance = Balance + ? WHERE AccountID = ?;",
            (_signed_delta(new_amt, ttype), account_id),
        )
        cur.execute(
            """
            UPDATE Transactions
               SET AccountID = ?, CategoryID = ?, Amount = ?,
                   TransactionType = ?, TransactionDate = ?,
                   Description = ?, Notes = ?
             WHERE TransactionID = ?;
            """,
            (account_id, category_id, new_amt, ttype, txn_date,
             description, notes, transaction_id),
        )


def delete(transaction_id: int) -> None:
    """Hard delete (Transactions has no IsActive flag)."""
    with cursor_scope() as cur:
        cur.execute(
            "SELECT AccountID, Amount, TransactionType FROM Transactions WHERE TransactionID = ?;",
            (transaction_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        account_id, amount, ttype = int(row[0]), Decimal(str(row[1])), row[2]
        cur.execute(
            "UPDATE Accounts SET Balance = Balance - ? WHERE AccountID = ?;",
            (_signed_delta(amount, ttype), account_id),
        )
        cur.execute("DELETE FROM Transactions WHERE TransactionID = ?;", (transaction_id,))


# ---------------------------------------------------------------------------
# Aggregate helpers used by the dashboard widgets
# ---------------------------------------------------------------------------
def monthly_summary_for_user(user_id: int, months_back: int = 6) -> list[dict[str, Any]]:
    """Income / Expense totals per month for the last N months."""
    return query_all(
        """
        SELECT FORMAT(TransactionDate, 'yyyy-MM') AS YearMonth,
               TransactionType,
               SUM(Amount) AS Total
          FROM Transactions
         WHERE UserID = ?
           AND TransactionDate >= DATEADD(MONTH, -?, CAST(GETDATE() AS DATE))
         GROUP BY FORMAT(TransactionDate, 'yyyy-MM'), TransactionType
         ORDER BY YearMonth;
        """,
        (user_id, months_back),
    )
