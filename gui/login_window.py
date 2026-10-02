"""
gui/login_window.py — login + register window.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from config import APP_NAME, APP_VERSION
import auth


class LoginWindow(ctk.CTk):
    """Top-level login form. Calls `on_success(user_dict)` when login succeeds."""

    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.title(f"{APP_NAME} — Login")
        self.geometry("440x560")
        self.minsize(440, 560)
        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        wrap = ctk.CTkFrame(self, corner_radius=12)
        wrap.pack(expand=True, fill="both", padx=24, pady=24)

        ctk.CTkLabel(wrap, text=APP_NAME,
                     font=ctk.CTkFont(size=18, weight="bold"),
                     wraplength=380, justify="center").pack(pady=(20, 6))
        ctk.CTkLabel(wrap, text=f"v{APP_VERSION}",
                     text_color="gray").pack(pady=(0, 18))

        self.tabs = ctk.CTkTabview(wrap, height=360)
        self.tabs.pack(expand=True, fill="both", padx=10, pady=10)
        self.tabs.add("Login")
        self.tabs.add("Register")
        self._build_login_tab(self.tabs.tab("Login"))
        self._build_register_tab(self.tabs.tab("Register"))

    # ------------------------------------------------------------------
    def _build_login_tab(self, parent) -> None:
        ctk.CTkLabel(parent, text="Username or email").pack(anchor="w", pady=(20, 4))
        self.login_user = ctk.CTkEntry(parent, width=320)
        self.login_user.pack()

        ctk.CTkLabel(parent, text="Password").pack(anchor="w", pady=(14, 4))
        self.login_pass = ctk.CTkEntry(parent, width=320, show="•")
        self.login_pass.pack()
        self.login_pass.bind("<Return>", lambda e: self._do_login())

        ctk.CTkButton(parent, text="Sign In", width=320,
                      command=self._do_login).pack(pady=(24, 8))
        ctk.CTkLabel(parent, text="Demo: admin / Admin123!  •  demo / Demo123!",
                     text_color="gray", font=ctk.CTkFont(size=11)).pack()

    def _build_register_tab(self, parent) -> None:
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(expand=True, fill="both", padx=8, pady=8)

        self.reg_first   = self._row(grid, "First name", 0)
        self.reg_last    = self._row(grid, "Last name",  1)
        self.reg_user    = self._row(grid, "Username",   2)
        self.reg_email   = self._row(grid, "Email",      3)
        self.reg_pass    = self._row(grid, "Password",   4, show="•")
        self.reg_pass2   = self._row(grid, "Confirm",    5, show="•")

        ctk.CTkButton(grid, text="Create Account",
                      command=self._do_register).grid(
            row=6, column=0, columnspan=2, pady=18, padx=8, sticky="ew")
        grid.grid_columnconfigure(1, weight=1)

    def _row(self, parent, label: str, row: int, *, show: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label).grid(
            row=row, column=0, sticky="e", padx=8, pady=6)
        e = ctk.CTkEntry(parent, show=show, width=240)
        e.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        return e

    # ------------------------------------------------------------------
    def _do_login(self) -> None:
        u = self.login_user.get().strip()
        p = self.login_pass.get()
        if not u or not p:
            messagebox.showwarning("Login", "Please enter username and password.")
            return
        try:
            user = auth.login(u, p)
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Login error", str(exc))
            return
        if not user:
            messagebox.showerror("Login failed",
                                 "Invalid credentials or account disabled.")
            return
        self.destroy()
        self.on_success(user)

    def _do_register(self) -> None:
        if self.reg_pass.get() != self.reg_pass2.get():
            messagebox.showwarning("Register", "Passwords do not match.")
            return
        try:
            new_id = auth.register_user(
                username=self.reg_user.get().strip(),
                email=self.reg_email.get().strip(),
                password=self.reg_pass.get(),
                first_name=self.reg_first.get().strip(),
                last_name=self.reg_last.get().strip(),
                role="User",
            )
        except ValueError as exc:
            messagebox.showwarning("Register", str(exc))
            return
        except Exception as exc:                       # noqa: BLE001
            messagebox.showerror("Register error", str(exc))
            return

        messagebox.showinfo("Register",
                            f"Account created (UserID={new_id}). You can now sign in.")
        self.tabs.set("Login")
        self.login_user.delete(0, tk.END)
        self.login_user.insert(0, self.reg_user.get().strip())
