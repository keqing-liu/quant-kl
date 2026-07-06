"""data_update_log 表写入。

这一层对应分层里的 repository：
只负责把更新结果记录到 SQLite，不判断一次更新应该算成功还是失败。
"""

from database.db_utils import get_connection


def log_price_update(
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
    """记录一次行情更新日志。"""

    conn = get_connection()
    try:
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
    finally:
        conn.close()
