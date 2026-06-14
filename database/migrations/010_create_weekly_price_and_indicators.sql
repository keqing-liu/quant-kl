-- 新增由日线聚合生成的周线行情表，以及基于周线行情计算的技术指标表。

CREATE TABLE IF NOT EXISTS weekly_price_data (
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

CREATE INDEX IF NOT EXISTS idx_weekly_price_data_symbol_date
ON weekly_price_data (symbol, date);


CREATE TABLE IF NOT EXISTS weekly_indicators (
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
        REFERENCES weekly_price_data (symbol, date)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_weekly_indicators_symbol_date
ON weekly_indicators (symbol, date);
