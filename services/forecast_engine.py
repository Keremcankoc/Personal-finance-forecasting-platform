"""
services/forecast_engine.py
===========================
Savings forecasting and What-if simulation.

For the **Savings Forecast** we delegate the heavy lifting to the
`Q2_SavingsForecast` query in `queries/advanced_queries.sql` (the project
spec: don't re-implement DB aggregations in Python).

For the **What-if Simulator** we combine the same baseline with the
user's hypothetical ScenarioItems to produce per-month projected balances
vs the baseline.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from db import query_all, query_one, run_named_query
from models import accounts


# ---------------------------------------------------------------------------
# Baseline (last-3-month average income & expense)
# ---------------------------------------------------------------------------
@dataclass
class Baseline:
    avg_income: Decimal
    avg_expense: Decimal
    starting_balance: Decimal

    @property
    def avg_net(self) -> Decimal:
        return self.avg_income - self.avg_expense


def baseline_for_user(user_id: int) -> Baseline:
    row = query_one(
        """
        SELECT
          COALESCE(AVG(CASE WHEN TransactionType = 'Income' THEN MonthlyTotal END), 0)  AS AvgIncome,
          COALESCE(AVG(CASE WHEN TransactionType = 'Expense' THEN MonthlyTotal END), 0) AS AvgExpense
        FROM (
          SELECT FORMAT(TransactionDate, 'yyyy-MM') AS YM,
                 TransactionType,
                 SUM(Amount) AS MonthlyTotal
            FROM Transactions
           WHERE UserID = ?
             AND TransactionDate >= DATEADD(MONTH, -3, CAST(GETDATE() AS DATE))
           GROUP BY FORMAT(TransactionDate, 'yyyy-MM'), TransactionType
        ) m;
        """,
        (user_id,),
    )
    avg_income = Decimal(str(row["AvgIncome"])) if row else Decimal("0")
    avg_expense = Decimal(str(row["AvgExpense"])) if row else Decimal("0")
    start_bal = accounts.total_balance_for_user(user_id)
    return Baseline(avg_income=avg_income, avg_expense=avg_expense,
                    starting_balance=start_bal)


# ---------------------------------------------------------------------------
# Savings Forecast (Q2)
# ---------------------------------------------------------------------------
def savings_forecast(user_id: int, months_ahead: int) -> list[dict[str, Any]]:
    """Wraps queries/advanced_queries.sql @name=Q2_SavingsForecast."""
    if not 1 <= months_ahead <= 60:
        raise ValueError("months_ahead must be 1..60")
    return run_named_query("Q2_SavingsForecast", (user_id, months_ahead))


# ---------------------------------------------------------------------------
# What-if simulator
# ---------------------------------------------------------------------------
_FREQ_TO_MONTHLY = {
    "OneTime": None,    # applied once at month 1
    "Daily":   Decimal("30"),
    "Weekly":  Decimal("4.345"),
    "Monthly": Decimal("1"),
    "Yearly":  Decimal("1") / Decimal("12"),
}


def _monthly_equivalent(amount: Decimal, freq: str) -> Decimal:
    if freq == "OneTime":
        return Decimal("0")
    factor = _FREQ_TO_MONTHLY[freq]
    return (amount * factor).quantize(Decimal("0.01"))


def simulate_scenario(user_id: int, scenario_id: int) -> dict[str, Any]:
    """
    Returns a dict with:
      months: [1, 2, ..., N]
      baseline_balance: [...]            (starting_balance + cumulative net per month)
      scenario_balance: [...]            (baseline + cumulative scenario delta per month)
      monthly_baseline_net: Decimal
      monthly_scenario_delta: Decimal    (net of all recurring scenario items)
      one_time_total: Decimal            (sum of OneTime items, applied at month 1)
    """
    sc = query_one(
        "SELECT ScenarioName, SimulationMonths FROM Scenarios "
        "WHERE ScenarioID = ? AND UserID = ?;",
        (scenario_id, user_id),
    )
    if not sc:
        raise ValueError("Scenario not found.")
    months = int(sc["SimulationMonths"])

    base = baseline_for_user(user_id)
    items = query_all(
        """
        SELECT Amount, TransactionType, Frequency
          FROM ScenarioItems WHERE ScenarioID = ?;
        """,
        (scenario_id,),
    )

    monthly_delta = Decimal("0")
    one_time_total = Decimal("0")
    for it in items:
        amt = Decimal(str(it["Amount"]))
        sign = Decimal("1") if it["TransactionType"] == "Income" else Decimal("-1")
        if it["Frequency"] == "OneTime":
            one_time_total += sign * amt
        else:
            monthly_delta += sign * _monthly_equivalent(amt, it["Frequency"])

    months_list: list[int] = []
    baseline_balance: list[float] = []
    scenario_balance: list[float] = []
    base_running = base.starting_balance
    sc_running = base.starting_balance + one_time_total  # one-time hits at t=1
    for m in range(1, months + 1):
        base_running += base.avg_net
        sc_running += base.avg_net + monthly_delta
        months_list.append(m)
        baseline_balance.append(float(base_running))
        scenario_balance.append(float(sc_running))

    return {
        "months": months_list,
        "baseline_balance": baseline_balance,
        "scenario_balance": scenario_balance,
        "monthly_baseline_net": base.avg_net,
        "monthly_scenario_delta": monthly_delta,
        "one_time_total": one_time_total,
        "scenario_name": sc["ScenarioName"],
    }
