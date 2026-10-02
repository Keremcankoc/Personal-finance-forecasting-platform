"""
services/alert_engine.py
========================
Generates alerts based on the current state of the user's budgets and
upcoming recurring payments. Designed to be called once on login, or
whenever the user clicks "Refresh alerts" in the UI.

Two checks:
  1. For each active budget, compute period-to-date spending and:
       - if spent >= 100% -> 'BudgetExceeded'
       - else if spent >= 80% -> 'BudgetWarning'
  2. For each active recurring payment whose NextChargeDate is within
     the next N days -> 'UpcomingPayment'.

Duplicates are avoided via models.alerts.already_exists_unread().
"""
from __future__ import annotations
from datetime import date, timedelta

from config import (
    BUDGET_WARNING_THRESHOLD,
    BUDGET_EXCEEDED_THRESHOLD,
    RECURRING_PAYMENT_LOOKAHEAD_DAYS,
)
from db import query_all
from models import alerts


def _fmt_currency(amount) -> str:
    """Use Turkish-style formatting: ₺ 1.234,56"""
    n = float(amount or 0)
    formatted = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"\u20BA {formatted}"


def check_budgets(user_id: int, today: date | None = None) -> int:
    """Insert budget warning/exceeded alerts. Returns number of alerts created."""
    today = today or date.today()
    rows = query_all(
        """
        SELECT b.BudgetID, b.BudgetAmount, c.CategoryName,
               b.StartDate, b.EndDate,
               COALESCE(SUM(CASE WHEN t.TransactionType = 'Expense'
                                  AND t.TransactionDate BETWEEN b.StartDate AND b.EndDate
                                 THEN t.Amount ELSE 0 END), 0) AS Spent
          FROM Budgets b
          JOIN Categories c ON c.CategoryID = b.CategoryID
          LEFT JOIN Transactions t
                 ON t.UserID = b.UserID AND t.CategoryID = b.CategoryID
         WHERE b.UserID = ?
           AND b.StartDate <= ? AND b.EndDate >= ?
         GROUP BY b.BudgetID, b.BudgetAmount, c.CategoryName, b.StartDate, b.EndDate;
        """,
        (user_id, today, today),
    )
    created = 0
    for r in rows:
        amt = float(r["BudgetAmount"]) or 0.0
        spent = float(r["Spent"]) or 0.0
        pct = (spent / amt * 100.0) if amt > 0 else 0.0
        bid = int(r["BudgetID"])

        if pct >= BUDGET_EXCEEDED_THRESHOLD:
            kind = "BudgetExceeded"
            title = f"Budget exceeded: {r['CategoryName']}"
            msg = (f"You have spent {_fmt_currency(spent)} of "
                   f"{_fmt_currency(amt)} ({pct:.1f}%) on '{r['CategoryName']}' "
                   f"in this period.")
        elif pct >= BUDGET_WARNING_THRESHOLD:
            kind = "BudgetWarning"
            title = f"Approaching budget limit: {r['CategoryName']}"
            msg = (f"You are at {pct:.1f}% of your budget for "
                   f"'{r['CategoryName']}' ({_fmt_currency(spent)} of "
                   f"{_fmt_currency(amt)}).")
        else:
            continue

        if alerts.already_exists_unread(user_id=user_id, alert_type=kind,
                                        related_budget_id=bid):
            continue
        alerts.create(user_id=user_id, alert_type=kind, title=title,
                      message=msg, related_budget_id=bid)
        created += 1
    return created


def check_upcoming_payments(user_id: int, today: date | None = None,
                            lookahead_days: int = RECURRING_PAYMENT_LOOKAHEAD_DAYS) -> int:
    """Insert 'UpcomingPayment' alerts. Returns the number created."""
    today = today or date.today()
    horizon = today + timedelta(days=lookahead_days)
    rows = query_all(
        """
        SELECT r.RecurringPaymentID, r.Amount, r.Description, r.NextChargeDate,
               r.TransactionType, c.CategoryName
          FROM RecurringPayments r
          JOIN Categories c ON c.CategoryID = r.CategoryID
         WHERE r.UserID = ? AND r.IsActive = 1
           AND r.NextChargeDate BETWEEN ? AND ?
           AND (r.EndDate IS NULL OR r.EndDate >= r.NextChargeDate);
        """,
        (user_id, today, horizon),
    )
    created = 0
    for r in rows:
        rid = int(r["RecurringPaymentID"])
        if alerts.already_exists_unread(user_id=user_id,
                                        alert_type="UpcomingPayment",
                                        related_recurring_id=rid):
            continue
        days = (r["NextChargeDate"] - today).days
        when = "today" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
        title = f"Upcoming payment: {r['Description']}"
        msg = (f"'{r['Description']}' ({r['CategoryName']}, "
               f"{_fmt_currency(r['Amount'])}) is due {when} "
               f"({r['NextChargeDate'].strftime('%d.%m.%Y')}).")
        alerts.create(user_id=user_id, alert_type="UpcomingPayment",
                      title=title, message=msg,
                      related_recurring_id=rid)
        created += 1
    return created


def run_all_checks(user_id: int) -> dict[str, int]:
    """Run both checks. Called on login from main.py."""
    return {
        "budget_alerts": check_budgets(user_id),
        "payment_alerts": check_upcoming_payments(user_id),
    }
