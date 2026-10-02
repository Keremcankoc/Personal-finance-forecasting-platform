"""
models/budgets.py — CRUD on the Budgets table.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Any

from db import execute, execute_returning_id, query_all, query_one


VALID_PERIODS = ("Weekly", "Monthly", "Yearly")


def list_for_user(user_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT b.BudgetID, b.UserID, b.CategoryID, b.BudgetAmount,
               b.PeriodType, b.StartDate, b.EndDate, b.CreatedAt,
               c.CategoryName
          FROM Budgets b
          JOIN Categories c ON c.CategoryID = b.CategoryID
         WHERE b.UserID = ?
         ORDER BY b.EndDate DESC, b.CategoryID;
        """,
        (user_id,),
    )


def list_active_for_user(user_id: int, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    return query_all(
        """
        SELECT b.BudgetID, b.UserID, b.CategoryID, b.BudgetAmount,
               b.PeriodType, b.StartDate, b.EndDate, b.CreatedAt,
               c.CategoryName
          FROM Budgets b
          JOIN Categories c ON c.CategoryID = b.CategoryID
         WHERE b.UserID = ? AND b.StartDate <= ? AND b.EndDate >= ?
         ORDER BY b.CategoryID;
        """,
        (user_id, today, today),
    )


def get(budget_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT BudgetID, UserID, CategoryID, BudgetAmount, PeriodType,
               StartDate, EndDate, CreatedAt
          FROM Budgets WHERE BudgetID = ?;
        """,
        (budget_id,),
    )


def create(*, user_id: int, category_id: int, amount: Decimal | float,
           period_type: str, start_date: date, end_date: date) -> int:
    if period_type not in VALID_PERIODS:
        raise ValueError(f"PeriodType must be one of {VALID_PERIODS}")
    return execute_returning_id(
        """
        INSERT INTO Budgets (UserID, CategoryID, BudgetAmount, PeriodType,
                             StartDate, EndDate, CreatedAt)
        VALUES (?, ?, ?, ?, ?, ?, GETDATE());
        """,
        (user_id, category_id, Decimal(str(amount)), period_type, start_date, end_date),
    )


def update(budget_id: int, *, category_id: int, amount: Decimal | float,
           period_type: str, start_date: date, end_date: date) -> None:
    if period_type not in VALID_PERIODS:
        raise ValueError(f"PeriodType must be one of {VALID_PERIODS}")
    execute(
        """
        UPDATE Budgets
           SET CategoryID = ?, BudgetAmount = ?, PeriodType = ?,
               StartDate = ?, EndDate = ?
         WHERE BudgetID = ?;
        """,
        (category_id, Decimal(str(amount)), period_type, start_date, end_date, budget_id),
    )


def delete(budget_id: int) -> None:
    """Hard delete; first NULL out any Alerts that reference this budget."""
    from db import cursor_scope
    with cursor_scope() as cur:
        cur.execute(
            "UPDATE Alerts SET RelatedBudgetID = NULL WHERE RelatedBudgetID = ?;",
            (budget_id,),
        )
        cur.execute("DELETE FROM Budgets WHERE BudgetID = ?;", (budget_id,))


def utilization(budget_id: int) -> dict[str, Any] | None:
    """How much of this budget has been spent so far in its period."""
    return query_one(
        """
        SELECT b.BudgetID, b.BudgetAmount,
               COALESCE(SUM(CASE WHEN t.TransactionType = 'Expense'
                                  AND t.TransactionDate BETWEEN b.StartDate AND b.EndDate
                                 THEN t.Amount ELSE 0 END), 0) AS Spent
          FROM Budgets b
          LEFT JOIN Transactions t
                 ON t.UserID = b.UserID AND t.CategoryID = b.CategoryID
         WHERE b.BudgetID = ?
         GROUP BY b.BudgetID, b.BudgetAmount;
        """,
        (budget_id,),
    )
