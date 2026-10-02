"""
gui/transactions_view.py — Transactions CRUD + filters.
"""
from __future__ import annotations
from datetime import date
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui import fmt_money, fmt_date, parse_date, parse_decimal
from models import accounts, categories, transactions


class TransactionsView(ctk.CTkFrame):
    def __init__(self, parent, user_id: int):
        super().__init__(parent, fg_color="transparent")
        self.user_id = user_id
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()
        self._refresh()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        ctk.CTkLabel(header, text="Transactions",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="+ New transaction",
                      command=self._open_create_dialog).pack(side="right")

        # Filter bar
        flt = ctk.CTkFrame(self)
        flt.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        for i in range(8):
            flt.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(flt, text="From").grid(row=0, column=0, padx=4, pady=8)
        self.e_from = ctk.CTkEntry(flt, placeholder_text="dd.mm.yyyy")
        self.e_from.grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkLabel(flt, text="To").grid(row=0, column=2, padx=4)
        self.e_to = ctk.CTkEntry(flt, placeholder_text="dd.mm.yyyy")
        self.e_to.grid(row=0, column=3, sticky="ew", padx=4)

        self.cb_account = ctk.CTkComboBox(flt, values=["(all accounts)"],
                                          width=160)
        self.cb_account.grid(row=0, column=4, sticky="ew", padx=4)

        self.cb_category = ctk.CTkComboBox(flt, values=["(all categories)"],
                                           width=160)
        self.cb_category.grid(row=0, column=5, sticky="ew", padx=4)

        self.cb_type = ctk.CTkComboBox(flt,
                                       values=["All", "Income", "Expense"],
                                       width=120)
        self.cb_type.set("All")
        self.cb_type.grid(row=0, column=6, sticky="ew", padx=4)

        ctk.CTkButton(flt, text="Apply", command=self._refresh
                      ).grid(row=0, column=7, padx=4)
        self._populate_filter_combos()

        # Table
        cols = ("TransactionID", "Date", "Type", "Amount",
                "Account", "Category", "Description")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w in zip(cols, (90, 100, 80, 130, 160, 200, 260)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        # Action buttons
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 16))
        ctk.CTkButton(btns, text="Edit", command=self._edit
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete", fg_color="#a14040",
                      hover_color="#7c2828", command=self._delete
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh
                      ).pack(side="right")

    def _populate_filter_combos(self) -> None:
        accs = accounts.list_for_user(self.user_id, only_active=False)
        self._account_lookup = {f"{a['AccountID']} — {a['AccountName']}":
                                a["AccountID"] for a in accs}
        self.cb_account.configure(values=["(all accounts)"] + list(self._account_lookup))
        self.cb_account.set("(all accounts)")

        cats = categories.list_visible_to_user(self.user_id, only_active=True)
        self._category_lookup = {f"{c['CategoryID']} — {c['CategoryName']}":
                                 c["CategoryID"] for c in cats}
        self.cb_category.configure(values=["(all categories)"]
                                   + list(self._category_lookup))
        self.cb_category.set("(all categories)")

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        try:
            d_from = parse_date(self.e_from.get())
            d_to   = parse_date(self.e_to.get())
        except ValueError as exc:
            messagebox.showwarning("Filter", str(exc))
            return
        acc_label = self.cb_account.get()
        cat_label = self.cb_category.get()
        ttype = self.cb_type.get()
        rows = transactions.list_for_user(
            self.user_id,
            date_from=d_from, date_to=d_to,
            account_id=self._account_lookup.get(acc_label),
            category_id=self._category_lookup.get(cat_label),
            ttype=None if ttype == "All" else ttype,
            limit=1000,
        )
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=str(r["TransactionID"]), values=(
                r["TransactionID"], fmt_date(r["TransactionDate"]),
                r["TransactionType"], fmt_money(r["Amount"]),
                r["AccountName"], r["CategoryName"],
                r["Description"] or "",
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ------------------------------------------------------------------
    def _open_create_dialog(self) -> None:
        TransactionDialog(self, on_save=self._after_save, user_id=self.user_id)

    def _edit(self) -> None:
        tid = self._selected_id()
        if tid is None:
            return
        TransactionDialog(self, on_save=self._after_save,
                          user_id=self.user_id,
                          txn=transactions.get(tid))

    def _delete(self) -> None:
        tid = self._selected_id()
        if tid is None:
            return
        if not messagebox.askyesno("Delete", "Delete this transaction?"):
            return
        transactions.delete(tid)
        self._refresh()

    def _after_save(self) -> None:
        self._populate_filter_combos()
        self._refresh()


class TransactionDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, user_id: int, txn: dict | None = None):
        super().__init__(parent)
        self.on_save = on_save
        self.user_id = user_id
        self.txn = txn
        self.title("Transaction")
        self.geometry("460x540")
        self.transient(parent)
        self.grab_set()
        self._accs = accounts.list_for_user(user_id, only_active=True)
        self._cats = categories.list_visible_to_user(user_id, only_active=True)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Account").pack(anchor="w", padx=18, pady=(18, 2))
        self._acc_lookup = {f"{a['AccountID']} — {a['AccountName']}": a["AccountID"]
                            for a in self._accs}
        self.cb_acc = ctk.CTkComboBox(self, width=420,
                                      values=list(self._acc_lookup) or ["(none)"])
        self.cb_acc.pack(padx=18)

        ctk.CTkLabel(self, text="Category").pack(anchor="w", padx=18, pady=(12, 2))
        self._cat_lookup = {f"{c['CategoryID']} — {c['CategoryName']} ({c['CategoryType']})":
                            c["CategoryID"] for c in self._cats}
        self.cb_cat = ctk.CTkComboBox(self, width=420,
                                      values=list(self._cat_lookup) or ["(none)"])
        self.cb_cat.pack(padx=18)

        ctk.CTkLabel(self, text="Type").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_type = ctk.CTkComboBox(self, width=420,
                                       values=["Expense", "Income"])
        self.cb_type.pack(padx=18)

        ctk.CTkLabel(self, text="Amount").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_amount = ctk.CTkEntry(self, width=420)
        self.e_amount.pack(padx=18)

        ctk.CTkLabel(self, text="Date (dd.mm.yyyy)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_date = ctk.CTkEntry(self, width=420)
        self.e_date.insert(0, date.today().strftime("%d.%m.%Y"))
        self.e_date.pack(padx=18)

        ctk.CTkLabel(self, text="Description").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_desc = ctk.CTkEntry(self, width=420)
        self.e_desc.pack(padx=18)

        if self.txn:
            for k, v in self._acc_lookup.items():
                if v == self.txn["AccountID"]:
                    self.cb_acc.set(k); break
            for k, v in self._cat_lookup.items():
                if v == self.txn["CategoryID"]:
                    self.cb_cat.set(k); break
            self.cb_type.set(self.txn["TransactionType"])
            self.e_amount.delete(0, "end")
            self.e_amount.insert(0, str(self.txn["Amount"]).replace(".", ","))
            self.e_date.delete(0, "end")
            self.e_date.insert(0, fmt_date(self.txn["TransactionDate"]))
            self.e_desc.insert(0, self.txn["Description"] or "")

        ctk.CTkButton(self, text="Save", command=self._save
                      ).pack(pady=20, padx=18, fill="x")

    def _save(self) -> None:
        try:
            acc_id = self._acc_lookup[self.cb_acc.get()]
            cat_id = self._cat_lookup[self.cb_cat.get()]
            ttype  = self.cb_type.get()
            amount = parse_decimal(self.e_amount.get())
            d      = parse_date(self.e_date.get()) or date.today()
            desc   = self.e_desc.get().strip() or None
            if self.txn:
                transactions.update(self.txn["TransactionID"],
                                    account_id=acc_id, category_id=cat_id,
                                    amount=amount, ttype=ttype,
                                    txn_date=d, description=desc, notes=None)
            else:
                transactions.create(user_id=self.user_id, account_id=acc_id,
                                    category_id=cat_id, amount=amount,
                                    ttype=ttype, txn_date=d, description=desc)
        except Exception as exc:                                # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
