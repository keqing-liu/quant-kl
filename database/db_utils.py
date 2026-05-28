"""SQLite 数据库工具函数。

这个文件把“连接数据库、建表、查询最新日期”这些通用动作集中起来。
SQLite 是一个本地文件型数据库，这里的数据库文件是 database/quant.db。
"""

import sqlite3
from pathlib import Path

# 数据库文件路径；Path("database/quant.db") 是相对项目根目录的路径。
DB_PATH = Path("database/quant.db")

# schema.sql 放在 database/ 目录下，集中管理建表语句。
SCHEMA_PATH = Path("database/schema.sql")

# 当前代码支持的数据库结构版本。
CURRENT_SCHEMA_VERSION = 1


def get_connection():
    """返回 SQLite 数据库连接。"""

    # 如果 database 目录不存在，就先创建；exist_ok=True 表示已存在也不报错。
    DB_PATH.parent.mkdir(exist_ok=True)

    # 返回一个 SQLite 连接对象。后续读写数据库都要通过这个连接。
    conn = sqlite3.connect(DB_PATH)

    # 开启外键约束。SQLite 默认不强制外键，需要显式打开。
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def initialize_database():
    """根据 schema.sql 初始化数据库表结构，并迁移旧数据库。"""

    # 建立连接；SQLite 会在数据库文件不存在时自动创建文件。
    conn = get_connection()

    try:
        # 如果 schema.sql 不存在，给出明确错误，方便排查项目结构问题。
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"找不到数据库结构文件: {SCHEMA_PATH}")

        # 在执行 schema.sql 之前先判断是否已有业务表。
        # 如果没有业务表，说明这是全新数据库，可以直接标记为当前版本。
        had_business_tables = _has_business_tables(conn)

        # 读取并执行 schema.sql 中的所有 SQL 语句。
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        if had_business_tables:
            _run_migrations(conn)
        else:
            _set_schema_version(conn, CURRENT_SCHEMA_VERSION)

        # commit 类似“保存修改”；对 CREATE/INSERT/UPDATE/DELETE 都很重要。
        conn.commit()

        print("数据库初始化完成")

    finally:
        # 用完连接后关闭，避免文件锁或资源占用。
        conn.close()


def _has_business_tables(conn):
    """判断数据库是否已经存在项目业务表。"""

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name IN (
              'price_data',
              'indicators',
              'asset_info',
              'data_update_log'
          )
        LIMIT 1
        """
    )

    return cursor.fetchone() is not None


def _get_schema_version(conn):
    """读取当前数据库结构版本；没有版本记录时返回 0。"""

    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()

    if result is None or result[0] is None:
        return 0

    return result[0]


def _set_schema_version(conn, version):
    """记录一个已经成功应用的数据库结构版本。"""

    conn.execute(
        """
        INSERT OR IGNORE INTO schema_version (version)
        VALUES (?)
        """,
        (version,),
    )


def _column_exists(conn, table_name, column_name):
    """检查指定表中是否已经存在某个字段。"""

    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")

    return any(row[1] == column_name for row in cursor.fetchall())


def _add_column_if_missing(conn, table_name, column_name, column_sql):
    """字段不存在时才执行 ALTER TABLE ADD COLUMN。"""

    if _column_exists(conn, table_name, column_name):
        return

    conn.execute(
        f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {column_sql}
        """
    )


def _backfill_timestamp_columns(conn, table_name):
    """为旧数据补齐 created_at / updated_at。"""

    conn.execute(
        f"""
        UPDATE {table_name}
        SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        """
    )


def _create_timestamp_insert_trigger(conn, table_name, trigger_name):
    """为旧表创建插入后自动补时间戳的触发器。"""

    conn.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS {trigger_name}
        AFTER INSERT ON {table_name}
        FOR EACH ROW
        WHEN NEW.created_at IS NULL OR NEW.updated_at IS NULL
        BEGIN
            UPDATE {table_name}
            SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE symbol = NEW.symbol
              AND date = NEW.date;
        END;
        """
    )


def _migrate_to_v1(conn):
    """迁移到 v1：为旧价格和指标表补时间戳字段。"""

    for table_name in ("price_data", "indicators"):
        _add_column_if_missing(conn, table_name, "created_at", "TEXT")
        _add_column_if_missing(conn, table_name, "updated_at", "TEXT")
        _backfill_timestamp_columns(conn, table_name)

    _create_timestamp_insert_trigger(
        conn,
        table_name="price_data",
        trigger_name="trg_price_data_fill_timestamps",
    )
    _create_timestamp_insert_trigger(
        conn,
        table_name="indicators",
        trigger_name="trg_indicators_fill_timestamps",
    )


def _run_migrations(conn):
    """按版本顺序执行未完成的数据库迁移。"""

    current_version = _get_schema_version(conn)

    if current_version < 1:
        _migrate_to_v1(conn)
        _set_schema_version(conn, 1)


def get_latest_date(symbol):
    """查询某个标的在 price_data 表中的最新日期。"""

    conn = get_connection()

    cursor = conn.cursor()

    # ? 是 SQL 参数占位符；把 symbol 放在第二个参数里可以避免 SQL 注入问题。
    cursor.execute(
        """
        SELECT MAX(date)
        FROM price_data
        WHERE symbol = ?
        """,
        (symbol,),
    )

    # fetchone 取回一行结果；这里结果形如 ("2024-01-01",)。
    result = cursor.fetchone()

    conn.close()

    # result[0] 取出 MAX(date) 的值；如果没有数据，通常会是 None。
    return result[0]


def log_data_update(
    symbol,
    asset_type=None,
    latest_date_before=None,
    start_date=None,
    end_date=None,
    rows_downloaded=0,
    rows_inserted=0,
    status="unknown",
    message=None,
    data_source=None,
):
    """记录一次数据更新日志。"""

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO data_update_log (
        symbol,
        asset_type,
        latest_date_before,
        start_date,
        end_date,
        rows_downloaded,
        rows_inserted,
        status,
        message,
        data_source
    )
    VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    )
    """

    cursor.execute(
        sql,
        (
            symbol,
            asset_type,
            latest_date_before,
            start_date,
            end_date,
            rows_downloaded,
            rows_inserted,
            status,
            message,
            data_source,
        ),
    )

    conn.commit()
    conn.close()
