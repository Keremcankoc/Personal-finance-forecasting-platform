"""
seed/seed_data.py
=================
Generates the demo dataset for the Personal Finance platform.

Two modes:

  $ python -m seed.seed_data --live
        Connects to the configured SQL Server, truncates all tables, and
        inserts ~5,000+ rows directly.

  $ python -m seed.seed_data --dump path/to/database_dump.sql
        Writes a self-contained T-SQL script (CREATE DATABASE + schema +
        INSERTs) to the given path. The script can then be loaded with:
            sqlcmd -S localhost -i database_dump.sql

Counts (approximate; 5,000+ total):
    Users           ~30   (incl. admin + demo)
    Categories      ~80   (system defaults at 3 levels + a few user customs)
    Accounts        ~80
    Transactions    ~4,500   (12+ months)
    RecurringPayments ~120
    Budgets         ~150
    Alerts          ~80
    Scenarios       ~60
    ScenarioItems   ~150

Determinism: Faker is seeded so the same script always produces the same
numbers — useful for the report's "sample result snippet" sections.
"""
from __future__ import annotations
import argparse
import io
import os
import random
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

# Allow running as `python seed/seed_data.py` AND as `python -m seed.seed_data`
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(THIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from faker import Faker
import bcrypt

from config import DB_NAME

RANDOM_SEED = 13                       # Group 13 — fixed seed
fake = Faker("en_US")
Faker.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def _q(value: Any) -> str:
    """Escape a Python value into a T-SQL literal (NVARCHAR-safe)."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, datetime):
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(value, date):
        return f"'{value.strftime('%Y-%m-%d')}'"
    if isinstance(value, str):
        return "N'" + value.replace("'", "''") + "'"
    return "N'" + str(value).replace("'", "''") + "'"


def _ins(table: str, columns: list[str], values: list[Any]) -> str:
    cols = ", ".join(columns)
    vals = ", ".join(_q(v) for v in values)
    return f"INSERT INTO {table} ({cols}) VALUES ({vals});"


# ---------------------------------------------------------------------------
# Dataset generation (in-memory, then either inserted or dumped)
# ---------------------------------------------------------------------------
@dataclass
class Dataset:
    users:        list[dict] = field(default_factory=list)
    categories:   list[dict] = field(default_factory=list)
    accounts:     list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)
    recurring:    list[dict] = field(default_factory=list)
    budgets:      list[dict] = field(default_factory=list)
    alerts:       list[dict] = field(default_factory=list)
    scenarios:    list[dict] = field(default_factory=list)
    scenario_items: list[dict] = field(default_factory=list)


# Realistic system category tree
SYSTEM_CATEGORY_TREE = [
    # (Name, Type, [children])
    ("Salary",              "Income",  []),
    ("Freelance",           "Income",  []),
    ("Investment Income",   "Income",  ["Dividends", "Capital Gains", "Interest"]),
    ("Other Income",        "Income",  ["Gifts Received", "Refunds", "Cash Back"]),
    ("Food & Dining",       "Expense", ["Groceries", "Restaurants", "Coffee Shops", "Snacks"]),
    ("Transportation",      "Expense", ["Fuel", "Public Transit", "Taxi", "Vehicle Maintenance"]),
    ("Housing",             "Expense", ["Rent", "Utilities", "Internet", "Home Repair"]),
    ("Health & Wellness",   "Expense", ["Pharmacy", "Doctor", "Gym Membership", "Therapy"]),
    ("Shopping",            "Expense", ["Clothing", "Electronics", "Home Goods", "Personal Care"]),
    ("Entertainment",       "Expense", ["Streaming", "Cinema", "Concerts", "Hobbies"]),
    ("Education",           "Expense", ["Tuition", "Books", "Online Courses"]),
    ("Travel",              "Expense", ["Flights", "Hotels", "Activities"]),
    ("Bills & Subscriptions","Expense", ["Phone", "Software", "Insurance"]),
    ("Other Expense",       "Expense", ["Charity", "Fees", "Miscellaneous"]),
]

ACCOUNT_TYPES = ["Cash", "Bank", "CreditCard", "Savings", "Investment"]
RECURRING_TEMPLATES = [
    ("Netflix subscription",   "Streaming",     "Monthly",   Decimal("149.99")),
    ("Spotify Premium",        "Streaming",     "Monthly",   Decimal("59.99")),
    ("Gym membership",         "Gym Membership","Monthly",   Decimal("499.00")),
    ("Phone plan",             "Phone",         "Monthly",   Decimal("249.00")),
    ("Internet bill",          "Internet",      "Monthly",   Decimal("349.00")),
    ("Electric bill",          "Utilities",     "Monthly",   Decimal("420.00")),
    ("Water bill",             "Utilities",     "Monthly",   Decimal("180.00")),
    ("Cloud storage",          "Software",      "Yearly",    Decimal("999.00")),
    ("Salary",                 "Salary",        "Monthly",   Decimal("28000.00")),
    ("Freelance retainer",     "Freelance",     "Monthly",   Decimal("6500.00")),
]


# ---------------------------------------------------------------------------
def build_dataset() -> Dataset:
    ds = Dataset()
    today = date.today()

    # --- Users ---------------------------------------------------------
    # 2 fixed demo users + 1 second admin + 27 generated regular users
    ds.users.append({
        "UserID": 1, "Username": "admin", "Email": "admin@example.com",
        "PasswordHash": _hash("Admin123!"),
        "FirstName": "System", "LastName": "Administrator",
        "PreferredCurrency": "TRY", "Role": "Admin", "IsActive": True,
        "CreatedAt": datetime.now() - timedelta(days=400),
        "LastLoginAt": datetime.now() - timedelta(days=1),
    })
    ds.users.append({
        "UserID": 2, "Username": "demo", "Email": "demo@example.com",
        "PasswordHash": _hash("Demo123!"),
        "FirstName": "Demo", "LastName": "User",
        "PreferredCurrency": "TRY", "Role": "User", "IsActive": True,
        "CreatedAt": datetime.now() - timedelta(days=400),
        "LastLoginAt": datetime.now() - timedelta(days=2),
    })
    ds.users.append({
        "UserID": 3, "Username": "moderator", "Email": "mod@example.com",
        "PasswordHash": _hash("Mod12345!"),
        "FirstName": "Mert", "LastName": "Yıldız",
        "PreferredCurrency": "TRY", "Role": "Admin", "IsActive": True,
        "CreatedAt": datetime.now() - timedelta(days=300),
        "LastLoginAt": datetime.now() - timedelta(days=4),
    })
    used_usernames = {u["Username"] for u in ds.users}
    used_emails = {u["Email"] for u in ds.users}
    for i in range(4, 31):
        first = fake.first_name()
        last = fake.last_name()
        base_user = (first.lower() + last.lower())[:14]
        username = base_user
        suffix = 1
        while username in used_usernames:
            username = f"{base_user}{suffix}"; suffix += 1
        used_usernames.add(username)
        email = f"{username}@example.com"
        if email in used_emails:
            email = f"{username}{i}@example.com"
        used_emails.add(email)
        ds.users.append({
            "UserID": i, "Username": username, "Email": email,
            "PasswordHash": _hash("User1234!"),
            "FirstName": first, "LastName": last,
            "PreferredCurrency": "TRY", "Role": "User", "IsActive": True,
            "CreatedAt": fake.date_time_between(start_date="-18m", end_date="-1m"),
            "LastLoginAt": fake.date_time_between(start_date="-30d", end_date="now"),
        })

    # --- Categories (system tree) -------------------------------------
    cat_id = 1
    name_to_id: dict[str, int] = {}
    for parent_name, ptype, children in SYSTEM_CATEGORY_TREE:
        parent_id = cat_id
        ds.categories.append({
            "CategoryID": cat_id, "CategoryName": parent_name,
            "CategoryType": ptype, "Description": f"{parent_name} (system)",
            "IconName": None, "ParentCategoryID": None,
            "UserID": None, "IsActive": True,
        })
        name_to_id[parent_name] = cat_id
        cat_id += 1
        for child_name in children:
            ds.categories.append({
                "CategoryID": cat_id, "CategoryName": child_name,
                "CategoryType": ptype, "Description": None,
                "IconName": None, "ParentCategoryID": parent_id,
                "UserID": None, "IsActive": True,
            })
            name_to_id[child_name] = cat_id
            cat_id += 1
    # A few user-custom categories for the demo user (UserID = 2)
    custom = [("Side hustle", "Income"), ("Pet care", "Expense"),
              ("Plant shop", "Expense"), ("Online courses", "Expense")]
    for name, ctype in custom:
        ds.categories.append({
            "CategoryID": cat_id, "CategoryName": name, "CategoryType": ctype,
            "Description": "User-custom", "IconName": None,
            "ParentCategoryID": None, "UserID": 2, "IsActive": True,
        })
        name_to_id[f"USER:{name}"] = cat_id
        cat_id += 1
    # And a custom category for several other users
    for u in ds.users[3:13]:                # ~10 random users
        ds.categories.append({
            "CategoryID": cat_id, "CategoryName": "Personal",
            "CategoryType": "Expense", "Description": "User-custom",
            "IconName": None, "ParentCategoryID": None,
            "UserID": u["UserID"], "IsActive": True,
        })
        cat_id += 1

    # IDs of usable expense / income leaf categories
    expense_leaf_ids = [c["CategoryID"] for c in ds.categories
                        if c["CategoryType"] == "Expense"
                        and c["UserID"] is None
                        and c["ParentCategoryID"] is not None]
    income_leaf_ids = [c["CategoryID"] for c in ds.categories
                       if c["CategoryType"] == "Income"
                       and c["UserID"] is None
                       and c["ParentCategoryID"] is not None]
    salary_id = name_to_id["Salary"]

    # --- Accounts ------------------------------------------------------
    acc_id = 1
    for u in ds.users:
        if u["Role"] == "Admin":
            continue
        # 2-4 accounts per user
        n_acc = random.randint(2, 4)
        types_pick = random.sample(ACCOUNT_TYPES, n_acc)
        for at in types_pick:
            ds.accounts.append({
                "AccountID": acc_id, "UserID": u["UserID"],
                "AccountName": f"{u['FirstName']}'s {at}",
                "AccountType": at,
                "Balance": Decimal("0.00"),     # filled by transactions
                "Currency": "TRY", "IsActive": True,
                "CreatedAt": u["CreatedAt"],
            })
            acc_id += 1

    user_accounts: dict[int, list[int]] = {}
    for a in ds.accounts:
        user_accounts.setdefault(a["UserID"], []).append(a["AccountID"])
    account_balance: dict[int, Decimal] = {a["AccountID"]: Decimal("0") for a in ds.accounts}

    # --- Transactions (12+ months back) -------------------------------
    tx_id = 1
    months_back = 14
    for u in ds.users:
        if u["Role"] == "Admin":
            continue
        accs = user_accounts.get(u["UserID"], [])
        if not accs:
            continue
        # Per-user volume: heavier for demo user
        per_month = 25 if u["UserID"] == 2 else random.randint(10, 14)
        for m_off in range(months_back, 0, -1):
            base_month_start = (today.replace(day=1) - timedelta(days=31 * m_off))
            base_month_start = base_month_start.replace(day=1)
            # 1 salary + N expenses + 0..2 random income
            salary_day = base_month_start.replace(day=1) + timedelta(days=random.randint(0, 4))
            ds.transactions.append({
                "TransactionID": tx_id, "UserID": u["UserID"],
                "AccountID": random.choice(accs),
                "CategoryID": salary_id,
                "Amount": Decimal(random.randint(22000, 35000)),
                "TransactionType": "Income",
                "TransactionDate": salary_day,
                "Description": "Monthly salary", "Notes": None,
                "IsRecurring": False,
                "CreatedAt": datetime.combine(salary_day, datetime.min.time()),
            })
            tx_id += 1
            for _ in range(per_month):
                d_offset = random.randint(0, 27)
                txn_date = base_month_start + timedelta(days=d_offset)
                if txn_date > today:
                    continue
                cat = random.choice(expense_leaf_ids)
                amt = Decimal(random.randint(15, 800)) + Decimal(random.choice(["0.00", "0.49", "0.99"]))
                ds.transactions.append({
                    "TransactionID": tx_id, "UserID": u["UserID"],
                    "AccountID": random.choice(accs),
                    "CategoryID": cat,
                    "Amount": amt, "TransactionType": "Expense",
                    "TransactionDate": txn_date,
                    "Description": fake.sentence(nb_words=4)[:80],
                    "Notes": None, "IsRecurring": False,
                    "CreatedAt": datetime.combine(txn_date, datetime.min.time()),
                })
                tx_id += 1
            # 0..2 misc income events per month
            for _ in range(random.randint(0, 2)):
                d_offset = random.randint(0, 27)
                txn_date = base_month_start + timedelta(days=d_offset)
                if txn_date > today:
                    continue
                cat = random.choice(income_leaf_ids)
                amt = Decimal(random.randint(150, 4500))
                ds.transactions.append({
                    "TransactionID": tx_id, "UserID": u["UserID"],
                    "AccountID": random.choice(accs),
                    "CategoryID": cat, "Amount": amt,
                    "TransactionType": "Income",
                    "TransactionDate": txn_date,
                    "Description": fake.sentence(nb_words=3)[:80],
                    "Notes": None, "IsRecurring": False,
                    "CreatedAt": datetime.combine(txn_date, datetime.min.time()),
                })
                tx_id += 1

    # Aggregate balances back into the Accounts list
    for t in ds.transactions:
        signed = t["Amount"] if t["TransactionType"] == "Income" else -t["Amount"]
        account_balance[t["AccountID"]] += signed
    for a in ds.accounts:
        a["Balance"] = account_balance[a["AccountID"]].quantize(Decimal("0.01"))

    # --- Recurring payments -------------------------------------------
    rp_id = 1
    for u in ds.users:
        if u["Role"] == "Admin":
            continue
        accs = user_accounts.get(u["UserID"], [])
        if not accs:
            continue
        n_rp = random.randint(3, 6)
        templates = random.sample(RECURRING_TEMPLATES, n_rp)
        for desc, cat_name, freq, amt in templates:
            cat_id_local = name_to_id.get(cat_name)
            if not cat_id_local:
                continue
            ttype = "Income" if cat_name in ("Salary", "Freelance") else "Expense"
            start = today - timedelta(days=random.randint(60, 720))
            next_charge = today + timedelta(days=random.randint(-2, 25))
            ds.recurring.append({
                "RecurringPaymentID": rp_id, "UserID": u["UserID"],
                "AccountID": random.choice(accs),
                "CategoryID": cat_id_local,
                "Amount": amt, "TransactionType": ttype,
                "Frequency": freq, "StartDate": start,
                "EndDate": None, "NextChargeDate": next_charge,
                "Description": desc, "IsActive": True,
                "CreatedAt": datetime.combine(start, datetime.min.time()),
            })
            rp_id += 1

    # --- Budgets -------------------------------------------------------
    b_id = 1
    period_choices = ["Monthly", "Monthly", "Monthly", "Weekly", "Yearly"]
    for u in ds.users:
        if u["Role"] == "Admin":
            continue
        n_b = random.randint(4, 7)
        cats_for_user = random.sample(expense_leaf_ids, min(n_b, len(expense_leaf_ids)))
        for cid in cats_for_user:
            period = random.choice(period_choices)
            if period == "Weekly":
                start = today - timedelta(days=today.weekday())
                end = start + timedelta(days=6)
                amt = Decimal(random.randint(500, 1500))
            elif period == "Yearly":
                start = today.replace(month=1, day=1)
                end = today.replace(month=12, day=31)
                amt = Decimal(random.randint(8000, 25000))
            else:
                start = today.replace(day=1)
                next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
                end = next_month - timedelta(days=1)
                amt = Decimal(random.randint(800, 4500))
            ds.budgets.append({
                "BudgetID": b_id, "UserID": u["UserID"],
                "CategoryID": cid, "BudgetAmount": amt,
                "PeriodType": period, "StartDate": start,
                "EndDate": end, "CreatedAt": datetime.now() - timedelta(days=20),
            })
            b_id += 1

    # --- Alerts --------------------------------------------------------
    a_id = 1
    for b in random.sample(ds.budgets, min(40, len(ds.budgets))):
        ds.alerts.append({
            "AlertID": a_id, "UserID": b["UserID"],
            "AlertType": random.choice(["BudgetWarning", "BudgetExceeded"]),
            "Title": "Budget threshold reached",
            "Message": "Spending in this category is approaching the limit.",
            "IsRead": random.choice([True, False, False]),
            "CreatedAt": datetime.now() - timedelta(days=random.randint(0, 20)),
            "RelatedBudgetID": b["BudgetID"],
            "RelatedRecurringPaymentID": None,
        })
        a_id += 1
    for r in random.sample(ds.recurring, min(40, len(ds.recurring))):
        ds.alerts.append({
            "AlertID": a_id, "UserID": r["UserID"],
            "AlertType": "UpcomingPayment",
            "Title": f"Upcoming: {r['Description']}",
            "Message": "A recurring payment is due in the next few days.",
            "IsRead": False,
            "CreatedAt": datetime.now() - timedelta(days=random.randint(0, 5)),
            "RelatedBudgetID": None,
            "RelatedRecurringPaymentID": r["RecurringPaymentID"],
        })
        a_id += 1

    # --- Scenarios + items --------------------------------------------
    s_id = 1
    si_id = 1
    scenario_blueprints = [
        ("Buy a car", "I want to model the cost of buying a small used car.",
         [("Car loan payment", "Expense", "Monthly", Decimal("4500")),
          ("Car insurance",    "Expense", "Monthly", Decimal("400")),
          ("Down payment",     "Expense", "OneTime", Decimal("80000"))]),
        ("Move out", "Renting my own flat in Eskişehir.",
         [("New rent",       "Expense", "Monthly", Decimal("8500")),
          ("Utilities bump", "Expense", "Monthly", Decimal("700")),
          ("Furniture",      "Expense", "OneTime", Decimal("25000"))]),
        ("Side income", "Freelance contract that brings in extra money.",
         [("Side income",    "Income",  "Monthly", Decimal("3500"))]),
        ("Travel plan", "Three-week trip to Spain.",
         [("Flights",        "Expense", "OneTime", Decimal("18000")),
          ("Hotels",         "Expense", "OneTime", Decimal("32000")),
          ("Daily expenses", "Expense", "Daily",   Decimal("500"))]),
    ]
    for u in ds.users[1:]:                    # all non-first users get scenarios
        if u["Role"] == "Admin":
            continue
        for blueprint_name, desc, items in random.sample(scenario_blueprints,
                                                         random.randint(2, 4)):
            ds.scenarios.append({
                "ScenarioID": s_id, "UserID": u["UserID"],
                "ScenarioName": blueprint_name, "Description": desc,
                "SimulationMonths": random.choice([3, 6, 12]),
                "CreatedAt": datetime.now() - timedelta(days=random.randint(2, 60)),
            })
            for item_desc, ttype, freq, amt in items:
                ds.scenario_items.append({
                    "ScenarioItemID": si_id, "ScenarioID": s_id,
                    "CategoryID": None, "ItemDescription": item_desc,
                    "Amount": amt, "TransactionType": ttype, "Frequency": freq,
                })
                si_id += 1
            s_id += 1

    return ds


# ---------------------------------------------------------------------------
# Insertion: live SQL Server vs. dump file
# ---------------------------------------------------------------------------
SCHEMA_FILE_PATH = os.path.join(PROJECT_ROOT, "schema.sql")


def _write_inserts(out: io.StringIO, ds: Dataset) -> None:
    out.write("\nSET IDENTITY_INSERT Users ON;\n")
    cols = ["UserID", "Username", "Email", "PasswordHash", "FirstName",
            "LastName", "PreferredCurrency", "Role", "IsActive",
            "CreatedAt", "LastLoginAt"]
    for u in ds.users:
        out.write(_ins("Users", cols, [u[c] for c in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Users OFF;\n")

    out.write("\nSET IDENTITY_INSERT Categories ON;\n")
    cols = ["CategoryID", "CategoryName", "CategoryType", "Description",
            "IconName", "ParentCategoryID", "UserID", "IsActive"]
    for c in ds.categories:
        out.write(_ins("Categories", cols, [c[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Categories OFF;\n")

    out.write("\nSET IDENTITY_INSERT Accounts ON;\n")
    cols = ["AccountID", "UserID", "AccountName", "AccountType", "Balance",
            "Currency", "IsActive", "CreatedAt"]
    for a in ds.accounts:
        out.write(_ins("Accounts", cols, [a[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Accounts OFF;\n")

    out.write("\nSET IDENTITY_INSERT Transactions ON;\n")
    cols = ["TransactionID", "UserID", "AccountID", "CategoryID", "Amount",
            "TransactionType", "TransactionDate", "Description", "Notes",
            "IsRecurring", "CreatedAt"]
    # Batched for sqlcmd performance
    batch_size = 200
    for i in range(0, len(ds.transactions), batch_size):
        for t in ds.transactions[i:i + batch_size]:
            out.write(_ins("Transactions", cols, [t[col] for col in cols]) + "\n")
        out.write("GO\n")
    out.write("SET IDENTITY_INSERT Transactions OFF;\n")

    out.write("\nSET IDENTITY_INSERT RecurringPayments ON;\n")
    cols = ["RecurringPaymentID", "UserID", "AccountID", "CategoryID",
            "Amount", "TransactionType", "Frequency", "StartDate", "EndDate",
            "NextChargeDate", "Description", "IsActive", "CreatedAt"]
    for r in ds.recurring:
        out.write(_ins("RecurringPayments", cols, [r[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT RecurringPayments OFF;\n")

    out.write("\nSET IDENTITY_INSERT Budgets ON;\n")
    cols = ["BudgetID", "UserID", "CategoryID", "BudgetAmount", "PeriodType",
            "StartDate", "EndDate", "CreatedAt"]
    for b in ds.budgets:
        out.write(_ins("Budgets", cols, [b[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Budgets OFF;\n")

    out.write("\nSET IDENTITY_INSERT Alerts ON;\n")
    cols = ["AlertID", "UserID", "AlertType", "Title", "Message", "IsRead",
            "CreatedAt", "RelatedBudgetID", "RelatedRecurringPaymentID"]
    for a in ds.alerts:
        out.write(_ins("Alerts", cols, [a[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Alerts OFF;\n")

    out.write("\nSET IDENTITY_INSERT Scenarios ON;\n")
    cols = ["ScenarioID", "UserID", "ScenarioName", "Description",
            "SimulationMonths", "CreatedAt"]
    for s in ds.scenarios:
        out.write(_ins("Scenarios", cols, [s[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT Scenarios OFF;\n")

    out.write("\nSET IDENTITY_INSERT ScenarioItems ON;\n")
    cols = ["ScenarioItemID", "ScenarioID", "CategoryID", "ItemDescription",
            "Amount", "TransactionType", "Frequency"]
    for si in ds.scenario_items:
        out.write(_ins("ScenarioItems", cols, [si[col] for col in cols]) + "\n")
    out.write("SET IDENTITY_INSERT ScenarioItems OFF;\n")


def write_dump(path: str) -> None:
    """Build the in-memory dataset and write a self-contained T-SQL dump."""
    ds = build_dataset()
    if not os.path.exists(SCHEMA_FILE_PATH):
        raise FileNotFoundError(
            f"schema.sql not found at {SCHEMA_FILE_PATH}. "
            "It should sit next to the seed/ folder.")
    with open(SCHEMA_FILE_PATH, "r", encoding="utf-8") as fh:
        schema_sql = fh.read()

    out = io.StringIO()
    out.write("/* ============================================================\n")
    out.write("   database_dump.sql — generated by seed/seed_data.py\n")
    out.write(f"   Generated:  {datetime.now().isoformat(timespec='seconds')}\n")
    out.write(f"   Random seed: {RANDOM_SEED}\n")
    out.write("   Run with:   sqlcmd -S localhost -i database_dump.sql\n")
    out.write("   ============================================================ */\n\n")

    out.write("IF DB_ID(N'" + DB_NAME + "') IS NULL\n")
    out.write("    CREATE DATABASE [" + DB_NAME + "];\n")
    out.write("GO\n")
    out.write("USE [" + DB_NAME + "];\n")
    out.write("GO\n\n")

    # Drop tables in reverse FK order if rerunning
    out.write("/* Idempotent reset: drop child-first */\n")
    for t in ["ScenarioItems", "Scenarios", "Alerts", "Budgets",
              "RecurringPayments", "Transactions", "Accounts",
              "Categories", "Users"]:
        out.write(f"IF OBJECT_ID(N'{t}', 'U') IS NOT NULL DROP TABLE [{t}];\n")
    out.write("GO\n\n")

    out.write("/* ----- Schema (from schema.sql) ----- */\n")
    out.write(schema_sql)
    out.write("\nGO\n")

    out.write("/* ----- Seed data ----- */\n")
    _write_inserts(out, ds)
    out.write("\nGO\n")

    out.write("/* ----- Performance indexes ----- */\n")
    out.write(
        "CREATE INDEX IX_Transactions_User_Date ON Transactions(UserID, TransactionDate);\n"
        "CREATE INDEX IX_Transactions_User_Cat  ON Transactions(UserID, CategoryID);\n"
        "CREATE INDEX IX_Recurring_User_Next    ON RecurringPayments(UserID, NextChargeDate);\n"
        "CREATE INDEX IX_Budgets_User_Period    ON Budgets(UserID, StartDate, EndDate);\n"
        "CREATE INDEX IX_Alerts_User_Unread     ON Alerts(UserID, IsRead);\n"
        "GO\n"
    )

    out.write("PRINT N'Seed complete.';\n")
    out.write(f"PRINT N'Users: {len(ds.users)} | Categories: {len(ds.categories)} | "
              f"Accounts: {len(ds.accounts)} | Transactions: {len(ds.transactions)} | "
              f"Recurring: {len(ds.recurring)} | Budgets: {len(ds.budgets)} | "
              f"Alerts: {len(ds.alerts)} | Scenarios: {len(ds.scenarios)} | "
              f"ScenarioItems: {len(ds.scenario_items)}';\n")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(out.getvalue())

    total = (len(ds.users) + len(ds.categories) + len(ds.accounts)
             + len(ds.transactions) + len(ds.recurring)
             + len(ds.budgets) + len(ds.alerts)
             + len(ds.scenarios) + len(ds.scenario_items))
    print(f"Wrote {path}")
    print(f"Total rows generated: {total}")


def insert_live() -> None:
    """Insert the dataset directly via pyodbc."""
    from db import cursor_scope, run_script   # imported lazily

    if os.path.exists(SCHEMA_FILE_PATH):
        with open(SCHEMA_FILE_PATH, "r", encoding="utf-8") as fh:
            run_script(fh.read())
        print("Schema installed.")

    ds = build_dataset()
    with cursor_scope() as cur:
        # Wipe in FK-safe order
        for t in ("ScenarioItems", "Scenarios", "Alerts", "Budgets",
                  "RecurringPayments", "Transactions", "Accounts",
                  "Categories", "Users"):
            cur.execute(f"DELETE FROM {t};")
        # Now insert via SET IDENTITY_INSERT for predictable IDs
        for table, rows, cols in [
            ("Users", ds.users, ["UserID","Username","Email","PasswordHash",
                                  "FirstName","LastName","PreferredCurrency","Role",
                                  "IsActive","CreatedAt","LastLoginAt"]),
            ("Categories", ds.categories, ["CategoryID","CategoryName","CategoryType",
                                             "Description","IconName",
                                             "ParentCategoryID","UserID","IsActive"]),
            ("Accounts", ds.accounts, ["AccountID","UserID","AccountName","AccountType",
                                         "Balance","Currency","IsActive","CreatedAt"]),
            ("Transactions", ds.transactions, ["TransactionID","UserID","AccountID",
                                                 "CategoryID","Amount","TransactionType",
                                                 "TransactionDate","Description","Notes",
                                                 "IsRecurring","CreatedAt"]),
            ("RecurringPayments", ds.recurring, ["RecurringPaymentID","UserID",
                                                   "AccountID","CategoryID","Amount",
                                                   "TransactionType","Frequency",
                                                   "StartDate","EndDate","NextChargeDate",
                                                   "Description","IsActive","CreatedAt"]),
            ("Budgets", ds.budgets, ["BudgetID","UserID","CategoryID","BudgetAmount",
                                       "PeriodType","StartDate","EndDate","CreatedAt"]),
            ("Alerts", ds.alerts, ["AlertID","UserID","AlertType","Title","Message",
                                     "IsRead","CreatedAt","RelatedBudgetID",
                                     "RelatedRecurringPaymentID"]),
            ("Scenarios", ds.scenarios, ["ScenarioID","UserID","ScenarioName",
                                           "Description","SimulationMonths","CreatedAt"]),
            ("ScenarioItems", ds.scenario_items, ["ScenarioItemID","ScenarioID",
                                                    "CategoryID","ItemDescription",
                                                    "Amount","TransactionType","Frequency"]),
        ]:
            cur.execute(f"SET IDENTITY_INSERT {table} ON;")
            placeholders = ", ".join(["?"] * len(cols))
            insert_sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders});"
            for row in rows:
                cur.execute(insert_sql, [row[c] for c in cols])
            cur.execute(f"SET IDENTITY_INSERT {table} OFF;")

    print(f"Live insert complete. Transactions: {len(ds.transactions)}")


# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="Generate the demo dataset.")
    p.add_argument("--live", action="store_true",
                   help="Insert directly into SQL Server (uses config.py).")
    p.add_argument("--dump", metavar="PATH",
                   help="Write a self-contained .sql dump to PATH.")
    args = p.parse_args()

    if not args.live and not args.dump:
        p.error("Pass either --live or --dump <path>.")
    if args.live:
        insert_live()
    if args.dump:
        write_dump(args.dump)


if __name__ == "__main__":
    main()
