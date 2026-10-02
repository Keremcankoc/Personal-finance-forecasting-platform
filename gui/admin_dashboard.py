"""
gui/admin_dashboard.py
======================
Admin shell. Three tabs:
  • Platform stats  — aggregate counts only (no per-user financials)
  • Users           — list / activate / deactivate
  • System categories — CRUD on the recursive tree (UserID IS NULL)

Per Phase 1 §1.2: admins must NEVER see individual users' financial data.
Every query on this screen goes through models.users / models.categories
helpers and only ever reads the system-default subset.
"""
from __future__ import annotations
from tkinter import messagebox, ttk
import customtkinter as ctk

from config import APP_NAME
from gui import fmt_date
from models import users, categories


class AdminDashboard(ctk.CTk):
    def __init__(self, user: dict):
        super().__init__()
        self.user = user
        self.title(f"{APP_NAME} — Admin ({user['Username']})")
        self.geometry("1150x720")
        self.minsize(1000, 640)
        self._build()

    def _build(self) -> None:
        bar = ctk.CTkFrame(self, height=56, corner_radius=0)
        bar.pack(fill="x")
        ctk.CTkLabel(bar, text="Admin Dashboard",
                     font=ctk.CTkFont(size=18, weight="bold")
                     ).pack(side="left", padx=18, pady=12)
        ctk.CTkButton(bar, text="Sign out", fg_color="#a14040",
                      hover_color="#7c2828",
                      command=self.destroy).pack(side="right", padx=18, pady=12)

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=16, pady=12)
        tabs.add("Platform Stats")
        tabs.add("Users")
        tabs.add("System Categories")

        self._build_stats_tab(tabs.tab("Platform Stats"))
        self._build_users_tab(tabs.tab("Users"))
        self._build_categories_tab(tabs.tab("System Categories"))

    # ------------------------------------------------------------------
    # Platform stats
    # ------------------------------------------------------------------
    def _build_stats_tab(self, parent) -> None:
        ctk.CTkButton(parent, text="Refresh stats",
                      command=lambda: self._refresh_stats(parent)
                      ).pack(anchor="w", padx=12, pady=10)
        self._stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._stats_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._refresh_stats(parent)

    def _refresh_stats(self, parent) -> None:
        for w in self._stats_frame.winfo_children():
            w.destroy()
        stats = users.platform_stats()
        rows = [
            ("Total users",          stats.get("TotalUsers", 0)),
            ("Active users",         stats.get("ActiveUsers", 0)),
            ("Admins",               stats.get("Admins", 0)),
            ("Total accounts",       stats.get("TotalAccounts", 0)),
            ("Total transactions",   stats.get("TotalTransactions", 0)),
            ("System categories",    stats.get("SystemCategories", 0)),
            ("User categories",      stats.get("UserCategories", 0)),
            ("Active recurring pmts",stats.get("ActiveRecurring", 0)),
            ("Total budgets",        stats.get("TotalBudgets", 0)),
        ]
        # 3-column grid of KPI cards
        grid = ctk.CTkFrame(self._stats_frame, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="kpi")
        for idx, (label, value) in enumerate(rows):
            card = ctk.CTkFrame(grid, corner_radius=10)
            card.grid(row=idx // 3, column=idx % 3, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(card, text=label, text_color="gray",
                         font=ctk.CTkFont(size=12)
                         ).pack(anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(card, text=str(value),
                         font=ctk.CTkFont(size=22, weight="bold")
                         ).pack(anchor="w", padx=14, pady=(0, 14))
        ctk.CTkLabel(self._stats_frame,
                     text="Note: per privacy policy, individual users' "
                          "financial data is never shown on the admin screen.",
                     text_color="gray", wraplength=900
                     ).pack(anchor="w", padx=8, pady=(8, 0))

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    def _build_users_tab(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(bar, text="Refresh",
                      command=self._refresh_users).pack(side="left")
        ctk.CTkButton(bar, text="Activate",
                      command=lambda: self._set_active(True)).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Deactivate", fg_color="#a14040",
                      hover_color="#7c2828",
                      command=lambda: self._set_active(False)
                      ).pack(side="left", padx=6)

        wrap = ctk.CTkFrame(parent)
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        cols = ("UserID", "Username", "Email", "Role", "IsActive",
                "FirstName", "LastName", "Currency", "CreatedAt", "LastLoginAt")
        self.users_tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                       selectmode="browse")
        for c, w in zip(cols, (60, 140, 200, 80, 70, 110, 110, 80, 130, 130)):
            self.users_tree.heading(c, text=c)
            self.users_tree.column(c, width=w, anchor="w")
        self.users_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._refresh_users()

    def _refresh_users(self) -> None:
        self.users_tree.delete(*self.users_tree.get_children())
        for u in users.list_all():
            self.users_tree.insert("", "end", iid=str(u["UserID"]), values=(
                u["UserID"], u["Username"], u["Email"], u["Role"],
                "Yes" if u["IsActive"] else "No",
                u["FirstName"], u["LastName"], u["PreferredCurrency"],
                fmt_date(u["CreatedAt"]),
                fmt_date(u["LastLoginAt"]) if u["LastLoginAt"] else "",
            ))

    def _set_active(self, active: bool) -> None:
        sel = self.users_tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        if uid == int(self.user["UserID"]) and not active:
            messagebox.showwarning("User", "You cannot deactivate yourself.")
            return
        users.set_active(uid, active)
        self._refresh_users()

    # ------------------------------------------------------------------
    # System categories
    # ------------------------------------------------------------------
    def _build_categories_tab(self, parent) -> None:
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(bar, text="+ New system category",
                      command=self._new_cat).pack(side="left")
        ctk.CTkButton(bar, text="Edit", command=self._edit_cat
                      ).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Deactivate", fg_color="#a14040",
                      hover_color="#7c2828",
                      command=self._delete_cat).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Refresh",
                      command=self._refresh_cats).pack(side="right")

        wrap = ctk.CTkFrame(parent)
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        cols = ("CategoryID", "CategoryName", "CategoryType",
                "Parent", "IsActive", "Description")
        self.cats_tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                      selectmode="browse")
        for c, w in zip(cols, (80, 220, 100, 220, 70, 320)):
            self.cats_tree.heading(c, text=c)
            self.cats_tree.column(c, width=w, anchor="w")
        self.cats_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.cats_tree.yview)
        self.cats_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._refresh_cats()

    def _refresh_cats(self) -> None:
        self.cats_tree.delete(*self.cats_tree.get_children())
        all_sys = categories.list_system_only(only_active=False)
        cat_map = {c["CategoryID"]: c["CategoryName"] for c in all_sys}
        for c in all_sys:
            self.cats_tree.insert("", "end", iid=str(c["CategoryID"]), values=(
                c["CategoryID"], c["CategoryName"], c["CategoryType"],
                cat_map.get(c["ParentCategoryID"], ""),
                "Yes" if c["IsActive"] else "No",
                c["Description"] or "",
            ))

    def _selected_cat(self) -> int | None:
        sel = self.cats_tree.selection()
        return int(sel[0]) if sel else None

    def _new_cat(self) -> None:
        SystemCategoryDialog(self, on_save=self._refresh_cats)

    def _edit_cat(self) -> None:
        cid = self._selected_cat()
        if cid is None:
            return
        SystemCategoryDialog(self, on_save=self._refresh_cats,
                             category=categories.get(cid))

    def _delete_cat(self) -> None:
        cid = self._selected_cat()
        if cid is None:
            return
        if not messagebox.askyesno("Deactivate",
                                   "Deactivate this system category?"):
            return
        categories.soft_delete(cid)
        self._refresh_cats()


class SystemCategoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, category: dict | None = None):
        super().__init__(parent)
        self.on_save = on_save
        self.category = category
        self.title("System category")
        self.geometry("440x420")
        self.transient(parent)
        self.grab_set()
        self._all = categories.list_system_only(only_active=True)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Name").pack(anchor="w", padx=18, pady=(18, 2))
        self.e_name = ctk.CTkEntry(self, width=400)
        self.e_name.pack(padx=18)

        ctk.CTkLabel(self, text="Type").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_type = ctk.CTkComboBox(self, width=400,
                                       values=["Income", "Expense"])
        self.cb_type.pack(padx=18)

        ctk.CTkLabel(self, text="Parent (optional)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        opts = ["(none)"] + [
            f"{c['CategoryID']} — {c['CategoryName']}"
            for c in self._all
            if not self.category or c["CategoryID"] != self.category["CategoryID"]
        ]
        self.cb_parent = ctk.CTkComboBox(self, width=400, values=opts)
        self.cb_parent.set(opts[0])
        self.cb_parent.pack(padx=18)

        ctk.CTkLabel(self, text="Description").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_desc = ctk.CTkEntry(self, width=400)
        self.e_desc.pack(padx=18)

        if self.category:
            self.e_name.insert(0, self.category["CategoryName"])
            self.cb_type.set(self.category["CategoryType"])
            self.e_desc.insert(0, self.category["Description"] or "")
            if self.category["ParentCategoryID"]:
                for opt in opts:
                    if opt.startswith(f"{self.category['ParentCategoryID']} —"):
                        self.cb_parent.set(opt); break

        ctk.CTkButton(self, text="Save", command=self._save
                      ).pack(pady=20, padx=18, fill="x")

    def _parse_parent(self) -> int | None:
        text = self.cb_parent.get()
        if text == "(none)":
            return None
        try:
            return int(text.split(" — ", 1)[0])
        except (ValueError, IndexError):
            return None

    def _save(self) -> None:
        name = self.e_name.get().strip()
        ctype = self.cb_type.get()
        if not name or ctype not in ("Income", "Expense"):
            messagebox.showwarning("Save", "Name and type are required.")
            return
        try:
            if self.category:
                categories.update(self.category["CategoryID"], name=name,
                                  ctype=ctype, parent_id=self._parse_parent(),
                                  description=self.e_desc.get().strip() or None,
                                  icon=None)
            else:
                # System category -> user_id=None
                categories.create(name=name, ctype=ctype, user_id=None,
                                  parent_id=self._parse_parent(),
                                  description=self.e_desc.get().strip() or None)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
