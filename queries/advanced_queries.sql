/* ============================================================
   advanced_queries.sql
   --------------------
   The five advanced T-SQL queries promised in Phase 1 §1.5.
   Each block starts with a `-- @name=<id>` marker; db.py parses these
   so the Python layer can call them by name, e.g.

       run_named_query('Q1_MonthlySpendingTrend', (user_id,))

   All ? placeholders are bound by pyodbc using parameterised
   substitution. No string concatenation is used anywhere.

   Parameter conventions (all queries):
       ?_1  : UserID                 (every query)
       ?_2  : extra parameter        (Q2 only: forecast horizon in months)

   Tested against Microsoft SQL Server 2019+ with an ODBC Driver 17/18
   client.
   ============================================================ */


-- ============================================================
-- Q1 — Monthly Spending Trend per Category
-- 6-month spending history grouped by month and (top-level)
-- category. Resolves the parent category name via a self-join,
-- so users see the rolled-up bucket name (e.g. 'Food & Dining'
-- rather than 'Snacks').
-- Used by: gui/analytics_view.py — stacked area / multi-line chart.
-- @name=Q1_MonthlySpendingTrend
-- ============================================================
SELECT
    FORMAT(t.TransactionDate, 'yyyy-MM')          AS YearMonth,
    COALESCE(parent.CategoryName, c.CategoryName) AS TopCategory,
    SUM(t.Amount)                                 AS TotalSpent,
    COUNT(*)                                      AS TxCount
FROM Transactions   t
JOIN Categories     c       ON c.CategoryID = t.CategoryID
LEFT JOIN Categories parent ON parent.CategoryID = c.ParentCategoryID
WHERE t.UserID            = ?
  AND t.TransactionType   = 'Expense'
  AND t.TransactionDate  >= DATEADD(MONTH, -6, CAST(GETDATE() AS DATE))
GROUP BY FORMAT(t.TransactionDate, 'yyyy-MM'),
         COALESCE(parent.CategoryName, c.CategoryName)
ORDER BY YearMonth, TopCategory;



-- ============================================================
-- Q2 — Savings Forecast
-- A CTE averages the user's last 3 months of income and expense,
-- then a recursive CTE projects net savings for the next N months.
-- Returns one row per future month with running cumulative savings.
-- Used by: gui/analytics_view.py — line chart with projected band.
-- @name=Q2_SavingsForecast
-- ============================================================
WITH MonthlyTotals AS (
    SELECT FORMAT(TransactionDate, 'yyyy-MM') AS YM,
           TransactionType,
           SUM(Amount) AS MonthlyTotal
      FROM Transactions
     WHERE UserID = ?
       AND TransactionDate >= DATEADD(MONTH, -3, CAST(GETDATE() AS DATE))
     GROUP BY FORMAT(TransactionDate, 'yyyy-MM'), TransactionType
),
Averages AS (
    SELECT
      COALESCE(AVG(CASE WHEN TransactionType = 'Income'  THEN MonthlyTotal END), 0) AS AvgIncome,
      COALESCE(AVG(CASE WHEN TransactionType = 'Expense' THEN MonthlyTotal END), 0) AS AvgExpense
      FROM MonthlyTotals
),
Forecast AS (
    SELECT
        1                                                         AS MonthOffset,
        DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)       AS MonthStart,
        AvgIncome,
        AvgExpense,
        (AvgIncome - AvgExpense)                                  AS MonthlyNet,
        (AvgIncome - AvgExpense)                                  AS CumulativeNet
      FROM Averages
    UNION ALL
    SELECT
        f.MonthOffset + 1,
        DATEADD(MONTH, 1, f.MonthStart),
        f.AvgIncome,
        f.AvgExpense,
        f.MonthlyNet,
        f.CumulativeNet + f.MonthlyNet
      FROM Forecast f
     WHERE f.MonthOffset < ?
)
SELECT
    MonthOffset,
    FORMAT(MonthStart, 'yyyy-MM') AS YearMonth,
    AvgIncome,
    AvgExpense,
    MonthlyNet,
    CumulativeNet
  FROM Forecast
 ORDER BY MonthOffset
OPTION (MAXRECURSION 60);



-- ============================================================
-- Q3 — Top 5 Spending Categories with Budget Utilization
-- Ranks the user's top 5 expense categories for the current
-- calendar month, LEFT JOINs the matching active budget so the
-- query still returns rows when no budget exists, and computes
-- a status column.
-- Used by: gui/analytics_view.py — horizontal bar chart, status colour.
-- @name=Q3_TopCategoriesBudgetUtilization
-- ============================================================
WITH MonthlySpend AS (
    SELECT t.CategoryID,
           c.CategoryName,
           SUM(t.Amount) AS TotalSpent
      FROM Transactions t
      JOIN Categories  c ON c.CategoryID = t.CategoryID
     WHERE t.UserID            = ?
       AND t.TransactionType   = 'Expense'
       AND YEAR(t.TransactionDate)  = YEAR(GETDATE())
       AND MONTH(t.TransactionDate) = MONTH(GETDATE())
     GROUP BY t.CategoryID, c.CategoryName
),
Ranked AS (
    SELECT TOP 5 CategoryID, CategoryName, TotalSpent
      FROM MonthlySpend
     ORDER BY TotalSpent DESC
)
SELECT
    r.CategoryID,
    r.CategoryName,
    r.TotalSpent,
    b.BudgetAmount,
    CASE WHEN b.BudgetAmount IS NULL OR b.BudgetAmount = 0
         THEN NULL
         ELSE CAST(r.TotalSpent * 100.0 / b.BudgetAmount AS DECIMAL(10,2))
    END AS PctUsed,
    CASE
        WHEN b.BudgetAmount IS NULL                            THEN 'NO BUDGET'
        WHEN r.TotalSpent > b.BudgetAmount                     THEN 'EXCEEDED'
        WHEN r.TotalSpent * 100.0 / b.BudgetAmount > 80        THEN 'WARNING'
        ELSE 'OK'
    END AS Status
FROM Ranked r
OUTER APPLY (
    SELECT TOP 1 b1.BudgetAmount
      FROM Budgets b1
     WHERE b1.UserID     = ?
       AND b1.CategoryID = r.CategoryID
       AND b1.PeriodType = 'Monthly'
       AND CAST(GETDATE() AS DATE) BETWEEN b1.StartDate AND b1.EndDate
     ORDER BY b1.BudgetAmount DESC
) b
ORDER BY r.TotalSpent DESC;



-- ============================================================
-- Q4 — Recurring Payment Calendar
-- All active recurring payments for the user, sorted by next
-- charge date. Computes DaysUntilCharge and MonthlyEquivalent
-- using the multipliers spec'd in §1.5 of the Phase 1 report:
--   Daily x30, Weekly x4.345, Biweekly x2.1725, Monthly x1,
--   Quarterly /3, Yearly /12.
-- Used by: gui/analytics_view.py — sortable Treeview.
-- @name=Q4_RecurringPaymentCalendar
-- ============================================================
SELECT
    r.RecurringPaymentID,
    r.Description,
    c.CategoryName,
    a.AccountName,
    r.Amount,
    r.TransactionType,
    r.Frequency,
    r.NextChargeDate,
    DATEDIFF(DAY, CAST(GETDATE() AS DATE), r.NextChargeDate) AS DaysUntilCharge,
    CAST(
        CASE r.Frequency
            WHEN 'Daily'     THEN r.Amount * 30
            WHEN 'Weekly'    THEN r.Amount * 4.345
            WHEN 'Biweekly'  THEN r.Amount * 2.1725
            WHEN 'Monthly'   THEN r.Amount
            WHEN 'Quarterly' THEN r.Amount / 3.0
            WHEN 'Yearly'    THEN r.Amount / 12.0
            ELSE r.Amount
        END
        AS DECIMAL(18,2)
    ) AS MonthlyEquivalent
FROM RecurringPayments r
JOIN Categories c ON c.CategoryID = r.CategoryID
JOIN Accounts   a ON a.AccountID  = r.AccountID
WHERE r.UserID   = ?
  AND r.IsActive = 1
  AND (r.EndDate IS NULL OR r.EndDate >= CAST(GETDATE() AS DATE))
ORDER BY r.NextChargeDate ASC;



-- ============================================================
-- Q5 — Recursive Category Hierarchy with Aggregated Spending
-- Walks the Categories tree from each root down to its leaves
-- using a recursive CTE, builds the full path string
-- (e.g., 'Food & Dining > Groceries > Snacks'), and aggregates
-- the user's spending at each node from the last 12 months.
-- Used by: gui/analytics_view.py — Treeview widget.
-- @name=Q5_CategoryHierarchySpending
-- ============================================================
WITH CategoryTree AS (

    SELECT
        c.CategoryID,
        c.CategoryName,
        c.ParentCategoryID,
        c.UserID                      AS OwnerUserID,
        CAST(c.CategoryName AS NVARCHAR(1000)) AS Path,
        0                             AS Depth
      FROM Categories c
     WHERE c.ParentCategoryID IS NULL
       AND c.IsActive = 1
       AND c.CategoryType = 'Expense'
       AND (c.UserID IS NULL OR c.UserID = ?)
    UNION ALL
    -- Children
    SELECT
        c.CategoryID,
        c.CategoryName,
        c.ParentCategoryID,
        c.UserID,
        CAST(p.Path + N' > ' + c.CategoryName AS NVARCHAR(1000)),
        p.Depth + 1
      FROM Categories c
      JOIN CategoryTree p ON p.CategoryID = c.ParentCategoryID
     WHERE c.IsActive = 1
       AND c.CategoryType = 'Expense'
       AND (c.UserID IS NULL OR c.UserID = p.OwnerUserID)
)
SELECT
    ct.CategoryID,
    ct.ParentCategoryID,
    ct.CategoryName,
    ct.Path,
    ct.Depth,
    COALESCE(s.TotalSpent, 0)        AS TotalSpent,
    COALESCE(s.TxCount, 0)           AS TxCount
FROM CategoryTree ct
LEFT JOIN (
    SELECT CategoryID, SUM(Amount) AS TotalSpent, COUNT(*) AS TxCount
      FROM Transactions
     WHERE TransactionType = 'Expense'
       AND UserID = ?
       AND TransactionDate >= DATEADD(MONTH, -12, CAST(GETDATE() AS DATE))
     GROUP BY CategoryID
) s ON s.CategoryID = ct.CategoryID
ORDER BY ct.Path
OPTION (MAXRECURSION 32);
