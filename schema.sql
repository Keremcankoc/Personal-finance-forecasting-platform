-- ============================================================
-- TABLE 1: Users
-- Purpose: Stores registered user accounts and their profiles.
-- Each user can track their own income, expenses, budgets, etc.
-- ============================================================
CREATE TABLE Users (
    UserID          INT             IDENTITY(1,1)   NOT NULL,
    Username        NVARCHAR(50)    NOT NULL,
    Email           NVARCHAR(100)   NOT NULL,
    PasswordHash    NVARCHAR(256)   NOT NULL,
    FirstName       NVARCHAR(50)    NOT NULL,
    LastName        NVARCHAR(50)    NOT NULL,
    PreferredCurrency NVARCHAR(3)   NOT NULL    DEFAULT N'TRY',
    Role            NVARCHAR(20)    NOT NULL    DEFAULT N'User',
    IsActive        BIT             NOT NULL    DEFAULT 1,
    CreatedAt       DATETIME2       NOT NULL    DEFAULT GETDATE(),
    LastLoginAt     DATETIME2       NULL,

    CONSTRAINT PK_Users PRIMARY KEY (UserID),
    CONSTRAINT UQ_Users_Username UNIQUE (Username),
    CONSTRAINT UQ_Users_Email UNIQUE (Email),
    CONSTRAINT CK_Users_Role CHECK (Role IN (N'User', N'Admin'))
);


-- ============================================================
-- TABLE 2: Categories
-- Purpose: Hierarchical (recursive) category tree for classifying
-- transactions. ParentCategoryID references the same table to
-- allow unlimited nesting (e.g., Food > Groceries > Snacks).
-- ============================================================
CREATE TABLE Categories (
    CategoryID      INT             IDENTITY(1,1)   NOT NULL,
    CategoryName    NVARCHAR(100)   NOT NULL,
    CategoryType    NVARCHAR(10)    NOT NULL,
    Description     NVARCHAR(255)   NULL,
    IconName        NVARCHAR(50)    NULL,
    ParentCategoryID INT            NULL,
    UserID          INT             NULL,           -- NULL = system-default category
    IsActive        BIT             NOT NULL    DEFAULT 1,

    CONSTRAINT PK_Categories PRIMARY KEY (CategoryID),
    CONSTRAINT FK_Categories_Parent FOREIGN KEY (ParentCategoryID)
        REFERENCES Categories(CategoryID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_Categories_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT CK_Categories_Type CHECK (CategoryType IN (N'Income', N'Expense'))
);


-- ============================================================
-- TABLE 3: Accounts
-- Purpose: Represents a user's financial accounts (wallet,
-- bank account, credit card, etc.). Transactions are linked
-- to an account so balances can be tracked per account.
-- ============================================================
CREATE TABLE Accounts (
    AccountID       INT             IDENTITY(1,1)   NOT NULL,
    UserID          INT             NOT NULL,
    AccountName     NVARCHAR(100)   NOT NULL,
    AccountType     NVARCHAR(30)    NOT NULL,
    Balance         DECIMAL(18,2)   NOT NULL    DEFAULT 0.00,
    Currency        NVARCHAR(3)     NOT NULL    DEFAULT N'TRY',
    IsActive        BIT             NOT NULL    DEFAULT 1,
    CreatedAt       DATETIME2       NOT NULL    DEFAULT GETDATE(),

    CONSTRAINT PK_Accounts PRIMARY KEY (AccountID),
    CONSTRAINT FK_Accounts_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT CK_Accounts_Type CHECK (AccountType IN (
        N'Cash', N'Bank', N'CreditCard', N'Savings', N'Investment'))
);


-- ============================================================
-- TABLE 4: Transactions
-- Purpose: Core table – every income or expense entry is a
-- transaction. Links to User, Category, and Account.
-- ============================================================

CREATE TABLE Transactions (
    TransactionID   INT             IDENTITY(1,1)   NOT NULL,
    UserID          INT             NOT NULL,
    AccountID       INT             NOT NULL,
    CategoryID      INT             NOT NULL,
    Amount          DECIMAL(18,2)   NOT NULL,
    TransactionType NVARCHAR(10)    NOT NULL,
    TransactionDate DATE            NOT NULL,
    Description     NVARCHAR(255)   NULL,
    Notes           NVARCHAR(500)   NULL,
    IsRecurring     BIT             NOT NULL    DEFAULT 0,
    CreatedAt       DATETIME2       NOT NULL    DEFAULT GETDATE(),

    CONSTRAINT PK_Transactions PRIMARY KEY (TransactionID),
    CONSTRAINT FK_Transactions_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Transactions_Account FOREIGN KEY (AccountID)
        REFERENCES Accounts(AccountID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_Transactions_Category FOREIGN KEY (CategoryID)
        REFERENCES Categories(CategoryID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_Transactions_Type CHECK (TransactionType IN (N'Income', N'Expense')),
    CONSTRAINT CK_Transactions_Amount CHECK (Amount > 0)
);

-- ============================================================
-- TABLE 5: RecurringPayments
-- Purpose: Defines subscriptions and recurring income/expense
-- entries. The application uses NextChargeDate to auto-generate
-- transactions on schedule.
-- ============================================================

CREATE TABLE RecurringPayments (
    RecurringPaymentID  INT             IDENTITY(1,1)   NOT NULL,
    UserID              INT             NOT NULL,
    AccountID           INT             NOT NULL,
    CategoryID          INT             NOT NULL,
    Amount              DECIMAL(18,2)   NOT NULL,
    TransactionType     NVARCHAR(10)    NOT NULL,
    Frequency           NVARCHAR(20)    NOT NULL,
    StartDate           DATE            NOT NULL,
    EndDate             DATE            NULL,
    NextChargeDate      DATE            NOT NULL,
    Description         NVARCHAR(255)   NOT NULL,
    IsActive            BIT             NOT NULL    DEFAULT 1,
    CreatedAt           DATETIME2       NOT NULL    DEFAULT GETDATE(),

    CONSTRAINT PK_RecurringPayments PRIMARY KEY (RecurringPaymentID),
    CONSTRAINT FK_RecurringPayments_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_RecurringPayments_Account FOREIGN KEY (AccountID)
        REFERENCES Accounts(AccountID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_RecurringPayments_Category FOREIGN KEY (CategoryID)
        REFERENCES Categories(CategoryID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_RecurringPayments_Type CHECK (TransactionType IN (N'Income', N'Expense')),
    CONSTRAINT CK_RecurringPayments_Freq CHECK (Frequency IN (
        N'Daily', N'Weekly', N'Biweekly', N'Monthly', N'Quarterly', N'Yearly')),
    CONSTRAINT CK_RecurringPayments_Amount CHECK (Amount > 0),
    CONSTRAINT CK_RecurringPayments_Dates CHECK (EndDate IS NULL OR EndDate >= StartDate)
);

-- ============================================================
-- TABLE 6: Budgets
-- Purpose: Users set spending limits per category and time
-- period. The system compares actual spending vs. budget to
-- trigger alerts.
-- ============================================================
CREATE TABLE Budgets (
    BudgetID        INT             IDENTITY(1,1)   NOT NULL,
    UserID          INT             NOT NULL,
    CategoryID      INT             NOT NULL,
    BudgetAmount    DECIMAL(18,2)   NOT NULL,
    PeriodType      NVARCHAR(10)    NOT NULL,
    StartDate       DATE            NOT NULL,
    EndDate         DATE            NOT NULL,
    CreatedAt       DATETIME2       NOT NULL    DEFAULT GETDATE(),

    CONSTRAINT PK_Budgets PRIMARY KEY (BudgetID),
    CONSTRAINT FK_Budgets_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Budgets_Category FOREIGN KEY (CategoryID)
        REFERENCES Categories(CategoryID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_Budgets_Amount CHECK (BudgetAmount > 0),
    CONSTRAINT CK_Budgets_Period CHECK (PeriodType IN (N'Weekly', N'Monthly', N'Yearly')),
    CONSTRAINT CK_Budgets_Dates CHECK (EndDate >= StartDate)
);

-- ============================================================
-- TABLE 7: Alerts
-- Purpose: System-generated notifications for budget limits,
-- upcoming recurring payments, and spending anomalies. Links
-- optionally to a budget or recurring payment.
-- ============================================================

CREATE TABLE Alerts (
    AlertID             INT             IDENTITY(1,1)   NOT NULL,
    UserID              INT             NOT NULL,
    AlertType           NVARCHAR(30)    NOT NULL,
    Title               NVARCHAR(100)   NOT NULL,
    Message             NVARCHAR(500)   NOT NULL,
    IsRead              BIT             NOT NULL    DEFAULT 0,
    CreatedAt           DATETIME2       NOT NULL    DEFAULT GETDATE(),
    RelatedBudgetID     INT             NULL,
    RelatedRecurringPaymentID INT       NULL,

    CONSTRAINT PK_Alerts PRIMARY KEY (AlertID),
    CONSTRAINT FK_Alerts_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_Alerts_Budget FOREIGN KEY (RelatedBudgetID)
        REFERENCES Budgets(BudgetID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_Alerts_Recurring FOREIGN KEY (RelatedRecurringPaymentID)
        REFERENCES RecurringPayments(RecurringPaymentID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_Alerts_Type CHECK (AlertType IN (
        N'BudgetExceeded', N'BudgetWarning', N'UpcomingPayment',
        N'SpendingAnomaly', N'SystemNotification'))
);

-- ============================================================
-- TABLE 8: Scenarios
-- Purpose: Stores "What-if" simulation sessions. Each scenario
-- contains one or more hypothetical items to model future impact.
-- ============================================================
CREATE TABLE Scenarios (
    ScenarioID      INT             IDENTITY(1,1)   NOT NULL,
    UserID          INT             NOT NULL,
    ScenarioName    NVARCHAR(100)   NOT NULL,
    Description     NVARCHAR(500)   NULL,
    SimulationMonths INT            NOT NULL    DEFAULT 3,
    CreatedAt       DATETIME2       NOT NULL    DEFAULT GETDATE(),

    CONSTRAINT PK_Scenarios PRIMARY KEY (ScenarioID),
    CONSTRAINT FK_Scenarios_User FOREIGN KEY (UserID)
        REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT CK_Scenarios_Months CHECK (SimulationMonths BETWEEN 1 AND 60)
);

-- ============================================================
-- TABLE 9: ScenarioItems
-- Purpose: Individual hypothetical income/expense entries inside
-- a simulation scenario (e.g., "new gym membership $50/month").
-- ============================================================

CREATE TABLE ScenarioItems (
    ScenarioItemID  INT             IDENTITY(1,1)   NOT NULL,
    ScenarioID      INT             NOT NULL,
    CategoryID      INT             NULL,
    ItemDescription NVARCHAR(255)   NOT NULL,
    Amount          DECIMAL(18,2)   NOT NULL,
    TransactionType NVARCHAR(10)    NOT NULL,
    Frequency       NVARCHAR(20)    NOT NULL    DEFAULT N'Monthly',

    CONSTRAINT PK_ScenarioItems PRIMARY KEY (ScenarioItemID),
    CONSTRAINT FK_ScenarioItems_Scenario FOREIGN KEY (ScenarioID)
        REFERENCES Scenarios(ScenarioID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT FK_ScenarioItems_Category FOREIGN KEY (CategoryID)
        REFERENCES Categories(CategoryID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_ScenarioItems_Type CHECK (TransactionType IN (N'Income', N'Expense')),
    CONSTRAINT CK_ScenarioItems_Freq CHECK (Frequency IN (
        N'OneTime', N'Daily', N'Weekly', N'Monthly', N'Yearly')),
    CONSTRAINT CK_ScenarioItems_Amount CHECK (Amount > 0)
);

