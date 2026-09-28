"""数据湖访问层: DuckDB 连接 + 分层路径约定。

分层约定:
  lake/raw/    源数据原样落地(不可变): CSV / SQLite / Excel
  lake/clean/  清洗后 Parquet, 按表 + 日期分区, zstd 压缩
"""

from __future__ import annotations

import duckdb

from data_core.config import LakeConfig, load_settings

_settings = load_settings()


def lake_config() -> LakeConfig:
    return _settings.lake


def get_duckdb(lake: LakeConfig | None = None) -> duckdb.DuckDBPyConnection:
    """返回配置了 S3 凭据(如启用)的 DuckDB 连接。"""
    lake = lake or _settings.lake
    con = duckdb.connect()
    if lake.is_s3:
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute(f"SET s3_endpoint='{lake.s3_endpoint}'")
        con.execute(f"SET s3_region='{lake.s3_region or 'us-east-1'}'")
        con.execute(f"SET s3_access_key_id='{lake.s3_access_key}'")
        con.execute(f"SET s3_secret_access_key='{lake.s3_secret_key}'")
        con.execute("SET s3_url_style='path'")
    return con
