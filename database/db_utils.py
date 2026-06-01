"""SQLite 数据库工具函数。

这个文件把“连接数据库、建表、查询最新日期”这些通用动作集中起来。
SQLite 是一个本地文件型数据库，这里的数据库文件是 database/quant.db。
"""

import sqlite3
from pathlib import Path

# 所有数据库相关文件都基于当前文件位置推导，避免依赖运行命令时的工作目录。
DATABASE_DIR = Path(__file__).resolve().parent
DB_PATH = DATABASE_DIR / "quant.db"

# 这里刻意把“完整 schema”和“增量 migration”拆开：
# 1. base.sql: 新建数据库时，一次性创建当前最新版表结构。
# 2. migrations/: 已有旧数据库时，按 schema_version 一步步升级。
BASE_SCHEMA_PATH = DATABASE_DIR / "schema" / "base.sql"
MIGRATIONS_DIR = DATABASE_DIR / "migrations"

# 当前代码支持的数据库结构版本。
# 后续每新增一个 migration 文件，都要同步递增这个版本号。
CURRENT_SCHEMA_VERSION = 5


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
    """初始化数据库表结构，并对旧数据库执行未完成迁移。"""

    # 建立连接；SQLite 会在数据库文件不存在时自动创建文件。
    conn = get_connection()

    try:
        # 如果 base.sql 不存在，给出明确错误，方便排查项目结构问题。
        if not BASE_SCHEMA_PATH.exists():
            raise FileNotFoundError(f"找不到数据库结构文件: {BASE_SCHEMA_PATH}")

        # 在执行 base.sql 之前先判断是否已有业务表。
        # 如果没有业务表，说明这是全新数据库，可以直接标记为当前版本。
        had_business_tables = _has_business_tables(conn)

        if had_business_tables:
            # 旧库不能直接依赖 base.sql 升级：
            # CREATE TABLE IF NOT EXISTS 不会修改已有表字段，
            # 而 CREATE INDEX 还可能引用旧表中不存在的新字段。
            # 所以先跑 migrations，把旧表改到最新结构。
            _run_migrations(conn)
            # migrations 负责把旧表结构推进到当前版本；
            # base.sql 再补齐缺失的新表或索引。
            _run_sql_file(conn, BASE_SCHEMA_PATH)
        else:
            # base.sql 始终保持“当前最新版完整结构”。
            _run_sql_file(conn, BASE_SCHEMA_PATH)
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
              'data_update_log',
              'stock_universe',
              'financial_indicators'
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


def _run_sql_file(conn, sql_path):
    """读取并执行一个 SQL 文件。"""

    if not sql_path.exists():
        raise FileNotFoundError(f"找不到数据库迁移文件: {sql_path}")

    sql = sql_path.read_text(encoding="utf-8")
    conn.executescript(sql)


def _migration_path(version):
    """根据版本号查找对应迁移文件。"""

    # 文件名采用 001_xxx.sql、002_xxx.sql 这种格式。
    # 这样一眼能看出执行顺序，也方便按版本号查找。
    pattern = f"{version:03d}_*.sql"
    matches = sorted(MIGRATIONS_DIR.glob(pattern))

    if not matches:
        raise FileNotFoundError(
            f"找不到 v{version} 数据库迁移文件: {MIGRATIONS_DIR / pattern}"
        )

    if len(matches) > 1:
        raise RuntimeError(f"v{version} 数据库迁移文件不唯一: {matches}")

    return matches[0]


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


def _drop_column_if_exists(conn, table_name, column_name):
    """字段存在时才执行 ALTER TABLE DROP COLUMN。"""

    if not _column_exists(conn, table_name, column_name):
        return

    conn.execute(
        f"""
        ALTER TABLE {table_name}
        DROP COLUMN {column_name}
        """
    )


def _migrate_to_v1(conn):
    """迁移到 v1：为旧价格和指标表补时间戳字段。"""

    # SQLite 对 ADD COLUMN IF NOT EXISTS 的支持不稳定，
    # 因此字段存在性检查放在 Python 里做。
    for table_name in ("price_data", "indicators"):
        _add_column_if_missing(conn, table_name, "created_at", "TEXT")
        _add_column_if_missing(conn, table_name, "updated_at", "TEXT")
    _run_sql_file(conn, _migration_path(1))


def _migrate_to_v2(conn):
    """迁移到 v2：新增 stock_universe 全市场股票池表。"""

    _run_sql_file(conn, _migration_path(2))


def _migrate_to_v3(conn):
    """迁移到 v3：新增 financial_indicators 财务指标表。"""

    _run_sql_file(conn, _migration_path(3))


def _migrate_to_v4(conn):
    """迁移到 v4：保留历史版本号占位。"""

    # v4 曾用于 fixed_asset_ratio 字段；该字段因为上游数据缺失较多已移除。
    # 保留这个 no-op 版本，可以让已经记录到 v4 的旧数据库继续平滑升级到 v5。
    _run_sql_file(conn, _migration_path(4))


def _migrate_to_v5(conn):
    """迁移到 v5：移除财务指标表中的固定资产比重字段。"""

    _drop_column_if_exists(
        conn,
        table_name="financial_indicators",
        column_name="fixed_asset_ratio",
    )
    _run_sql_file(conn, _migration_path(5))


def _run_migrations(conn):
    """按版本顺序执行未完成的数据库迁移。"""

    # 注意 current_version 在函数开头读取一次即可。
    # 后续每完成一个版本就写入 schema_version；
    # if 判断仍然基于原始版本，正好可以从旧版本一路跑到最新版本。
    current_version = _get_schema_version(conn)

    if current_version < 1:
        _migrate_to_v1(conn)
        _set_schema_version(conn, 1)

    if current_version < 2:
        _migrate_to_v2(conn)
        _set_schema_version(conn, 2)

    if current_version < 3:
        _migrate_to_v3(conn)
        _set_schema_version(conn, 3)

    if current_version < 4:
        _migrate_to_v4(conn)
        _set_schema_version(conn, 4)

    if current_version < 5:
        _migrate_to_v5(conn)
        _set_schema_version(conn, 5)


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
