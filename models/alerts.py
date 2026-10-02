"""
models/alerts.py — CRUD on the Alerts table.
"""
from __future__ import annotations
from typing import Any

from db import execute, execute_returning_id, query_all, query_one


VALID_TYPES = (
    "BudgetExceeded", "BudgetWarning", "UpcomingPayment",
    "SpendingAnomaly", "SystemNotification",
)


def list_for_user(user_id: int, *, only_unread: bool = False,
                  limit: int = 200) -> list[dict[str, Any]]:
    sql = f"""
        SELECT TOP ({int(limit)})
               AlertID, UserID, AlertType, Title, Message, IsRead, CreatedAt,
               RelatedBudgetID, RelatedRecurringPaymentID
          FROM Alerts
         WHERE UserID = ?
    """
    if only_unread:
        sql += " AND IsRead = 0"
    sql += " ORDER BY CreatedAt DESC;"
    return query_all(sql, (user_id,))


def get(alert_id: int) -> dict[str, Any] | None:
    return query_one(
        "SELECT * FROM Alerts WHERE AlertID = ?;",
        (alert_id,),
    )


def create(*, user_id: int, alert_type: str, title: str, message: str,
           related_budget_id: int | None = None,
           related_recurring_id: int | None = None) -> int:
    if alert_type not in VALID_TYPES:
        raise ValueError(f"AlertType must be one of {VALID_TYPES}")
    return execute_returning_id(
        """
        INSERT INTO Alerts (UserID, AlertType, Title, Message, IsRead,
                            CreatedAt, RelatedBudgetID, RelatedRecurringPaymentID)
        VALUES (?, ?, ?, ?, 0, GETDATE(), ?, ?);
        """,
        (user_id, alert_type, title, message, related_budget_id, related_recurring_id),
    )


def mark_read(alert_id: int) -> None:
    execute("UPDATE Alerts SET IsRead = 1 WHERE AlertID = ?;", (alert_id,))


def mark_all_read(user_id: int) -> None:
    execute("UPDATE Alerts SET IsRead = 1 WHERE UserID = ? AND IsRead = 0;", (user_id,))


def delete(alert_id: int) -> None:
    execute("DELETE FROM Alerts WHERE AlertID = ?;", (alert_id,))


def unread_count(user_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS C FROM Alerts WHERE UserID = ? AND IsRead = 0;",
        (user_id,),
    )
    return int(row["C"]) if row else 0


def already_exists_unread(*, user_id: int, alert_type: str,
                          related_budget_id: int | None = None,
                          related_recurring_id: int | None = None) -> bool:
    """Used by the alert engine to deduplicate: an unread alert of the same
    type and reference is treated as still pending; we don't reinsert."""
    row = query_one(
        """
        SELECT 1 AS X FROM Alerts
         WHERE UserID = ? AND AlertType = ? AND IsRead = 0
           AND ( (RelatedBudgetID IS NULL AND ? IS NULL) OR RelatedBudgetID = ? )
           AND ( (RelatedRecurringPaymentID IS NULL AND ? IS NULL)
                 OR RelatedRecurringPaymentID = ? );
        """,
        (user_id, alert_type,
         related_budget_id, related_budget_id,
         related_recurring_id, related_recurring_id),
    )
    return row is not None
