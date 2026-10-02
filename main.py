"""
main.py
=======
Application entry point. Boots customtkinter, runs a database health
check, opens the LoginWindow, and on successful login routes the user
to the User or Admin dashboard depending on Role. Loops back to the
login window on logout.
"""
from __future__ import annotations
import sys
from tkinter import messagebox

import customtkinter as ctk

from config import APP_NAME, APP_VERSION, CTK_APPEARANCE_MODE, CTK_COLOR_THEME
from db import healthcheck
from gui.login_window import LoginWindow
from gui.user_dashboard import UserDashboard
from gui.admin_dashboard import AdminDashboard
from services.alert_engine import run_all_checks


def _on_login_success(user: dict) -> None:
    """Open the right dashboard. After it closes, loop back to login."""
    role = user.get("Role")

    # Auto-run the alert engine for regular users on every login.
    if role == "User":
        try:
            run_all_checks(int(user["UserID"]))
        except Exception as exc:                                # noqa: BLE001
            print(f"[alert_engine] warning: {exc}", file=sys.stderr)

    if role == "Admin":
        dash = AdminDashboard(user)
    else:
        dash = UserDashboard(user)

    dash.mainloop()
    # When the dashboard window is closed, return to the login screen
    _launch_login()


def _launch_login() -> None:
    win = LoginWindow(on_success=_on_login_success)
    win.mainloop()


def main() -> None:
    ctk.set_appearance_mode(CTK_APPEARANCE_MODE)
    ctk.set_default_color_theme(CTK_COLOR_THEME)

    ok, msg = healthcheck()
    if not ok:
        # Show a Tk error dialog AND print to stderr so users see it whether
        # they launched from a terminal or a file manager
        print(f"[fatal] Database connection failed: {msg}", file=sys.stderr)
        try:
            tmp = ctk.CTk(); tmp.withdraw()
            messagebox.showerror(
                f"{APP_NAME} v{APP_VERSION}",
                "Could not connect to SQL Server.\n\n"
                f"{msg}\n\n"
                "Edit config.py with your server / database, then ensure the "
                "schema and seed data have been loaded (see how_to_run.txt).")
            tmp.destroy()
        except Exception:                                       # noqa: BLE001
            pass
        sys.exit(1)

    print(f"[startup] {APP_NAME} v{APP_VERSION} — connected to: {msg}")
    _launch_login()


if __name__ == "__main__":
    main()
