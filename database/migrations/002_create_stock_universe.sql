-- Migration 002
-- 新增沪深 A 股股票池表。

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

CREATE INDEX IF NOT EXISTS idx_stock_universe_active_flags
ON stock_universe (
    is_active,
    is_st,
    is_delisting_risk
);
