"""
models/recurring.py — CRUD on RecurringPayments and due-charge processing.
"""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta

from db import cursor_scope, execute, execute_returning_id, query_all, query_one


VALID_FREQS = ("Daily", "Weekly", "Biweekly", "Monthly", "Quarterly", "Yearly")


def _advance(d: date, freq: str) -> date:
    if freq == "Daily":     return d + timedelta(days=1)
    if freq == "Weekly":    return d + timedelta(weeks=1)
    if freq == "Biweekly":  return d + timedelta(weeks=2)
    if freq == "Monthly":   return d + relativedelta(months=1)
    if freq == "Quarterly": return d + relativedelta(months=3)
    if freq == "Yearly":    return d + relativedelta(years=1)
    raise ValueError(f"Unknown frequency: {freq}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def list_for_user(user_id: int, *, only_active: bool = True) -> list[dict[str, Any]]:
    sql = """
        SELECT r.RecurringPaymentID, r.UserID, r.AccountID, r.CategoryID,
               r.Amount, r.TransactionType, r.Frequency, r.StartDate,
               r.EndDate, r.NextChargeDate, r.Description, r.IsActive,
               r.CreatedAt, a.AccountName, c.CategoryName
          FROM RecurringPayments r
          JOIN Accounts a   ON a.AccountID = r.AccountID
          JOIN Categories c ON c.CategoryID = r.CategoryID
         WHERE r.UserID = ?
    """
    if only_active:
        sql += " AND r.IsActive = 1"
    sql += " ORDER BY r.NextChargeDate;"
    return query_all(sql, (user_id,))


def get(rp_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT RecurringPaymentID, UserID, AccountID, CategoryID, Amount,
               TransactionType, Frequency, StartDate, EndDate,
               NextChargeDate, Description, IsActive, CreatedAt
          FROM RecurringPayments WHERE RecurringPaymentID = ?;
        """,
        (rp_id,),
    )


def create(*, user_id: int, account_id: int, category_id: int,
           amount: Decimal | float, ttype: str, frequency: str,
           start_date: date, next_charge_date: date | None,
           end_date: date | None, description: str) -> int:
    if ttype not in ("Income", "Expense"):
        raise ValueError("TransactionType must be 'Income' or 'Expense'.")
    if frequency not in VALID_FREQS:
        raise ValueError(f"Frequency must be one of {VALID_FREQS}")
    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Amount must be > 0.")
    next_charge = next_charge_date or start_date
    return execute_returning_id(
        """
        INSERT INTO RecurringPayments
            (UserID, AccountID, CategoryID, Amount, TransactionType,
             Frequency, StartDate, EndDate, NextChargeDate, Description,
             IsActive, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, GETDATE());
        """,
        (user_id, account_id, category_id, amt, ttype, frequency,
         start_date, end_date, next_charge, description),
    )


def update(rp_id: int, *, account_id: int, category_id: int,
           amount: Decimal | float, ttype: str, frequency: str,
           start_date: date, end_date: date | None,
           next_charge_date: date, description: str) -> None:
    if ttype not in ("Income", "Expense"):
        raise ValueError("TransactionType must be 'Income' or 'Expense'.")
    if frequency not in VALID_FREQS:
        raise ValueError(f"Frequency must be one of {VALID_FREQS}")
    execute(
        """
        UPDATE RecurringPayments
           SET AccountID = ?, CategoryID = ?, Amount = ?, TransactionType = ?,
               Frequency = ?, StartDate = ?, EndDate = ?, NextChargeDate = ?,
               Description = ?
         WHERE RecurringPaymentID = ?;
        """,
        (account_id, category_id, Decimal(str(amount)), ttype, frequency,
         start_date, end_date, next_charge_date, description, rp_id),
    )


def soft_delete(rp_id: int) -> None:
    execute("UPDATE RecurringPayments SET IsActive = 0 WHERE RecurringPaymentID = ?;", (rp_id,))


def restore(rp_id: int) -> None:
    execute("UPDATE RecurringPayments SET IsActive = 1 WHERE RecurringPaymentID = ?;", (rp_id,))


# ---------------------------------------------------------------------------
# Process due charges
# ---------------------------------------------------------------------------
def process_due_charges(user_id: int, today: date | None = None) -> int:
    """
    Walk active recurring payments and, for every one whose NextChargeDate is
    <= today and not past EndDate, generate a Transaction and advance
    NextChargeDate. Returns the count of generated transactions.
    """
    today = today or date.today()
    generated = 0
    rps = query_all(
        """
        SELECT RecurringPaymentID, AccountID, CategoryID, Amount,
               TransactionType, Frequency, EndDate, NextChargeDate, Description
          FROM RecurringPayments
         WHERE UserID = ? AND IsActive = 1 AND NextChargeDate <= ?
           AND (EndDate IS NULL OR NextChargeDate <= EndDate);
        """,
        (user_id, today),
    )
    for rp in rps:
        next_d = rp["NextChargeDate"]
        while next_d <= today and (rp["EndDate"] is None or next_d <= rp["EndDate"]):
            with cursor_scope() as cur:
                cur.execute(
                    """
                    INSERT INTO Transactions
                        (UserID, AccountID, CategoryID, Amount, TransactionType,
                         TransactionDate, Description, IsRecurring, CreatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, GETDATE());
                    """,
                    (user_id, rp["AccountID"], rp["CategoryID"],
                     Decimal(str(rp["Amount"])), rp["TransactionType"],
                     next_d, rp["Description"]),
                )
                signed = Decimal(str(rp["Amount"])) if rp["TransactionType"] == "Income" \
                         else -Decimal(str(rp["Amount"]))
                cur.execute(
                    "UPDATE Accounts SET Balance = Balance + ? WHERE AccountID = ?;",
                    (signed, rp["AccountID"]),
                )
            generated += 1
            next_d = _advance(next_d, rp["Frequency"])
        execute(
            "UPDATE RecurringPayments SET NextChargeDate = ? WHERE RecurringPaymentID = ?;",
            (next_d, rp["RecurringPaymentID"]),
        )
    return generated
