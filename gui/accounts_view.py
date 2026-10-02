"""
gui/accounts_view.py — Accounts CRUD.
"""
from __future__ import annotations
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui import fmt_money, fmt_date, parse_decimal
from models import accounts


class AccountsView(ctk.CTkFrame):
    def __init__(self, parent, user_id: int):
        super().__init__(parent, fg_color="transparent")
        self.user_id = user_id
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self._refresh()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))
        ctk.CTkLabel(header, text="Accounts",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="+ New account",
                      command=self._open_create_dialog).pack(side="right")

        cols = ("AccountID", "AccountName", "AccountType",
                "Balance", "Currency", "IsActive", "CreatedAt")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (60, 220, 120, 140, 80, 80, 130)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 16))
        ctk.CTkButton(btns, text="Edit",   command=self._edit).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Deactivate", fg_color="#a14040",
                      hover_color="#7c2828", command=self._delete).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh).pack(side="right")

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for a in accounts.list_for_user(self.user_id, only_active=False):
            self.tree.insert("", "end", iid=str(a["AccountID"]), values=(
                a["AccountID"], a["AccountName"], a["AccountType"],
                fmt_money(a["Balance"]), a["Currency"],
                "Yes" if a["IsActive"] else "No",
                fmt_date(a["CreatedAt"]),
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ------------------------------------------------------------------
    def _open_create_dialog(self) -> None:
        AccountDialog(self, on_save=self._refresh, user_id=self.user_id)

    def _edit(self) -> None:
        aid = self._selected_id()
        if aid is None:
            messagebox.showinfo("Edit", "Pick an account from the list.")
            return
        AccountDialog(self, on_save=self._refresh, user_id=self.user_id,
                      account=accounts.get(aid))

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Deactivate",
                                   "Soft-delete this account? Existing transactions are kept."):
            return
        accounts.soft_delete(aid)
        self._refresh()


class AccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, user_id: int, account: dict | None = None):
        super().__init__(parent)
        self.user_id = user_id
        self.account = account
        self.on_save = on_save
        self.title("Account")
        self.geometry("420x360")
        self.transient(parent)
        self.grab_set()
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Account name").pack(anchor="w", padx=18, pady=(18, 2))
        self.e_name = ctk.CTkEntry(self, width=380)
        self.e_name.pack(padx=18)

        ctk.CTkLabel(self, text="Type").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_type = ctk.CTkComboBox(
            self, width=380,
            values=["Cash", "Bank", "CreditCard", "Savings", "Investment"])
        self.cb_type.pack(padx=18)

        ctk.CTkLabel(self, text="Currency").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_currency = ctk.CTkEntry(self, width=380)
        self.e_currency.insert(0, "TRY")
        self.e_currency.pack(padx=18)

        ctk.CTkLabel(self, text="Initial balance (only on create)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_balance = ctk.CTkEntry(self, width=380)
        self.e_balance.insert(0, "0,00")
        self.e_balance.pack(padx=18)

        if self.account:
            self.e_name.insert(0, self.account["AccountName"])
            self.cb_type.set(self.account["AccountType"])
            self.e_currency.delete(0, "end")
            self.e_currency.insert(0, self.account["Currency"])
            self.e_balance.configure(state="disabled")

        ctk.CTkButton(self, text="Save", command=self._save
                      ).pack(pady=20, padx=18, fill="x")

    def _save(self) -> None:
        name = self.e_name.get().strip()
        atype = self.cb_type.get().strip()
        currency = self.e_currency.get().strip().upper() or "TRY"
        if not name:
            messagebox.showwarning("Save", "Account name is required.")
            return
        try:
            if self.account:
                accounts.update(self.account["AccountID"],
                                name=name, account_type=atype, currency=currency)
            else:
                bal = parse_decimal(self.e_balance.get())
                accounts.create(user_id=self.user_id, name=name,
                                account_type=atype, initial_balance=bal,
                                currency=currency)
        except Exception as exc:                                # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
