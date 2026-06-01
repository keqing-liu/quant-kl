-- Migration 001
-- 为旧版 price_data / indicators 补齐 created_at、updated_at，并添加插入触发器。
-- 字段添加本身由 db_utils.py 做存在性检查，避免 SQLite 重复 ADD COLUMN 报错。

UPDATE price_data
SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP);

UPDATE indicators
SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP);

CREATE TRIGGER IF NOT EXISTS trg_price_data_fill_timestamps
AFTER INSERT ON price_data
FOR EACH ROW
WHEN NEW.created_at IS NULL OR NEW.updated_at IS NULL
BEGIN
    UPDATE price_data
    SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
        updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
    WHERE symbol = NEW.symbol
      AND date = NEW.date;
END;

CREATE TRIGGER IF NOT EXISTS trg_indicators_fill_timestamps
AFTER INSERT ON indicators
FOR EACH ROW
WHEN NEW.created_at IS NULL OR NEW.updated_at IS NULL
BEGIN
    UPDATE indicators
    SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
        updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
    WHERE symbol = NEW.symbol
      AND date = NEW.date;
END;
