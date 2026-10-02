"""
gui/alerts_view.py — view, mark-as-read, and delete alerts.
"""
from __future__ import annotations
from tkinter import messagebox, ttk
import customtkinter as ctk

from gui import fmt_date
from models import alerts
from services.alert_engine import run_all_checks


class AlertsView(ctk.CTkFrame):
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
        ctk.CTkLabel(header, text="Alerts",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="Run checks now",
                      command=self._run_checks).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Mark all read",
                      command=self._mark_all).pack(side="right", padx=4)

        cols = ("AlertID", "Type", "Title", "Message", "Read", "Created")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                 selectmode="browse")
        for c, w in zip(cols, (70, 130, 200, 460, 60, 130)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 16))
        ctk.CTkButton(btns, text="Mark read", command=self._mark_one
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete", fg_color="#a14040",
                      hover_color="#7c2828", command=self._delete
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh
                      ).pack(side="right")

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for a in alerts.list_for_user(self.user_id):
            self.tree.insert("", "end", iid=str(a["AlertID"]), values=(
                a["AlertID"], a["AlertType"], a["Title"], a["Message"],
                "Yes" if a["IsRead"] else "No",
                fmt_date(a["CreatedAt"]),
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _mark_one(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        alerts.mark_read(aid)
        self._refresh()

    def _mark_all(self) -> None:
        alerts.mark_all_read(self.user_id)
        self._refresh()

    def _delete(self) -> None:
        aid = self._selected_id()
        if aid is None:
            return
        if not messagebox.askyesno("Delete", "Delete this alert?"):
            return
        alerts.delete(aid)
        self._refresh()

    def _run_checks(self) -> None:
        try:
            stats = run_all_checks(self.user_id)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("Run checks", str(exc))
            return
        messagebox.showinfo("Run checks",
                            f"New budget alerts: {stats['budget_alerts']}\n"
                            f"New payment alerts: {stats['payment_alerts']}")
        self._refresh()
