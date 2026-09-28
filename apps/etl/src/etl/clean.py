"""清洗管线: lake/raw -> lake/clean (Parquet, 按日期分区, zstd)。

规则与产出报告:
  sensors:
    - 电压物理量程 [11.5, 12.8] 之外 -> 置 NULL (clamped_v 裁剪计数)
    - 温度缺失 -> 同设备前值填充 (forward fill)
    - (device_id, ts) 重复 -> 保留最后一条
  orders:
    - order_id 重复 -> 保留 ts 最新
    - amount > 10000 视为"分"误记 -> /100 单位统一 (unit_fixed 计数)
    - qty <= 0 -> 剔除
  master/customers/products: 原样 Parquet 化
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl
from data_core.lake import get_duckdb, lake_config


def _reset_dir(path: str) -> None:
    """COPY TO 分区目录不支持覆盖, 运行前清空重建。"""
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def clean_sensors(con: duckdb.DuckDBPyConnection, raw: Path, clean: Path) -> None:
    csv_glob = f"{raw}/sensors/device_readings_*.csv"
    stats = con.execute(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE voltage_v < 11.5 OR voltage_v > 12.8) AS v_out_of_range,
               count(*) FILTER (WHERE temp_c IS NULL) AS temp_missing,
               count(*) - count(DISTINCT (device_id, ts)) AS dup_rows
        FROM read_csv(?, header=true)""",
        [csv_glob],
    ).fetchone()
    out = f"{clean}/sensors"
    _reset_dir(out)
    con.execute(
        f"CREATE OR REPLACE TABLE _stg_sensors AS SELECT * FROM read_csv('{csv_glob}', header=true)"
    )
    con.execute(
        f"""
        COPY (
            SELECT
                device_id, ts,
                coalesce(
                    temp_c,
                    last_value(temp_c IGNORE NULLS) OVER (
                        PARTITION BY device_id ORDER BY ts
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ),
                ) AS temp_c,
                humidity_pct,
                CASE WHEN voltage_v BETWEEN 11.5 AND 12.8 THEN voltage_v END AS voltage_v,
                current_a, status,
                strftime(ts, '%Y-%m-%d') AS read_date
            FROM (SELECT *, row_number() OVER (PARTITION BY device_id, ts ORDER BY ts) AS rn
                  FROM _stg_sensors)
            WHERE rn = 1
        ) TO '{out}' (FORMAT PARQUET, PARTITION_BY (read_date), COMPRESSION ZSTD)
        """
    )
    print(
        f"[clean] sensors: in={stats[0]:,} voltage_clamped={stats[1]:,} "
        f"temp_filled={stats[2]:,} deduped={stats[3]:,}"
    )
    con.execute("DROP TABLE _stg_sensors")


def clean_orders(con: duckdb.DuckDBPyConnection, raw: Path, clean: Path) -> None:
    db = f"{raw}/orders.db"
    con.execute("INSTALL sqlite; LOAD sqlite;")
    con.execute(f"ATTACH '{db}' AS src (TYPE SQLITE)")
    stats = con.execute(
        """
        SELECT count(*),
               count(*) FILTER (WHERE amount > 10000),
               count(*) FILTER (WHERE qty <= 0),
               count(*) - count(DISTINCT order_id)
        FROM src.orders"""
    ).fetchone()
    out = f"{clean}/orders"
    _reset_dir(out)
    con.execute(
        f"""
        COPY (
            SELECT order_id, ts::TIMESTAMP AS ts, customer_id, product_id, qty,
                   CASE WHEN amount > 10000 THEN round(amount / 100.0, 2) ELSE amount END AS amount,
                   channel, strftime(ts::TIMESTAMP, '%Y-%m-%d') AS order_date
            FROM (SELECT *, row_number() OVER (PARTITION BY order_id ORDER BY ts DESC) AS rn
                  FROM src.orders)
            WHERE rn = 1 AND qty > 0
        ) TO '{out}' (FORMAT PARQUET, PARTITION_BY (order_date), COMPRESSION ZSTD)
        """
    )
    # 维表 Parquet 化
    for table in ("customers", "products"):
        con.execute(
            f"COPY (SELECT * FROM src.{table}) TO '{clean}/{table}.parquet' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    con.execute("DETACH src")
    print(
        f"[clean] orders: in={stats[0]:,} unit_fixed={stats[1]:,} "
        f"invalid_qty_removed={stats[2]:,} deduped={stats[3]:,}"
    )


def clean_master(con: duckdb.DuckDBPyConnection, raw: Path, clean: Path) -> None:
    xlsx = f"{raw}/master/equipment_master.xlsx"
    df = pl.read_excel(xlsx)
    con.register("_master", df.to_pandas())
    con.execute(
        f"COPY (SELECT * FROM _master) TO '{clean}/equipment_master.parquet' "
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    con.unregister("_master")
    print(f"[clean] master: {df.height} rows")


def main() -> None:
    lake = lake_config()
    raw, clean = Path(lake.raw_dir), Path(lake.clean_dir)
    clean.mkdir(parents=True, exist_ok=True)
    con = get_duckdb()
    print(f"[clean] raw={raw} -> clean={clean}")
    clean_sensors(con, raw, clean)
    clean_orders(con, raw, clean)
    clean_master(con, raw, clean)
    con.close()
    print("[clean] done")


if __name__ == "__main__":
    main()
