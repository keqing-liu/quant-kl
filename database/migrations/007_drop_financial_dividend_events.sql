-- Migration 007
-- 暂停巨潮分红事件下载，删除此前创建的 financial_dividend_events 表。

DROP TABLE IF EXISTS financial_dividend_events;
