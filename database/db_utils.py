"""SQLite 数据库工具函数。

这个文件把“连接数据库、建表、查询最新日期”这些通用动作集中起来。
SQLite 是一个本地文件型数据库，这里的数据库文件是 database/quant.db。
"""

# sqlite3 是 Python 标准库，自带，不需要额外安装。
import sqlite3

# Path 比普通字符串路径更稳，能方便地拼接目录、创建目录。
from pathlib import Path

# 数据库文件路径；Path("database/quant.db") 是相对项目根目录的路径。
DB_PATH = Path("database/quant.db")


def get_connection():

    # 如果 database 目录不存在，就先创建；exist_ok=True 表示已存在也不报错。
    DB_PATH.parent.mkdir(exist_ok=True)

    # 返回一个 SQLite 连接对象。后续读写数据库都要通过这个连接。
    return sqlite3.connect(DB_PATH)


def initialize_database():

    # 建立连接；SQLite 会在数据库文件不存在时自动创建文件。
    conn = get_connection()

    # cursor 可以理解为“数据库操作手柄”，用它执行 SQL 语句。
    cursor = conn.cursor()

    # CREATE TABLE IF NOT EXISTS：如果表不存在就创建，存在则什么也不做。
    # indicators 表用 (symbol, date) 做联合主键，保证同一只标的同一天只有一行指标。
    cursor.execute("""
                   
    CREATE TABLE IF NOT EXISTS indicators (
        symbol TEXT,
        date TEXT,

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

        PRIMARY KEY (symbol, date)
    )
    """)

    # commit 类似“保存修改”；对 CREATE/INSERT/UPDATE/DELETE 都很重要。
    conn.commit()

    # 用完连接后关闭，避免文件锁或资源占用。
    conn.close()

    print("数据库初始化完成")


def get_latest_date(symbol):

    conn = get_connection()

    cursor = conn.cursor()

    # ? 是 SQL 参数占位符；把 symbol 放在第二个参数里可以避免 SQL 注入问题。
    cursor.execute("""

    SELECT MAX(date)
    FROM price_data
    WHERE symbol = ?

    """, (symbol,))

    # fetchone 取回一行结果；这里结果形如 ("2024-01-01",)。
    result = cursor.fetchone()

    conn.close()

    # result[0] 取出 MAX(date) 的值；如果没有数据，通常会是 None。
    return result[0]
