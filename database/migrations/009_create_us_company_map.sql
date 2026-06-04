-- Migration 009
-- 新增美国上市公司 ticker/CIK 映射表。

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
