"""双引擎 SQL: 同一业务查询在 DuckDB(湖) 与 StarRocks(仓) 下的两份方言。

表名映射:
  DuckDB(Parquet hive 分区)              StarRocks(内表, 由 scripts/load_starrocks.py 导入)
  lake/clean/sensors/**/*.parquet   ->   device_readings
  lake/clean/orders/**/*.parquet    ->   orders
  lake/clean/products.parquet       ->   products
"""

from __future__ import annotations

from data_core.engine import EngineName
from data_core.lake import lake_config

lake = lake_config()


def daily_orders(engine: EngineName, days: int) -> str:
    if engine == "starrocks":
        return f"""
        SELECT date_trunc('day', ts) AS date, count(*) AS orders, sum(amount) AS revenue
        FROM orders
        GROUP BY 1 ORDER BY 1 DESC LIMIT {days}
        """
    return f"""
    SELECT CAST(ts AS DATE) AS date, count(*) AS orders, sum(amount) AS revenue
    FROM read_parquet('{lake.clean_dir}/orders/**/*.parquet', hive_partitioning=true)
    GROUP BY 1 ORDER BY 1 DESC LIMIT {days}
    """


def category_revenue(engine: EngineName, days: int) -> str:
    if engine == "starrocks":
        return f"""
        SELECT p.category AS category, sum(o.amount) AS revenue, count(*) AS orders
        FROM orders o JOIN products p USING (product_id)
        WHERE o.ts >= date_sub(NOW(), INTERVAL '{days}' DAY)
        GROUP BY 1 ORDER BY 2 DESC
        """
    return f"""
    SELECT p.category AS category, sum(o.amount) AS revenue, count(*) AS orders
    FROM read_parquet('{lake.clean_dir}/orders/**/*.parquet', hive_partitioning=true) o
    JOIN read_parquet('{lake.clean_dir}/products.parquet') p USING (product_id)
    WHERE o.ts >= CURRENT_DATE - INTERVAL '{days}' DAY
    GROUP BY 1 ORDER BY 2 DESC
    """


def sensor_summary(engine: EngineName) -> str:
    if engine == "starrocks":
        return """
        SELECT count(DISTINCT device_id) AS total_devices,
               avg(CASE WHEN status = 'online' THEN 1.0 ELSE 0.0 END) AS online_ratio,
               count(*) AS total_readings
        FROM device_readings
        """
    return f"""
    SELECT count(DISTINCT device_id) AS total_devices,
           avg(CASE WHEN status = 'online' THEN 1.0 ELSE 0.0 END) AS online_ratio,
           count(*) AS total_readings
    FROM read_parquet('{lake.clean_dir}/sensors/**/*.parquet', hive_partitioning=true)
    """


def sensor_series(engine: EngineName, device: str, date_from: str, date_to: str) -> str:
    if engine == "starrocks":
        return f"""
        SELECT date_trunc('hour', ts) AS ts,
               avg(temp_c) AS temp_avg, min(temp_c) AS temp_min, max(temp_c) AS temp_max,
               avg(voltage_v) AS voltage_avg
        FROM device_readings
        WHERE device_id = '{device}' AND ts BETWEEN '{date_from}' AND '{date_to}'
        GROUP BY 1 ORDER BY 1
        """
    return f"""
    SELECT date_trunc('hour', ts) AS ts,
           avg(temp_c) AS temp_avg, min(temp_c) AS temp_min, max(temp_c) AS temp_max,
           avg(voltage_v) AS voltage_avg
    FROM read_parquet('{lake.clean_dir}/sensors/**/*.parquet', hive_partitioning=true)
    WHERE device_id = '{device}' AND ts BETWEEN '{date_from}' AND '{date_to}'
    GROUP BY 1 ORDER BY 1
    """


def sensor_anomalies(engine: EngineName, z_threshold: float = 2.0) -> str:
    """设备内日均值温度 z-score: |z| 超阈值且绝对偏离 > 0.5C(工程阈值)。
    双条件避免极小方差放大噪声残余; 可发现 D-07 第 100~120 天 +3C 漂移。"""
    if engine == "starrocks":
        return f"""
        WITH daily AS (
            SELECT device_id, date_trunc('day', ts) AS date, avg(temp_c) AS temp_avg
            FROM device_readings GROUP BY 1, 2
        ), scored AS (
            SELECT device_id, date, temp_avg,
                   (temp_avg - avg(temp_avg) OVER w) / stddev_samp(temp_avg) OVER w AS z,
                   abs(temp_avg - avg(temp_avg) OVER w) AS dev
            FROM daily WINDOW w AS (PARTITION BY device_id)
        )
        SELECT device_id, date, round(temp_avg, 2) AS temp_avg, round(z, 2) AS z
        FROM scored WHERE abs(z) > {z_threshold} AND dev > 0.5 ORDER BY device_id, date
        """
    return f"""
    WITH daily AS (
        SELECT device_id, CAST(ts AS DATE) AS date, avg(temp_c) AS temp_avg
        FROM read_parquet('{lake.clean_dir}/sensors/**/*.parquet', hive_partitioning=true)
        GROUP BY 1, 2
    ), scored AS (
        SELECT device_id, date, temp_avg,
               (temp_avg - avg(temp_avg) OVER w) / stddev_samp(temp_avg) OVER w AS z,
               abs(temp_avg - avg(temp_avg) OVER w) AS dev
        FROM daily WINDOW w AS (PARTITION BY device_id)
    )
    SELECT device_id, date, round(temp_avg, 2) AS temp_avg, round(z, 2) AS z
    FROM scored WHERE abs(z) > {z_threshold} AND dev > 0.5 ORDER BY device_id, date
    """
