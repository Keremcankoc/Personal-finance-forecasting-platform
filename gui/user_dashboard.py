"""
gui/user_dashboard.py
=====================
Main shell for users (Role = 'User'). A left sidebar lists every CRUD
screen plus Analytics and What-if. Each click swaps the right-hand pane
to the relevant view.
"""
from __future__ import annotations
from decimal import Decimal
import customtkinter as ctk

from config import APP_NAME
from gui import fmt_money
from models import accounts, alerts, transactions
from .accounts_view import AccountsView
from .categories_view import CategoriesView
from .transactions_view import TransactionsView
from .recurring_view import RecurringView
from .budgets_view import BudgetsView
from .scenarios_view import ScenariosView
from .analytics_view import AnalyticsView
from .alerts_view import AlertsView


class UserDashboard(ctk.CTk):
    def __init__(self, user: dict):
        super().__init__()
        self.user = user
        self.user_id = int(user["UserID"])
        self.title(f"{APP_NAME} — {user['FirstName']} {user['LastName']}")
        self.geometry("1280x780")
        self.minsize(1100, 680)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self.content = ctk.CTkFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._current_view = None
        self.show_summary()

    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, width=220, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ns")
        bar.grid_propagate(False)

        ctk.CTkLabel(bar, text="Personal Finance",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     wraplength=200).pack(pady=(18, 4))
        ctk.CTkLabel(bar, text=f"{self.user['FirstName']}",
                     text_color="gray").pack(pady=(0, 18))

        items = [
            ("Summary",       self.show_summary),
            ("Accounts",      lambda: self._swap(AccountsView)),
            ("Transactions",  lambda: self._swap(TransactionsView)),
            ("Categories",    lambda: self._swap(CategoriesView)),
            ("Budgets",       lambda: self._swap(BudgetsView)),
            ("Recurring",     lambda: self._swap(RecurringView)),
            ("Scenarios",     lambda: self._swap(ScenariosView)),
            ("Analytics",     lambda: self._swap(AnalyticsView)),
            ("Alerts",        lambda: self._swap(AlertsView)),
        ]
        for label, cmd in items:
            ctk.CTkButton(bar, text=label, width=190, anchor="w", command=cmd
                          ).pack(padx=14, pady=4)

        ctk.CTkLabel(bar, text="").pack(expand=True)
        ctk.CTkButton(bar, text="Sign out", width=190,
                      fg_color="#a14040", hover_color="#7c2828",
                      command=self._logout).pack(padx=14, pady=14)

    # ------------------------------------------------------------------
    def _swap(self, view_cls) -> None:
        if self._current_view is not None:
            self._current_view.destroy()
        self._current_view = view_cls(self.content, user_id=self.user_id)
        self._current_view.grid(row=0, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    def show_summary(self) -> None:
        if self._current_view is not None:
            self._current_view.destroy()
        view = ctk.CTkFrame(self.content, fg_color="transparent")
        view.grid(row=0, column=0, sticky="nsew")
        self._current_view = view

        ctk.CTkLabel(view, text=f"Welcome back, {self.user['FirstName']}.",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(anchor="w", padx=24, pady=(24, 6))
        ctk.CTkLabel(view, text="Quick overview of your finances.",
                     text_color="gray").pack(anchor="w", padx=24, pady=(0, 18))

        # KPI cards
        kpi = ctk.CTkFrame(view, fg_color="transparent")
        kpi.pack(fill="x", padx=24)
        for i in range(4):
            kpi.grid_columnconfigure(i, weight=1, uniform="kpi")

        total_balance = accounts.total_balance_for_user(self.user_id)
        ms = transactions.monthly_summary_for_user(self.user_id, months_back=1)
        income_this_month = sum(
            (Decimal(str(r["Total"])) for r in ms if r["TransactionType"] == "Income"),
            Decimal("0"),
        )
        expense_this_month = sum(
            (Decimal(str(r["Total"])) for r in ms if r["TransactionType"] == "Expense"),
            Decimal("0"),
        )
        unread = alerts.unread_count(self.user_id)

        self._kpi_card(kpi, 0, "Total balance", fmt_money(total_balance))
        self._kpi_card(kpi, 1, "Income (recent)", fmt_money(income_this_month))
        self._kpi_card(kpi, 2, "Expense (recent)", fmt_money(expense_this_month))
        self._kpi_card(kpi, 3, "Unread alerts", str(unread))

        ctk.CTkLabel(
            view,
            text=("Use the sidebar to manage your accounts, transactions, "
                  "budgets, recurring payments, what-if scenarios, and to "
                  "view analytics. Alerts about budget limits and upcoming "
                  "payments appear in the Alerts screen."),
            wraplength=900, justify="left",
        ).pack(anchor="w", padx=24, pady=24)

    @staticmethod
    def _kpi_card(parent, col: int, title: str, value: str) -> None:
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        ctk.CTkLabel(card, text=title, text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card, text=value,
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(anchor="w", padx=14, pady=(0, 14))

    # ------------------------------------------------------------------
    def _logout(self) -> None:
        self.destroy()
        # main.py registers an after-destroy hook to relaunch the login window.
