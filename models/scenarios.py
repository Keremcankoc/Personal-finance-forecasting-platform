"""
models/scenarios.py — CRUD on Scenarios and ScenarioItems.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any

from db import execute, execute_returning_id, query_all, query_one


VALID_ITEM_FREQS = ("OneTime", "Daily", "Weekly", "Monthly", "Yearly")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------
def list_for_user(user_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT ScenarioID, UserID, ScenarioName, Description,
               SimulationMonths, CreatedAt
          FROM Scenarios WHERE UserID = ?
         ORDER BY CreatedAt DESC;
        """,
        (user_id,),
    )


def get(scenario_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT ScenarioID, UserID, ScenarioName, Description,
               SimulationMonths, CreatedAt
          FROM Scenarios WHERE ScenarioID = ?;
        """,
        (scenario_id,),
    )


def create(*, user_id: int, name: str, description: str | None,
           simulation_months: int) -> int:
    if not 1 <= simulation_months <= 60:
        raise ValueError("SimulationMonths must be between 1 and 60.")
    return execute_returning_id(
        """
        INSERT INTO Scenarios (UserID, ScenarioName, Description,
                               SimulationMonths, CreatedAt)
        VALUES (?, ?, ?, ?, GETDATE());
        """,
        (user_id, name, description, simulation_months),
    )


def update(scenario_id: int, *, name: str, description: str | None,
           simulation_months: int) -> None:
    if not 1 <= simulation_months <= 60:
        raise ValueError("SimulationMonths must be between 1 and 60.")
    execute(
        """
        UPDATE Scenarios
           SET ScenarioName = ?, Description = ?, SimulationMonths = ?
         WHERE ScenarioID = ?;
        """,
        (name, description, simulation_months, scenario_id),
    )


def delete(scenario_id: int) -> None:
    """ScenarioItems CASCADE-delete with the parent scenario."""
    execute("DELETE FROM Scenarios WHERE ScenarioID = ?;", (scenario_id,))


# ---------------------------------------------------------------------------
# Scenario items
# ---------------------------------------------------------------------------
def list_items(scenario_id: int) -> list[dict[str, Any]]:
    return query_all(
        """
        SELECT si.ScenarioItemID, si.ScenarioID, si.CategoryID,
               si.ItemDescription, si.Amount, si.TransactionType,
               si.Frequency, c.CategoryName
          FROM ScenarioItems si
          LEFT JOIN Categories c ON c.CategoryID = si.CategoryID
         WHERE si.ScenarioID = ?
         ORDER BY si.ScenarioItemID;
        """,
        (scenario_id,),
    )


def add_item(*, scenario_id: int, category_id: int | None,
             description: str, amount: Decimal | float,
             ttype: str, frequency: str) -> int:
    if ttype not in ("Income", "Expense"):
        raise ValueError("TransactionType must be 'Income' or 'Expense'.")
    if frequency not in VALID_ITEM_FREQS:
        raise ValueError(f"Frequency must be one of {VALID_ITEM_FREQS}")
    return execute_returning_id(
        """
        INSERT INTO ScenarioItems (ScenarioID, CategoryID, ItemDescription,
                                   Amount, TransactionType, Frequency)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (scenario_id, category_id, description, Decimal(str(amount)), ttype, frequency),
    )


def delete_item(item_id: int) -> None:
    execute("DELETE FROM ScenarioItems WHERE ScenarioItemID = ?;", (item_id,))
