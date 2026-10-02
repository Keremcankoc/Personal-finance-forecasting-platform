"""
gui/
====
customtkinter-based desktop GUI. Each screen lives in its own module.
This package's __init__ exposes a few shared formatting helpers used by
multiple views, so we don't sprinkle the same code across files.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from config import UI_DATE_FORMAT, CURRENCY_SYMBOL


def fmt_money(value: Any, *, with_symbol: bool = True) -> str:
    """Format a Decimal/float as Turkish-style currency: ₺ 1.234,56"""
    if value is None:
        return "—"
    n = float(value)
    formatted = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY_SYMBOL} {formatted}" if with_symbol else formatted


def fmt_date(value: Any) -> str:
    """Format a date as dd.mm.yyyy."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime(UI_DATE_FORMAT)
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime(UI_DATE_FORMAT)
    except (ValueError, TypeError):
        return str(value)


def parse_date(text: str) -> date | None:
    """Parse a dd.mm.yyyy string into a date (returns None if blank)."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, UI_DATE_FORMAT).date()
    except ValueError:
        # Accept ISO format too as a fallback
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Date must be dd.mm.yyyy (got '{text}')") from exc


def parse_decimal(text: str) -> Decimal:
    """Parse '1.234,56' or '1234.56' into a Decimal."""
    text = (text or "").strip().replace(" ", "")
    if not text:
        raise ValueError("Amount is required.")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: '{text}'") from exc
