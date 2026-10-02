"""
gui/categories_view.py — Category management.

Users can create / edit / soft-delete their own custom categories. System
defaults (UserID IS NULL) are visible but read-only on this screen — the
Admin dashboard is the only place to edit them.
"""
from __future__ import annotations
from tkinter import messagebox, ttk
import customtkinter as ctk

from models import categories


class CategoriesView(ctk.CTkFrame):
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
        ctk.CTkLabel(header, text="Categories",
                     font=ctk.CTkFont(size=20, weight="bold")
                     ).pack(side="left")
        ctk.CTkButton(header, text="+ New custom category",
                      command=self._open_create_dialog).pack(side="right")

        cols = ("CategoryID", "CategoryName", "CategoryType", "Parent",
                "Owner", "IsActive")
        wrap = ctk.CTkFrame(self)
        wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (70, 220, 100, 220, 80, 70)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 16))
        ctk.CTkButton(btns, text="Edit (own only)", command=self._edit
                      ).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Deactivate (own only)", fg_color="#a14040",
                      hover_color="#7c2828",
                      command=self._delete).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Refresh", command=self._refresh
                      ).pack(side="right")

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        all_cats = categories.list_visible_to_user(self.user_id, only_active=False)
        cat_map = {c["CategoryID"]: c["CategoryName"] for c in all_cats}
        for c in all_cats:
            parent_name = cat_map.get(c["ParentCategoryID"], "")
            owner = "User" if c["UserID"] else "System"
            self.tree.insert("", "end", iid=str(c["CategoryID"]), values=(
                c["CategoryID"], c["CategoryName"], c["CategoryType"],
                parent_name, owner, "Yes" if c["IsActive"] else "No",
            ))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _open_create_dialog(self) -> None:
        CategoryDialog(self, on_save=self._refresh, user_id=self.user_id)

    def _edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cat = categories.get(cid)
        if cat is None or cat["UserID"] is None:
            messagebox.showinfo("Edit",
                                "System categories are read-only here. "
                                "Use the Admin dashboard.")
            return
        CategoryDialog(self, on_save=self._refresh,
                       user_id=self.user_id, category=cat)

    def _delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        cat = categories.get(cid)
        if cat is None or cat["UserID"] is None:
            messagebox.showinfo("Delete",
                                "Cannot deactivate a system category here.")
            return
        if not messagebox.askyesno("Deactivate", "Soft-delete this category?"):
            return
        categories.soft_delete(cid)
        self._refresh()


class CategoryDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, on_save, user_id: int,
                 category: dict | None = None):
        super().__init__(parent)
        self.user_id = user_id
        self.category = category
        self.on_save = on_save
        self.title("Category")
        self.geometry("440x440")
        self.transient(parent)
        self.grab_set()
        self._all = categories.list_visible_to_user(user_id, only_active=True)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self, text="Name").pack(anchor="w", padx=18, pady=(18, 2))
        self.e_name = ctk.CTkEntry(self, width=400)
        self.e_name.pack(padx=18)

        ctk.CTkLabel(self, text="Type").pack(anchor="w", padx=18, pady=(12, 2))
        self.cb_type = ctk.CTkComboBox(self, width=400,
                                       values=["Income", "Expense"])
        self.cb_type.pack(padx=18)

        ctk.CTkLabel(self, text="Parent (optional)").pack(anchor="w", padx=18, pady=(12, 2))
        parent_options = ["(none)"] + [f"{c['CategoryID']} — {c['CategoryName']}"
                                       for c in self._all
                                       if not self.category
                                       or c["CategoryID"] != self.category["CategoryID"]]
        self.cb_parent = ctk.CTkComboBox(self, width=400, values=parent_options)
        self.cb_parent.set(parent_options[0])
        self.cb_parent.pack(padx=18)

        ctk.CTkLabel(self, text="Description").pack(anchor="w", padx=18, pady=(12, 2))
        self.e_desc = ctk.CTkEntry(self, width=400)
        self.e_desc.pack(padx=18)

        if self.category:
            self.e_name.insert(0, self.category["CategoryName"])
            self.cb_type.set(self.category["CategoryType"])
            self.e_desc.insert(0, self.category["Description"] or "")
            if self.category["ParentCategoryID"]:
                for opt in parent_options:
                    if opt.startswith(f"{self.category['ParentCategoryID']} —"):
                        self.cb_parent.set(opt)
                        break

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
        ctype = self.cb_type.get().strip()
        if not name or ctype not in ("Income", "Expense"):
            messagebox.showwarning("Save", "Name and type are required.")
            return
        parent_id = self._parse_parent()
        try:
            if self.category:
                categories.update(self.category["CategoryID"], name=name,
                                  ctype=ctype, parent_id=parent_id,
                                  description=self.e_desc.get().strip() or None,
                                  icon=None)
            else:
                categories.create(name=name, ctype=ctype, user_id=self.user_id,
                                  parent_id=parent_id,
                                  description=self.e_desc.get().strip() or None)
        except Exception as exc:                                # noqa: BLE001
            messagebox.showerror("Save error", str(exc))
            return
        self.on_save()
        self.destroy()
