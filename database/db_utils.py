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
    """根据 schema.sql 初始化数据库表结构。"""

    # 建立连接；SQLite 会在数据库文件不存在时自动创建文件。
    conn = get_connection()

    try:
        # 如果 schema.sql 不存在，给出明确错误，方便排查项目结构问题。
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"找不到数据库结构文件: {SCHEMA_PATH}")

        # 读取并执行 schema.sql 中的所有 SQL 语句。
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        # commit 类似“保存修改”；对 CREATE/INSERT/UPDATE/DELETE 都很重要。
        conn.commit()

        print("数据库初始化完成")

    finally:
        # 用完连接后关闭，避免文件锁或资源占用。
        conn.close()


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
