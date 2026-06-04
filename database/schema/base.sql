-- database/schema/base.sql
-- Quant-KL SQLite database schema
-- 作用：为全新数据库一次性创建当前最新版表结构。
-- 旧数据库的增量变更放在 database/migrations/ 目录。
--
-- 维护规则：
-- 1. 这个文件代表“新建数据库时应该长什么样”。
-- 2. 已经存在的旧数据库不会因为 CREATE TABLE IF NOT EXISTS 自动新增/删除字段。
-- 3. 因此每次改表结构时，除了更新本文件，还要新增 migration 文件。

PRAGMA foreign_keys = ON;

-- =========================================================
-- 1. 原始行情数据表
-- =========================================================
CREATE TABLE IF NOT EXISTS price_data (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,

    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_price_data_symbol_date
ON price_data (symbol, date);


-- =========================================================
-- 2. 技术指标数据表
-- =========================================================
CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,

    MA20 REAL,
    MA50 REAL,
    MA60 REAL,
    RETURN REAL,

    VOLATILITY20 REAL,
    VOLATILITY252 REAL,

    STD20 REAL,
    BOLL_UPPER REAL,
    BOLL_LOWER REAL,

    VOL5 REAL,
    VOL20 REAL,

    RSV REAL,
    K REAL,
    D REAL,
    J REAL,

    CCI REAL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, date),

    FOREIGN KEY (symbol, date)
        REFERENCES price_data (symbol, date)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_indicators_symbol_date
ON indicators (symbol, date);


-- =========================================================
-- 3. 资产信息表
-- =========================================================
CREATE TABLE IF NOT EXISTS asset_info (
    symbol TEXT PRIMARY KEY,

    name TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    asset_class TEXT,
    market TEXT,
    data_source TEXT,

    benchmark_symbol TEXT,
    benchmark_name TEXT,

    is_active INTEGER DEFAULT 1,

    note TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 4. 全市场股票池表
-- =========================================================
CREATE TABLE IF NOT EXISTS stock_universe (
    symbol TEXT PRIMARY KEY,
    stock_code TEXT NOT NULL,
    name TEXT NOT NULL,

    exchange TEXT,
    market TEXT DEFAULT 'CN',

    is_active INTEGER DEFAULT 1,
    is_st INTEGER DEFAULT 0,
    is_delisting_risk INTEGER DEFAULT 0,

    list_date TEXT,
    delist_date TEXT,

    data_source TEXT,
    note TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 财报下载前会从 stock_universe 里筛选：
-- 仍在交易、非 ST、无明显退市风险的股票。
CREATE INDEX IF NOT EXISTS idx_stock_universe_active_flags
ON stock_universe (
    is_active,
    is_st,
    is_delisting_risk
);


-- =========================================================
-- 5. 美国上市公司 SEC 映射表
-- =========================================================
CREATE TABLE IF NOT EXISTS us_company_map (
    symbol TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    cik TEXT NOT NULL,
    name TEXT,
    exchange TEXT,
    is_active INTEGER DEFAULT 1,
    data_source TEXT,
    note TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_us_company_map_ticker
ON us_company_map (ticker);

CREATE INDEX IF NOT EXISTS idx_us_company_map_cik
ON us_company_map (cik);


-- =========================================================
-- 6. 财务指标数据表
-- =========================================================
CREATE TABLE IF NOT EXISTS financial_indicators (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,

    announce_date TEXT,
    period_type TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,

    roe REAL,
    weighted_roe REAL,
    roa REAL,
    revenue REAL,
    revenue_yoy REAL,
    net_profit REAL,
    net_profit_yoy REAL,
    deducted_net_profit REAL,
    gross_margin REAL,
    operating_margin REAL,
    net_margin REAL,
    cost_expense_margin REAL,
    main_profit_ratio REAL,
    non_main_ratio REAL,
    debt_ratio REAL,
    equity_ratio REAL,
    current_ratio REAL,
    quick_ratio REAL,
    cash_ratio REAL,
    interest_coverage REAL,
    receivable_turnover REAL,
    receivable_days REAL,
    inventory_turnover REAL,
    inventory_days REAL,
    total_asset_turnover REAL,
    fixed_asset_ratio REAL,
    ocf_to_revenue REAL,
    ocf_to_net_profit REAL,
    ocf_to_debt REAL,
    cash_flow_ratio REAL,
    operating_cash_flow REAL,
    operating_cash_flow_per_share REAL,
    book_value_per_share REAL,
    eps REAL,

    data_source TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, report_date)
);

CREATE INDEX IF NOT EXISTS idx_financial_indicators_symbol_report_date
ON financial_indicators (symbol, report_date);

-- announce_date 当前多数记录为空，但先保留索引位。
-- 后续补公告日后，历史回测应按 announce_date 判断财报是否已经可见。
CREATE INDEX IF NOT EXISTS idx_financial_indicators_announce_date
ON financial_indicators (announce_date);


-- =========================================================
-- 7. 财务报表明细窄表
-- =========================================================
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


-- =========================================================
-- 8. 巴菲特框架衍生指标
-- =========================================================
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


-- =========================================================
-- =========================================================
-- 9. 数据更新日志表
-- =========================================================
CREATE TABLE IF NOT EXISTS data_update_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    symbol TEXT NOT NULL,
    asset_type TEXT,

    update_time TEXT DEFAULT CURRENT_TIMESTAMP,

    latest_date_before TEXT,
    start_date TEXT,
    end_date TEXT,

    rows_downloaded INTEGER DEFAULT 0,
    rows_inserted INTEGER DEFAULT 0,

    status TEXT NOT NULL,
    message TEXT,

    data_source TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);


-- =========================================================
-- 10. 数据库结构版本表
-- =========================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);
