-- Migration 003
-- 新增股票财务指标表。
--
-- 注意：这里保存的是“报告期 report_date”，不是严格意义上的“公告可见日”。
-- 后续如果接入公告日数据，应补齐 announce_date 并在回测中优先使用公告日。

CREATE TABLE IF NOT EXISTS financial_indicators (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,

    announce_date TEXT,
    period_type TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,

    roe REAL,
    revenue REAL,
    revenue_yoy REAL,
    net_profit REAL,
    net_profit_yoy REAL,
    gross_margin REAL,
    debt_ratio REAL,
    operating_cash_flow REAL,
    eps REAL,

    data_source TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (symbol, report_date)
);

CREATE INDEX IF NOT EXISTS idx_financial_indicators_symbol_report_date
ON financial_indicators (symbol, report_date);

CREATE INDEX IF NOT EXISTS idx_financial_indicators_announce_date
ON financial_indicators (announce_date);
