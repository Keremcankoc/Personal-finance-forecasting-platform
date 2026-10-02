"""
gui/recurring_view.py — Recurring payments CRUD.
"""
from __future__ import annotations
from datetime import date
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui import fmt_money, fmt_date, parse_date, parse_decimal
from models import accounts, categories, recurring


class RecurringView(ctk.CTkFrame):
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
        ctk.CTkLabel(header, text="Recurring Payments",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="+ New recurring",
                      command=self._open_create_dialog).pack(side="right")
        ctk.CTkButton(header, text="Process due",
                      command=self._process_due
                      ).pack(side="right", padx=8)

        cols = ("RecurringPaymentID", "Description", "Type", "Amount",
                "Frequency", "Next charge", "Account", "Category", "Active")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w in zip(cols, (110, 220, 80, 120, 90, 110, 160, 160, 70)):
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
        ctk.CTkButton(btns, text="Deactivate", fg_color="#a14040",
                      hover_color="#7c2828", command=self._delete
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh
                      ).pack(side="right")

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in recurring.list_for_user(self.user_id, only_active=False):
            self.tree.insert("", "end", iid=str(r["RecurringPaymentID"]),
                             values=(
                r["RecurringPaymentID"], r["Description"], r["TransactionType"],
                fmt_money(r["Amount"]), r["Frequency"],
                fmt_date(r["NextChargeDate"]),
                r["AccountName"], r["CategoryName"],
                "Yes" if r["IsActive"] else "No",
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _open_create_dialog(self) -> None:
        RecurringDialog(self, on_save=self._refresh, user_id=self.user_id)

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        RecurringDialog(self, on_save=self._refresh, user_id=self.user_id,
                        rp=recurring.get(rid))

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno("Deactivate",
                                   "Deactivate this recurring payment?"):
            return
        recurring.soft_delete(rid)
        self._refresh()

    def _process_due(self) -> None:
        n = recurring.process_due_charges(self.user_id)
        messagebox.showinfo("Process due",
                            f"Generated {n} transaction(s) from due recurring payments.")
        self._refresh()


class RecurringDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, user_id: int, rp: dict | None = None):
        super().__init__(parent)
        self.on_save = on_save
        self.user_id = user_id
        self.rp = rp
        self.title("Recurring payment")
        self.geometry("480x680")
        self.transient(parent)
        self.grab_set()
        self._accs = accounts.list_for_user(user_id, only_active=True)
        self._cats = categories.list_visible_to_user(user_id, only_active=True)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Description"
                     ).pack(anchor="w", padx=18, pady=(18, 2))
        self.e_desc = ctk.CTkEntry(self, width=440)
        self.e_desc.pack(padx=18)

        ctk.CTkLabel(self, text="Account").pack(anchor="w", padx=18, pady=(12, 2))
        self._acc_lookup = {f"{a['AccountID']} — {a['AccountName']}":
                            a["AccountID"] for a in self._accs}
        self.cb_acc = ctk.CTkComboBox(self, width=440,
                                      values=list(self._acc_lookup) or ["(none)"])
        self.cb_acc.pack(padx=18)

        ctk.CTkLabel(self, text="Category").pack(anchor="w", padx=18, pady=(12, 2))
        self._cat_lookup = {f"{c['CategoryID']} — {c['CategoryName']} ({c['CategoryType']})":
                            c["CategoryID"] for c in self._cats}
        self.cb_cat = ctk.CTkComboBox(self, width=440,
                                      values=list(self._cat_lookup) or ["(none)"])
        self.cb_cat.pack(padx=18)

        ctk.CTkLabel(self, text="Type").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_type = ctk.CTkComboBox(self, width=440,
                                       values=["Expense", "Income"])
        self.cb_type.pack(padx=18)

        ctk.CTkLabel(self, text="Amount").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_amt = ctk.CTkEntry(self, width=440)
        self.e_amt.pack(padx=18)

        ctk.CTkLabel(self, text="Frequency").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_freq = ctk.CTkComboBox(self, width=440,
                                       values=["Daily", "Weekly", "Biweekly",
                                               "Monthly", "Quarterly", "Yearly"])
        self.cb_freq.set("Monthly")
        self.cb_freq.pack(padx=18)

        ctk.CTkLabel(self, text="Start date (dd.mm.yyyy)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_start = ctk.CTkEntry(self, width=440)
        self.e_start.insert(0, date.today().strftime("%d.%m.%Y"))
        self.e_start.pack(padx=18)

        ctk.CTkLabel(self, text="Next charge date (dd.mm.yyyy)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_next = ctk.CTkEntry(self, width=440)
        self.e_next.insert(0, date.today().strftime("%d.%m.%Y"))
        self.e_next.pack(padx=18)

        ctk.CTkLabel(self, text="End date (optional)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_end = ctk.CTkEntry(self, width=440)
        self.e_end.pack(padx=18)

        if self.rp:
            self.e_desc.insert(0, self.rp["Description"])
            for k, v in self._acc_lookup.items():
                if v == self.rp["AccountID"]:
                    self.cb_acc.set(k); break
            for k, v in self._cat_lookup.items():
                if v == self.rp["CategoryID"]:
                    self.cb_cat.set(k); break
            self.cb_type.set(self.rp["TransactionType"])
            self.e_amt.delete(0, "end")
            self.e_amt.insert(0, str(self.rp["Amount"]).replace(".", ","))
            self.cb_freq.set(self.rp["Frequency"])
            self.e_start.delete(0, "end")
            self.e_start.insert(0, fmt_date(self.rp["StartDate"]))
            self.e_next.delete(0, "end")
            self.e_next.insert(0, fmt_date(self.rp["NextChargeDate"]))
            if self.rp["EndDate"]:
                self.e_end.insert(0, fmt_date(self.rp["EndDate"]))

        ctk.CTkButton(self, text="Save", command=self._save
                      ).pack(pady=18, padx=18, fill="x")

    def _save(self) -> None:
        try:
            desc = self.e_desc.get().strip()
            if not desc:
                raise ValueError("Description is required.")
            acc_id = self._acc_lookup[self.cb_acc.get()]
            cat_id = self._cat_lookup[self.cb_cat.get()]
            ttype = self.cb_type.get()
            amount = parse_decimal(self.e_amt.get())
            freq = self.cb_freq.get()
            start = parse_date(self.e_start.get())
            nxt = parse_date(self.e_next.get())
            end = parse_date(self.e_end.get())
            if start is None:
                raise ValueError("Start date is required.")
            if nxt is None:
                nxt = start
            if end is not None and end < start:
                raise ValueError("End date must be on/after start date.")
            if self.rp:
                recurring.update(self.rp["RecurringPaymentID"],
                                 account_id=acc_id, category_id=cat_id,
                                 amount=amount, ttype=ttype, frequency=freq,
                                 start_date=start, end_date=end,
                                 next_charge_date=nxt, description=desc)
            else:
                recurring.create(user_id=self.user_id, account_id=acc_id,
                                 category_id=cat_id, amount=amount,
                                 ttype=ttype, frequency=freq,
                                 start_date=start, end_date=end,
                                 next_charge_date=nxt, description=desc)
        except Exception as exc:                                # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
