"""
gui/analytics_view.py
=====================
Tabbed analytics dashboard. Each tab runs ONE of the five Phase 1
advanced queries (Q1–Q5 in queries/advanced_queries.sql) and renders
the result.

The aggregation work is deliberately delegated to T-SQL — the GUI only
plots / formats — so the project demonstrates database capability
rather than re-implementing it in Python.
"""
from __future__ import annotations
from collections import defaultdict
from tkinter import ttk
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui import fmt_money
from db import run_named_query


class AnalyticsView(ctk.CTkFrame):
    def __init__(self, parent, user_id: int):
        super().__init__(parent, fg_color="transparent")
        self.user_id = user_id
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        ctk.CTkLabel(self, text="Analytics & Advanced Queries",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        self.tabs.add("Q1 — Spending Trend")
        self.tabs.add("Q2 — Savings Forecast")
        self.tabs.add("Q3 — Top Categories")
        self.tabs.add("Q4 — Recurring Calendar")
        self.tabs.add("Q5 — Category Tree")

        self._build_q1(self.tabs.tab("Q1 — Spending Trend"))
        self._build_q2(self.tabs.tab("Q2 — Savings Forecast"))
        self._build_q3(self.tabs.tab("Q3 — Top Categories"))
        self._build_q4(self.tabs.tab("Q4 — Recurring Calendar"))
        self._build_q5(self.tabs.tab("Q5 — Category Tree"))

    # ==================================================================
    # Q1 — Monthly Spending Trend
    # ==================================================================
    def _build_q1(self, parent) -> None:
        ctk.CTkButton(parent, text="Run query",
                      command=lambda: self._run_q1(parent)
                      ).pack(anchor="w", padx=12, pady=10)
        self.q1_chart = ctk.CTkFrame(parent)
        self.q1_chart.pack(fill="both", expand=True, padx=12, pady=12)
        self._run_q1(parent)

    def _run_q1(self, parent) -> None:
        for w in self.q1_chart.winfo_children():
            w.destroy()
        try:
            rows = run_named_query("Q1_MonthlySpendingTrend", (self.user_id,))
        except Exception as exc:                            # noqa: BLE001
            ctk.CTkLabel(self.q1_chart, text=f"Query error: {exc}",
                         text_color="red").pack(pady=20)
            return
        if not rows:
            ctk.CTkLabel(self.q1_chart, text="No expense data in the last 6 months."
                         ).pack(pady=20)
            return

        # Pivot: months on x-axis, one line per top-category
        months_set: list[str] = []
        seen = set()
        for r in rows:
            if r["YearMonth"] not in seen:
                months_set.append(r["YearMonth"]); seen.add(r["YearMonth"])
        cats = sorted({r["TopCategory"] for r in rows})
        pivot = defaultdict(lambda: {m: 0.0 for m in months_set})
        for r in rows:
            pivot[r["TopCategory"]][r["YearMonth"]] = float(r["TotalSpent"] or 0)

        fig = Figure(figsize=(8, 4.5), dpi=100)
        ax = fig.add_subplot(111)
        for cat in cats:
            ys = [pivot[cat][m] for m in months_set]
            ax.plot(months_set, ys, marker="o", linewidth=2, label=cat)
        ax.set_title("Monthly spending by top-level category (last 6 months)")
        ax.set_xlabel("Month"); ax.set_ylabel("Total spent (TRY)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")
        for t in ax.get_xticklabels():
            t.set_rotation(30); t.set_ha("right")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.q1_chart)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ==================================================================
    # Q2 — Savings Forecast
    # ==================================================================
    def _build_q2(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(bar, text="Months ahead (1–60):"
                     ).pack(side="left", padx=4)
        self.q2_months = ctk.CTkEntry(bar, width=80)
        self.q2_months.insert(0, "6")
        self.q2_months.pack(side="left", padx=4)
        ctk.CTkButton(bar, text="Run forecast",
                      command=self._run_q2).pack(side="left", padx=4)

        self.q2_chart = ctk.CTkFrame(parent)
        self.q2_chart.pack(fill="both", expand=True, padx=12, pady=12)
        self._run_q2()

    def _run_q2(self) -> None:
        for w in self.q2_chart.winfo_children():
            w.destroy()
        try:
            n = int(self.q2_months.get())
            if not 1 <= n <= 60:
                raise ValueError("Out of range")
        except (TypeError, ValueError):
            ctk.CTkLabel(self.q2_chart, text="Months must be an integer 1–60",
                         text_color="red").pack(pady=20)
            return
        try:
            rows = run_named_query("Q2_SavingsForecast", (self.user_id, n))
        except Exception as exc:                            # noqa: BLE001
            ctk.CTkLabel(self.q2_chart, text=f"Query error: {exc}",
                         text_color="red").pack(pady=20)
            return

        months = [r["MonthOffset"] for r in rows]
        cum = [float(r["CumulativeNet"]) for r in rows]
        net = [float(r["MonthlyNet"]) for r in rows]

        fig = Figure(figsize=(8, 4.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(months, cum, marker="o", linewidth=2, label="Cumulative net savings")
        ax.bar(months, net, alpha=0.25, label="Monthly net")
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title(f"Savings forecast — next {n} months")
        ax.set_xlabel("Months ahead"); ax.set_ylabel("TRY")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.q2_chart)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ==================================================================
    # Q3 — Top 5 Categories with Budget Utilization
    # ==================================================================
    def _build_q3(self, parent) -> None:
        ctk.CTkButton(parent, text="Run query",
                      command=lambda: self._run_q3(parent)
                      ).pack(anchor="w", padx=12, pady=10)
        self.q3_chart = ctk.CTkFrame(parent)
        self.q3_chart.pack(fill="both", expand=True, padx=12, pady=12)
        self._run_q3(parent)

    def _run_q3(self, parent) -> None:
        import matplotlib.pyplot as plt
        for w in self.q3_chart.winfo_children():
            w.destroy()
        plt.close('all')
        try:
            rows = run_named_query("Q3_TopCategoriesBudgetUtilization",
                                   (self.user_id, self.user_id))
        except Exception as exc:                            # noqa: BLE001
            ctk.CTkLabel(self.q3_chart, text=f"Query error: {exc}",
                         text_color="red").pack(pady=20)
            return
        if not rows:
            ctk.CTkLabel(self.q3_chart, text="No expense data this month."
                         ).pack(pady=20)
            return

        labels = [r["CategoryName"] for r in rows]
        spent = [float(r["TotalSpent"] or 0) for r in rows]
        statuses = [r["Status"] for r in rows]
        colour_map = {"OK": "#3a8a3a", "WARNING": "#d6a52b",
                      "EXCEEDED": "#b03030", "NO BUDGET": "#888"}
        colours = [colour_map.get(s, "#3a7ab8") for s in statuses]

        # Reverse once so the highest-spending category sits at the top
        labels_r = labels[::-1]
        spent_r = spent[::-1]
        statuses_r = statuses[::-1]
        colours_r = colours[::-1]

        fig = Figure(figsize=(8, 4.5), dpi=100)
        ax = fig.add_subplot(111)
        bars = ax.barh(labels_r, spent_r, color=colours_r)
        ax.set_title("Top 5 spending categories — current month (colour = budget status)")
        ax.set_xlabel("TRY")
        # Use each bar's own y-coordinate to anchor its label
        for bar, s, st in zip(bars, spent_r, statuses_r):
            y = bar.get_y() + bar.get_height() / 2
            ax.text(s, y, f"  {fmt_money(s, with_symbol=False)} ({st})",
                    va="center", fontsize=9)
        ax.grid(True, axis="x", alpha=0.3)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.q3_chart)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ==================================================================
    # Q4 — Recurring Payment Calendar
    # ==================================================================
    def _build_q4(self, parent) -> None:
        ctk.CTkButton(parent, text="Run query",
                      command=lambda: self._run_q4(parent)
                      ).pack(anchor="w", padx=12, pady=10)
        wrap = ctk.CTkFrame(parent)
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        cols = ("Description", "Category", "Account", "Amount", "Type",
                "Frequency", "NextChargeDate", "DaysUntilCharge",
                "MonthlyEquivalent")
        self.q4_tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                    selectmode="browse")
        for c, w in zip(cols, (200, 150, 150, 110, 80, 100, 110, 90, 130)):
            self.q4_tree.heading(c, text=c)
            self.q4_tree.column(c, width=w, anchor="w")
        self.q4_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.q4_tree.yview)
        self.q4_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._run_q4(parent)

    def _run_q4(self, parent) -> None:
        from gui import fmt_date
        self.q4_tree.delete(*self.q4_tree.get_children())
        try:
            rows = run_named_query("Q4_RecurringPaymentCalendar", (self.user_id,))
        except Exception as exc:                            # noqa: BLE001
            self.q4_tree.insert("", "end", values=(f"Query error: {exc}",
                                                   "", "", "", "", "", "", "", ""))
            return
        for r in rows:
            self.q4_tree.insert("", "end", values=(
                r["Description"], r["CategoryName"], r["AccountName"],
                fmt_money(r["Amount"]), r["TransactionType"],
                r["Frequency"], fmt_date(r["NextChargeDate"]),
                r["DaysUntilCharge"], fmt_money(r["MonthlyEquivalent"]),
            ))

    # ==================================================================
    # Q5 — Recursive Category Hierarchy with Aggregated Spending
    # ==================================================================
    def _build_q5(self, parent) -> None:
        ctk.CTkButton(parent, text="Run query",
                      command=lambda: self._run_q5(parent)
                      ).pack(anchor="w", padx=12, pady=10)
        wrap = ctk.CTkFrame(parent)
        wrap.pack(fill="both", expand=True, padx=12, pady=12)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.q5_tree = ttk.Treeview(wrap, columns=("Spent", "TxCount"),
                                    show="tree headings", selectmode="browse")
        self.q5_tree.heading("#0", text="Category path")
        self.q5_tree.heading("Spent", text="Total spent (12 mo)")
        self.q5_tree.heading("TxCount", text="# Transactions")
        self.q5_tree.column("#0", width=420, anchor="w")
        self.q5_tree.column("Spent", width=180, anchor="e")
        self.q5_tree.column("TxCount", width=110, anchor="center")
        self.q5_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.q5_tree.yview)
        self.q5_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        self._run_q5(parent)

    def _run_q5(self, parent) -> None:
        self.q5_tree.delete(*self.q5_tree.get_children())
        try:
            rows = run_named_query("Q5_CategoryHierarchySpending", (self.user_id, self.user_id))
        except Exception as exc:                            # noqa: BLE001
            self.q5_tree.insert("", "end", text=f"Query error: {exc}",
                                values=("", ""))
            return

        # Build parent-child treeview off the recursive CTE result
        node_ids: dict[int, str] = {}
        for r in rows:
            parent_id = r["ParentCategoryID"]
            parent_iid = node_ids.get(parent_id, "") if parent_id else ""
            iid = self.q5_tree.insert(
                parent_iid, "end",
                text=f"{r['CategoryName']}",
                values=(fmt_money(r["TotalSpent"]), r["TxCount"]),
                open=True,
            )
            node_ids[r["CategoryID"]] = iid
