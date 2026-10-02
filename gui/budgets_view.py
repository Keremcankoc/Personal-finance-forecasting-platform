"""
gui/budgets_view.py — Budget CRUD + per-budget utilization display.
"""
from __future__ import annotations
from datetime import date
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui import fmt_money, fmt_date, parse_date, parse_decimal
from models import budgets, categories


class BudgetsView(ctk.CTkFrame):
    def __init__(self, parent, user_id: int):
        super().__init__(parent, fg_color="transparent")
        self.user_id = user_id
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self._refresh()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        ctk.CTkLabel(header, text="Budgets",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="+ New budget",
                      command=self._open_create_dialog).pack(side="right")

        cols = ("BudgetID", "Category", "Period",
                "BudgetAmount", "Spent", "PctUsed",
                "StartDate", "EndDate")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w in zip(cols, (70, 200, 80, 130, 130, 80, 110, 110)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 16))
        ctk.CTkButton(btns, text="Edit", command=self._edit
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete", fg_color="#a14040",
                      hover_color="#7c2828", command=self._delete
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh
                      ).pack(side="right")

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for b in budgets.list_for_user(self.user_id):
            util = budgets.utilization(b["BudgetID"]) or {"Spent": 0, "BudgetAmount": b["BudgetAmount"]}
            spent = float(util["Spent"] or 0)
            amount = float(util["BudgetAmount"] or 1)
            pct = (spent / amount * 100.0) if amount else 0.0
            self.tree.insert("", "end", iid=str(b["BudgetID"]), values=(
                b["BudgetID"], b["CategoryName"], b["PeriodType"],
                fmt_money(b["BudgetAmount"]),
                fmt_money(spent),
                f"{pct:.1f}%",
                fmt_date(b["StartDate"]),
                fmt_date(b["EndDate"]),
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _open_create_dialog(self) -> None:
        BudgetDialog(self, on_save=self._refresh, user_id=self.user_id)

    def _edit(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        BudgetDialog(self, on_save=self._refresh, user_id=self.user_id,
                     budget=budgets.get(bid))

    def _delete(self) -> None:
        bid = self._selected_id()
        if bid is None:
            return
        if not messagebox.askyesno("Delete", "Delete this budget?"):
            return
        budgets.delete(bid)
        self._refresh()


class BudgetDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, user_id: int, budget: dict | None = None):
        super().__init__(parent)
        self.on_save = on_save
        self.user_id = user_id
        self.budget = budget
        self.title("Budget")
        self.geometry("460x500")
        self.transient(parent)
        self.grab_set()
        self._cats = [c for c in categories.list_visible_to_user(user_id)
                      if c["CategoryType"] == "Expense"]
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Category (Expense)"
                     ).pack(anchor="w", padx=18, pady=(18, 2))
        self._cat_lookup = {f"{c['CategoryID']} — {c['CategoryName']}":
                            c["CategoryID"] for c in self._cats}
        self.cb_cat = ctk.CTkComboBox(self, width=420,
                                      values=list(self._cat_lookup) or ["(none)"])
        self.cb_cat.pack(padx=18)

        ctk.CTkLabel(self, text="Amount").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_amt = ctk.CTkEntry(self, width=420)
        self.e_amt.pack(padx=18)

        ctk.CTkLabel(self, text="Period").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_period = ctk.CTkComboBox(self, width=420,
                                         values=["Weekly", "Monthly", "Yearly"])
        self.cb_period.set("Monthly")
        self.cb_period.pack(padx=18)

        ctk.CTkLabel(self, text="Start date (dd.mm.yyyy)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_start = ctk.CTkEntry(self, width=420)
        self.e_start.insert(0, date.today().replace(day=1).strftime("%d.%m.%Y"))
        self.e_start.pack(padx=18)

        ctk.CTkLabel(self, text="End date (dd.mm.yyyy)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_end = ctk.CTkEntry(self, width=420)
        self.e_end.pack(padx=18)

        if self.budget:
            for k, v in self._cat_lookup.items():
                if v == self.budget["CategoryID"]:
                    self.cb_cat.set(k); break
            self.e_amt.delete(0, "end")
            self.e_amt.insert(0, str(self.budget["BudgetAmount"]).replace(".", ","))
            self.cb_period.set(self.budget["PeriodType"])
            self.e_start.delete(0, "end")
            self.e_start.insert(0, fmt_date(self.budget["StartDate"]))
            self.e_end.delete(0, "end")
            self.e_end.insert(0, fmt_date(self.budget["EndDate"]))

        ctk.CTkButton(self, text="Save", command=self._save
                      ).pack(pady=20, padx=18, fill="x")

    def _save(self) -> None:
        try:
            cid = self._cat_lookup[self.cb_cat.get()]
            amt = parse_decimal(self.e_amt.get())
            period = self.cb_period.get()
            start = parse_date(self.e_start.get())
            end = parse_date(self.e_end.get())
            if start is None or end is None or end < start:
                raise ValueError("End date must be on/after start date.")
            if self.budget:
                budgets.update(self.budget["BudgetID"], category_id=cid,
                               amount=amt, period_type=period,
                               start_date=start, end_date=end)
            else:
                budgets.create(user_id=self.user_id, category_id=cid,
                               amount=amt, period_type=period,
                               start_date=start, end_date=end)
        except Exception as exc:                                # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
