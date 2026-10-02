"""
models/categories.py — CRUD on the Categories table.

Categories with UserID IS NULL are system defaults visible to everyone.
Categories with UserID = ? are the user's personal customisations.
"""
from __future__ import annotations
from typing import Any

from db import execute, execute_returning_id, query_all, query_one


def list_visible_to_user(user_id: int, *, only_active: bool = True,
                         category_type: str | None = None) -> list[dict[str, Any]]:
    """Categories the user can see: system defaults + their own custom ones."""
    where = ["(UserID IS NULL OR UserID = ?)"]
    params: list[Any] = [user_id]
    if only_active:
        where.append("IsActive = 1")
    if category_type in ("Income", "Expense"):
        where.append("CategoryType = ?")
        params.append(category_type)
    sql = f"""
        SELECT CategoryID, CategoryName, CategoryType, Description, IconName,
               ParentCategoryID, UserID, IsActive
          FROM Categories
         WHERE {' AND '.join(where)}
         ORDER BY CategoryType, CategoryName;
    """
    return query_all(sql, params)


def list_system_only(*, only_active: bool = True) -> list[dict[str, Any]]:
    sql = """
        SELECT CategoryID, CategoryName, CategoryType, Description, IconName,
               ParentCategoryID, UserID, IsActive
          FROM Categories
         WHERE UserID IS NULL
    """
    if only_active:
        sql += " AND IsActive = 1"
    sql += " ORDER BY CategoryType, CategoryName;"
    return query_all(sql)


def list_user_only(user_id: int, *, only_active: bool = True) -> list[dict[str, Any]]:
    sql = """
        SELECT CategoryID, CategoryName, CategoryType, Description, IconName,
               ParentCategoryID, UserID, IsActive
          FROM Categories
         WHERE UserID = ?
    """
    if only_active:
        sql += " AND IsActive = 1"
    sql += " ORDER BY CategoryType, CategoryName;"
    return query_all(sql, (user_id,))


def get(category_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT CategoryID, CategoryName, CategoryType, Description, IconName,
               ParentCategoryID, UserID, IsActive
          FROM Categories WHERE CategoryID = ?;
        """,
        (category_id,),
    )


def create(*, name: str, ctype: str, user_id: int | None,
           parent_id: int | None = None, description: str | None = None,
           icon: str | None = None) -> int:
    if ctype not in ("Income", "Expense"):
        raise ValueError("CategoryType must be 'Income' or 'Expense'.")
    sql = """
        INSERT INTO Categories
            (CategoryName, CategoryType, Description, IconName,
             ParentCategoryID, UserID, IsActive)
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """
    return execute_returning_id(sql, (name, ctype, description, icon, parent_id, user_id))


def update(category_id: int, *, name: str, ctype: str,
           parent_id: int | None, description: str | None,
           icon: str | None) -> None:
    if ctype not in ("Income", "Expense"):
        raise ValueError("CategoryType must be 'Income' or 'Expense'.")
    if parent_id == category_id:
        raise ValueError("A category cannot be its own parent.")
    execute(
        """
        UPDATE Categories
           SET CategoryName = ?, CategoryType = ?, Description = ?,
               IconName = ?, ParentCategoryID = ?
         WHERE CategoryID = ?;
        """,
        (name, ctype, description, icon, parent_id, category_id),
    )


def soft_delete(category_id: int) -> None:
    execute("UPDATE Categories SET IsActive = 0 WHERE CategoryID = ?;", (category_id,))


def restore(category_id: int) -> None:
    execute("UPDATE Categories SET IsActive = 1 WHERE CategoryID = ?;", (category_id,))


def is_system(category_id: int) -> bool:
    row = query_one("SELECT UserID FROM Categories WHERE CategoryID = ?;", (category_id,))
    return bool(row) and row["UserID"] is None
