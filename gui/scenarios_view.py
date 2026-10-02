"""
gui/scenarios_view.py — What-if scenario simulator.

Two-pane layout:
  Left  — list of scenarios + buttons (new / delete).
  Right — selected scenario details: items list, item editor, simulate chart.
"""
from __future__ import annotations
from tkinter import messagebox, ttk
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui import fmt_money, parse_decimal
from models import categories, scenarios
from services.forecast_engine import simulate_scenario


class ScenariosView(ctk.CTkFrame):
    def __init__(self, parent, user_id: int):
        super().__init__(parent, fg_color="transparent")
        self.user_id = user_id
        self.selected_id: int | None = None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()
        self._refresh_list()

    # ------------------------------------------------------------------
    def _build_left(self) -> None:
        left = ctk.CTkFrame(self, width=320)
        left.grid(row=0, column=0, sticky="nsw", padx=(16, 8), pady=16)
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Scenarios",
                     font=ctk.CTkFont(size=18, weight="bold")
                     ).pack(anchor="w", padx=12, pady=(10, 4))

        cols = ("ID", "Name", "Months")
        self.list_tree = ttk.Treeview(left, columns=cols, show="headings",
                                      selectmode="browse", height=20)
        for c, w in zip(cols, (50, 180, 70)):
            self.list_tree.heading(c, text=c)
            self.list_tree.column(c, width=w, anchor="w")
        self.list_tree.pack(fill="both", expand=True, padx=10)
        self.list_tree.bind("<<TreeviewSelect>>", self._on_select)

        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(btns, text="+ New",
                      command=self._new_scenario).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Delete", fg_color="#a14040",
                      hover_color="#7c2828",
                      command=self._delete_scenario).pack(side="left", padx=4)

    def _build_right(self) -> None:
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        self.lbl_title = ctk.CTkLabel(
            right, text="Pick or create a scenario.",
            font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_title.grid(row=0, column=0, sticky="w", padx=14, pady=(10, 6))

        # Item editor
        editor = ctk.CTkFrame(right)
        editor.grid(row=1, column=0, sticky="ew", padx=14, pady=4)
        editor.grid_columnconfigure(7, weight=1)
        ctk.CTkLabel(editor, text="Description").grid(row=0, column=0, padx=4, pady=8)
        self.e_desc = ctk.CTkEntry(editor, width=180)
        self.e_desc.grid(row=0, column=1, padx=4)
        ctk.CTkLabel(editor, text="Amount").grid(row=0, column=2, padx=4)
        self.e_amt = ctk.CTkEntry(editor, width=110)
        self.e_amt.grid(row=0, column=3, padx=4)

        ctk.CTkLabel(editor, text="Type").grid(row=0, column=4, padx=4)
        self.cb_type = ctk.CTkComboBox(editor, width=110,
                                       values=["Expense", "Income"])
        self.cb_type.grid(row=0, column=5, padx=4)

        ctk.CTkLabel(editor, text="Freq").grid(row=0, column=6, padx=4)
        self.cb_freq = ctk.CTkComboBox(
            editor, width=120,
            values=["Monthly", "OneTime", "Daily", "Weekly", "Yearly"])
        self.cb_freq.grid(row=0, column=7, padx=4)

        ctk.CTkButton(editor, text="+ Add item",
                      command=self._add_item
                      ).grid(row=0, column=8, padx=8)

        # Items + chart split
        split = ctk.CTkFrame(right, fg_color="transparent")
        split.grid(row=2, column=0, sticky="nsew", padx=10, pady=8)
        split.grid_columnconfigure(0, weight=1)
        split.grid_columnconfigure(1, weight=2)
        split.grid_rowconfigure(0, weight=1)

        # Items
        items_frame = ctk.CTkFrame(split)
        items_frame.grid(row=0, column=0, sticky="nsew", padx=4)
        cols = ("ID", "Description", "Amount", "Type", "Frequency")
        self.items_tree = ttk.Treeview(items_frame, columns=cols, show="headings",
                                       selectmode="browse")
        for c, w in zip(cols, (50, 180, 110, 80, 100)):
            self.items_tree.heading(c, text=c)
            self.items_tree.column(c, width=w, anchor="w")
        self.items_tree.pack(fill="both", expand=True, padx=4, pady=4)
        ctk.CTkButton(items_frame, text="Remove selected item",
                      fg_color="#a14040", hover_color="#7c2828",
                      command=self._remove_item).pack(pady=6)

        # Chart
        self.chart_frame = ctk.CTkFrame(split)
        self.chart_frame.grid(row=0, column=1, sticky="nsew", padx=4)
        self.chart_frame.grid_columnconfigure(0, weight=1)
        self.chart_frame.grid_rowconfigure(0, weight=1)

        ctk.CTkButton(right, text="Simulate scenario",
                      command=self._simulate
                      ).grid(row=3, column=0, sticky="ew", padx=14, pady=10)

    # ------------------------------------------------------------------
    def _refresh_list(self) -> None:
        self.list_tree.delete(*self.list_tree.get_children())
        for s in scenarios.list_for_user(self.user_id):
            self.list_tree.insert("", "end", iid=str(s["ScenarioID"]),
                                  values=(s["ScenarioID"], s["ScenarioName"],
                                          s["SimulationMonths"]))

    def _on_select(self, _evt) -> None:
        sel = self.list_tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        sc = scenarios.get(self.selected_id)
        if not sc:
            return
        self.lbl_title.configure(
            text=f"{sc['ScenarioName']} — horizon {sc['SimulationMonths']} months")
        self._refresh_items()

    def _refresh_items(self) -> None:
        self.items_tree.delete(*self.items_tree.get_children())
        if self.selected_id is None:
            return
        for it in scenarios.list_items(self.selected_id):
            self.items_tree.insert("", "end", iid=str(it["ScenarioItemID"]),
                                   values=(
                it["ScenarioItemID"],
                it["ItemDescription"],
                fmt_money(it["Amount"]),
                it["TransactionType"],
                it["Frequency"],
            ))

    # ------------------------------------------------------------------
    def _new_scenario(self) -> None:
        dlg = NewScenarioDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            try:
                new_id = scenarios.create(user_id=self.user_id, **dlg.result)
            except Exception as exc:                        # noqa: BLE001
                messagebox.showerror("Error", str(exc))
                return
            self._refresh_list()
            self.list_tree.selection_set(str(new_id))
            self._on_select(None)

    def _delete_scenario(self) -> None:
        if self.selected_id is None:
            return
        if not messagebox.askyesno("Delete",
                                   "Delete this scenario and all its items?"):
            return
        scenarios.delete(self.selected_id)
        self.selected_id = None
        self.lbl_title.configure(text="Pick or create a scenario.")
        self._refresh_list()
        self._refresh_items()

    def _add_item(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("Add item", "Pick a scenario first.")
            return
        try:
            desc = self.e_desc.get().strip()
            if not desc:
                raise ValueError("Description is required.")
            amt = parse_decimal(self.e_amt.get())
            scenarios.add_item(scenario_id=self.selected_id,
                               category_id=None, description=desc,
                               amount=amt, ttype=self.cb_type.get(),
                               frequency=self.cb_freq.get())
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("Add item", str(exc))
            return
        self.e_desc.delete(0, "end"); self.e_amt.delete(0, "end")
        self._refresh_items()

    def _remove_item(self) -> None:
        sel = self.items_tree.selection()
        if not sel:
            return
        scenarios.delete_item(int(sel[0]))
        self._refresh_items()

    # ------------------------------------------------------------------
    def _simulate(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("Simulate", "Pick a scenario first.")
            return
        try:
            data = simulate_scenario(self.user_id, self.selected_id)
        except Exception as exc:                            # noqa: BLE001
            messagebox.showerror("Simulate", str(exc))
            return

        for w in self.chart_frame.winfo_children():
            w.destroy()
        fig = Figure(figsize=(6, 3.5), dpi=100)
        ax = fig.add_subplot(111)
        ax.plot(data["months"], data["baseline_balance"],
                label="Baseline", linewidth=2)
        ax.plot(data["months"], data["scenario_balance"],
                label=data["scenario_name"], linewidth=2, linestyle="--")
        ax.set_title("Projected balance vs baseline")
        ax.set_xlabel("Months ahead")
        ax.set_ylabel("Balance (TRY)")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")


class NewScenarioDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result: dict | None = None
        self.title("New scenario")
        self.geometry("400x340")
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="Name").pack(anchor="w", padx=18, pady=(18, 2))
        self.e_name = ctk.CTkEntry(self, width=360)
        self.e_name.pack(padx=18)

        ctk.CTkLabel(self, text="Description (optional)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_desc = ctk.CTkEntry(self, width=360)
        self.e_desc.pack(padx=18)

        ctk.CTkLabel(self, text="Simulation horizon (months 1–60)"
                     ).pack(anchor="w", padx=18, pady=(12, 2))
        self.e_months = ctk.CTkEntry(self, width=360)
        self.e_months.insert(0, "6")
        self.e_months.pack(padx=18)

        ctk.CTkButton(self, text="Create", command=self._save
                      ).pack(pady=20, padx=18, fill="x")

    def _save(self) -> None:
        try:
            name = self.e_name.get().strip()
            if not name:
                raise ValueError("Name is required.")
            months = int(self.e_months.get().strip() or "6")
            self.result = {
                "name": name,
                "description": self.e_desc.get().strip() or None,
                "simulation_months": months,
            }
        except Exception as exc:                            # noqa: BLE001
            messagebox.showwarning("New scenario", str(exc))
            return
        self.destroy()
