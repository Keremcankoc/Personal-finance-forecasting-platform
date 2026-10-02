"""
config.py
=========
Central configuration for the Personal Finance Simulation & Forecasting Platform.
Edit the SQL Server connection settings below to match your local environment.

The app uses Microsoft SQL Server (Express edition is fine) via pyodbc with
ODBC Driver 17 or 18 for SQL Server. Trusted Connection (Windows auth) is
the default; switch to SQL auth by setting USE_TRUSTED_CONNECTION = False
and providing DB_USER / DB_PASSWORD.
"""

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
DB_DRIVER = "ODBC Driver 17 for SQL Server"   # or "ODBC Driver 18 for SQL Server"
DB_SERVER = "localhost"                       # e.g. "localhost\\SQLEXPRESS"
DB_NAME = "PersonalFinanceDB"
USE_TRUSTED_CONNECTION = True                 # Windows authentication
DB_USER = "sa"                                  # used only when USE_TRUSTED_CONNECTION = False
DB_PASSWORD = "YourStrongPasswordHere"

# Driver 18 enforces TLS by default; this disables cert validation on
# local dev machines. Drop the option in production.
EXTRA_CONN_OPTIONS = "TrustServerCertificate=yes;Encrypt=no;"


def build_connection_string() -> str:
    """Assemble the ODBC connection string from the values above."""
    parts = [
        f"DRIVER={{{DB_DRIVER}}}",
        f"SERVER={DB_SERVER}",
        f"DATABASE={DB_NAME}",
    ]
    if USE_TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={DB_USER}")
        parts.append(f"PWD={DB_PASSWORD}")
    parts.append(EXTRA_CONN_OPTIONS.rstrip(";"))
    return ";".join(parts) + ";"


# ---------------------------------------------------------------------------
# Application constants
# ---------------------------------------------------------------------------
APP_NAME = "Personal Finance Simulation & Forecasting Platform"
APP_VERSION = "1.0.0 (Phase 2)"

DEFAULT_CURRENCY = "TRY"
CURRENCY_SYMBOL = "\u20BA"   # ₺

# Date format for the UI (Turkish style); storage stays as DATE / DATETIME2.
UI_DATE_FORMAT = "%d.%m.%Y"
UI_DATETIME_FORMAT = "%d.%m.%Y %H:%M"

# customtkinter appearance
CTK_APPEARANCE_MODE = "System"   # "Light", "Dark", "System"
CTK_COLOR_THEME = "blue"

# Alert thresholds (percent of budget consumed)
BUDGET_WARNING_THRESHOLD = 80.0
BUDGET_EXCEEDED_THRESHOLD = 100.0

# Look-ahead window (days) for "upcoming recurring payment" alerts
RECURRING_PAYMENT_LOOKAHEAD_DAYS = 3
