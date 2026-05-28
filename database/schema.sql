-- database/schema.sql
-- Quant-KL SQLite database schema
-- 作用：统一创建项目所需的数据表，避免 price_data 表依赖手动创建。
-- 使用方式：由 database/db_utils.py 中的 initialize_database() 读取并执行。

PRAGMA foreign_keys = ON;

-- =========================================================
-- 1. 原始行情数据表
-- =========================================================
-- 每一行代表一个标的在一个交易日的 OHLCV 数据。
-- PRIMARY KEY (symbol, date) 保证同一标的同一日期只能有一条记录，
-- 避免重复下载或重复写入造成指标和回测失真。
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

-- 按 symbol 和 date 查询是最常见操作，例如：
-- 1. 查询某只 ETF 的历史行情；
-- 2. 查询最新日期；
-- 3. 计算指标和回测。
-- 复合主键本身已经建立索引，但这里保留显式索引，便于阅读和扩展。
CREATE INDEX IF NOT EXISTS idx_price_data_symbol_date
ON price_data (symbol, date);


-- =========================================================
-- 2. 技术指标数据表
-- =========================================================
-- 字段名称保持与你当前 db_utils.py 里的 indicators 表一致，
-- 避免影响 analysis/indicators.py、summary.py、scoring2.py 等已有模块。
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

    -- 如果某个交易日没有 price_data，也允许先写 indicators 失败，
    -- 这样可以帮助发现数据流程问题。
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
-- 4. 数据更新日志表
-- =========================================================
-- 每一行记录一次 symbol 的数据更新结果。
-- 用于追踪哪些标的更新成功、失败、返回空数据、没有新增数据等。

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