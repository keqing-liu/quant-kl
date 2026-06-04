-- Migration 006
-- 扩展财务数据结构，支持新浪三大报和巴菲特式衍生指标。

CREATE TABLE IF NOT EXISTS financial_statement_items (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,
    statement_type TEXT NOT NULL,
    item_name TEXT NOT NULL,

    announce_date TEXT,
    item_value REAL,
    currency TEXT,
    report_type TEXT,
    is_audited TEXT,
    data_source TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, report_date, statement_type, item_name)
);

CREATE INDEX IF NOT EXISTS idx_financial_statement_items_symbol_report_date
ON financial_statement_items (symbol, report_date);

CREATE INDEX IF NOT EXISTS idx_financial_statement_items_announce_date
ON financial_statement_items (announce_date);

CREATE TABLE IF NOT EXISTS buffett_metrics (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,

    announce_date TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,

    revenue REAL,
    net_profit REAL,
    operating_cash_flow REAL,
    capital_expenditure REAL,
    depreciation_amortization REAL,
    free_cash_flow REAL,
    free_cash_flow_margin REAL,
    market_cap REAL,
    free_cash_flow_yield REAL,
    cfo_to_net_profit REAL,
    cfo_to_revenue REAL,
    capex_to_cfo REAL,
    capex_to_depreciation REAL,
    owner_earnings_approx REAL,
    nopat REAL,
    invested_capital REAL,
    roic REAL,
    net_debt REAL,
    net_debt_ratio REAL,
    interest_coverage REAL,
    goodwill_to_equity REAL,
    receivable_to_revenue REAL,
    inventory_to_revenue REAL,
    working_capital REAL,
    working_capital_change REAL,
    data_source TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, report_date)
);

CREATE INDEX IF NOT EXISTS idx_buffett_metrics_symbol_report_date
ON buffett_metrics (symbol, report_date);
