"""StarRocks 导入: 湖(clean Parquet on S3) -> 内表, 三步 schema/load/verify。

前提: DP_LAKE_ROOT=s3://bucket/prefix 且配置 AK/SK/ENDPOINT; StarRocks FE 可达。
本地 Demo(无集群/本地目录)不需要本步骤, API 自动用 DuckDB 直查湖。

用法:
  uv run sr-load --mode schema   # 执行 sql/starrocks_schema.sql
  uv run sr-load --mode load     # INSERT INTO ... SELECT FROM FILES(s3 parquet)
  uv run sr-load --mode verify   # 行数对账(湖 vs 仓)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymysql
from data_core.config import load_settings

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "sql" / "starrocks_schema.sql"


def _conn():
    sr = load_settings().starrocks
    return pymysql.connect(
        host=sr.host,
        port=sr.port,
        user=sr.user,
        password=sr.password,
        database=sr.database,
        connect_timeout=5,
        autocommit=True,
    )


def _s3_props() -> dict[str, str]:
    from data_core.config import load_settings

    lake = load_settings().lake
    if not lake.is_s3:
        raise SystemExit("DP_LAKE_ROOT 未指向 s3://; 本地目录模式无需导入 StarRocks")
    return {
        "aws.s3.endpoint": lake.s3_endpoint,
        "aws.s3.region": lake.s3_region or "us-east-1",
        "aws.s3.access_key": lake.s3_access_key,
        "aws.s3.secret_key": lake.s3_secret_key,
        "aws.s3.use_path_style": "true",
    }


def _files_props(path_glob: str) -> str:
    props = _s3_props()
    kv = ", ".join(f'"{k}"="{v}"' for k, v in props.items())
    return f'FROM FILES("path"="{path_glob}", "format"="parquet", {kv})'


def run_schema(conn: pymysql.connections.Connection) -> None:
    for stmt in SCHEMA_SQL.read_text().split(";"):
        if stmt.strip():
            conn.execute(stmt.strip())
            print(f"[sr] ok: {stmt.strip().splitlines()[0][:60]}...")


def run_load(conn: pymysql.connections.Connection) -> None:
    lake = load_settings().lake
    root = lake.root.rstrip("/")
    loads = {
        "device_readings": f"{root}/clean/sensors/*/*.parquet",
        "orders": f"{root}/clean/orders/*/*.parquet",
        "products": f"{root}/clean/products.parquet",
        "customers": f"{root}/clean/customers.parquet",
    }
    for table, glob in loads.items():
        print(f"[sr] loading {table} ...")
        conn.execute(f"INSERT INTO {table} SELECT * {_files_props(glob)}")


def run_verify(conn: pymysql.connections.Connection) -> None:
    import duckdb

    lake = load_settings().lake
    con = duckdb.connect()
    if lake.is_s3:
        con.execute("INSTALL httpfs; LOAD httpfs;")
    checks = {
        "device_readings": f"{lake.clean_dir}/sensors/**/*.parquet",
        "orders": f"{lake.clean_dir}/orders/**/*.parquet",
    }
    for table, glob in checks.items():
        if lake.is_s3:
            lake_cfg = load_settings().lake
            con.execute(f"SET s3_endpoint='{lake_cfg.s3_endpoint}'")
            con.execute(f"SET s3_region='{lake_cfg.s3_region or 'us-east-1'}'")
            con.execute(f"SET s3_access_key_id='{lake_cfg.s3_access_key}'")
            con.execute(f"SET s3_secret_access_key='{lake_cfg.s3_secret_key}'")
            con.execute("SET s3_url_style='path'")
        lake_n = con.execute(f"SELECT count(*) FROM read_parquet('{glob}')").fetchone()[0]
        sr_n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        status = "OK" if lake_n == sr_n else "MISMATCH"
        print(f"[sr] {table}: lake={lake_n:,} starrocks={sr_n:,} -> {status}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["schema", "load", "verify"], required=True)
    args = parser.parse_args()
    conn = _conn()
    try:
        {"schema": run_schema, "load": run_load, "verify": run_verify}[args.mode](conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
