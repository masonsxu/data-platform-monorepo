"""合成混合源数据(通用 IoT + 订单域, 无真实业务含义)。

规模目标 raw 层约 1GB:
  lake/raw/sensors/device_readings_*.csv   30 设备 x 180 天 x 1 分钟 ≈ 778 万行
  lake/raw/orders.db (SQLite)              120 天订单 ≈ 96 万行 + 客户/产品维表
  lake/raw/master/equipment_master.xlsx    设备台账 30 行

锚定日期 2025-01-01, 保证 demo 可复现。

注入的"待清洗/待发现"模式:
  - 电压偶发越限(<11.5V 或 >12.8V, 物理量程外) -> 清洗裁剪演示
  - 设备 D-07 第 100~120 天温度基线 +3 度 -> 时序分析/异常检测可发现
  - 10% 订单金额单位误记为"分" -> 单位统一清洗演示
  - 0.1% 订单号重复 -> 去重演示
  - 传感器温度随机缺失段 -> 缺失值策略演示
  - 订单周末峰值 + 缓慢增长 + 促销日尖峰 -> 预测模型可学习
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
from data_core.lake import lake_config

ANCHOR = datetime(2025, 1, 1)
N_DEVICES = 48
SENSOR_DAYS = 180
ORDER_DAYS = 120
BASE_ORDERS_PER_DAY = 8000

rng = np.random.default_rng(42)


def device_ids() -> list[str]:
    return [f"D-{i:02d}" for i in range(1, N_DEVICES + 1)]


def gen_sensors(raw_dir: Path) -> None:
    """按 30 天分块生成写 CSV, 控制单块内存 ~130MB。"""
    out_dir = raw_dir / "sensors"
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = device_ids()
    drift_devices = {"D-07": (100, 120, 3.0)}  # 第100~120天基线+3度

    # 设备基线全程固定(物理直觉), 日周期相位固定
    base = rng.uniform(20, 28, N_DEVICES)
    day_frac = (np.arange(1440)) / 1440.0
    diurnal_day = np.sin(2 * np.pi * day_frac - np.pi / 2) * 2.0  # 夜低昼高
    diurnal_block = np.tile(diurnal_day, 30)  # 30 天 x 1440 分钟

    for chunk_idx in range(SENSOR_DAYS // 30):
        start = ANCHOR + timedelta(days=30 * chunk_idx)
        minutes = 30 * 24 * 60
        rows_per_chunk = minutes * N_DEVICES  # 129.6 万行/块

        ts = np.datetime64(start) + np.arange(minutes).astype("timedelta64[m]")
        ts_all = np.tile(ts, N_DEVICES)
        dev_all = np.repeat(np.array(ids), minutes)

        # 每设备独立温度基线 20~28 度, 日周期 +-2 度, 噪声 0.3
        temp = (
            np.repeat(base, minutes)
            + np.tile(diurnal_block, N_DEVICES)
            + rng.normal(0, 0.3, rows_per_chunk)
        )
        # 注入漂移
        day_offset = np.tile(np.arange(minutes) // 1440, N_DEVICES) + 30 * chunk_idx
        for dev, (d0, d1, delta) in drift_devices.items():
            mask = (dev_all == dev) & (day_offset >= d0) & (day_offset <= d1)
            temp[mask] += delta
        # 温度缺失段: 每块每设备随机 0~3 段、每段 10~60 分钟
        miss = rng.random(rows_per_chunk) < 0.002
        temp[miss] = np.nan

        humidity = np.clip(rng.normal(45, 8, rows_per_chunk) - 0.5 * (temp - 24), 10, 90)
        voltage = rng.normal(12.0, 0.15, rows_per_chunk)
        # 注入越限电压 ~0.05%
        spike = rng.random(rows_per_chunk) < 0.0005
        voltage[spike] = rng.uniform(10.8, 14.2, spike.sum())
        current = np.clip(rng.normal(1.8, 0.4, rows_per_chunk), 0, None)
        status = np.where(rng.random(rows_per_chunk) < 0.995, "online", "offline")

        df = pl.DataFrame(
            {
                "ts": ts_all,
                "device_id": dev_all,
                "temp_c": temp,
                "humidity_pct": np.round(humidity, 1),
                "voltage_v": np.round(voltage, 2),
                "current_a": np.round(current, 2),
                "status": status,
            }
        ).with_columns(pl.col("temp_c").fill_nan(None))  # NaN -> null, CSV 写空字段
        path = out_dir / f"device_readings_{chunk_idx:02d}.csv"
        df.write_csv(path)
        print(f"  wrote {path.name}: {df.height:,} rows")
        del df, temp, humidity, voltage, current


def gen_orders(raw_dir: Path) -> None:
    db_path = raw_dir / "orders.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY, name TEXT, tier TEXT, city TEXT);
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, unit_price REAL);
        CREATE TABLE orders (
            order_id TEXT, ts TEXT, customer_id INTEGER, product_id INTEGER,
            qty INTEGER, amount REAL, channel TEXT);
        CREATE INDEX idx_orders_ts ON orders(ts);
        """
    )
    # 维表
    cities = ["SZ", "SH", "BJ", "HZ", "CD", "WH", "XA", "NJ"]
    tiers = ["free", "basic", "pro"]
    n_cust = 2000
    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?)",
        [
            (
                i,
                f"customer_{i:04d}",
                tiers[min(int(rng.exponential(2)), 2)],
                cities[int(rng.integers(0, len(cities)))],
            )
            for i in range(1, n_cust + 1)
        ],
    )
    categories = ["sensor", "gateway", "module", "accessory", "service"]
    products = [
        (
            i,
            f"SKU-{i:03d}",
            categories[int(rng.integers(0, len(categories)))],
            round(float(rng.uniform(20, 2000)), 2),
        )
        for i in range(1, 51)
    ]
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    prices = {p[0]: p[3] for p in products}

    # 订单: 周末 x1.6, 趋势 +18%/120天, 促销日(第45/第90天)x2.2
    promo_days = {45, 90}
    seq = 0
    for d in range(ORDER_DAYS):
        day = ANCHOR + timedelta(days=d)
        trend = 1.0 + 0.18 * d / ORDER_DAYS
        dow = day.weekday()
        weekend = 1.6 if dow >= 5 else 1.0
        promo = 2.2 if d in promo_days else 1.0
        n = int(BASE_ORDERS_PER_DAY * trend * weekend * promo * rng.normal(1, 0.04))
        # 时段分布: 早晚高峰
        hour_w = np.array(
            [
                0.2,
                0.1,
                0.05,
                0.05,
                0.1,
                0.5,
                1,
                1.5,
                2,
                2,
                1.8,
                1.5,
                1.2,
                1.2,
                1.5,
                1.8,
                2,
                2.2,
                2,
                1.5,
                1.2,
                1,
                0.6,
                0.4,
            ]
        )
        hour_w = hour_w / hour_w.sum()
        hours = rng.choice(24, size=n, p=hour_w)
        batch = []
        for h in hours:
            ts = day + timedelta(
                hours=int(h), minutes=int(rng.integers(0, 60)), seconds=int(rng.integers(0, 60))
            )
            pid = int(rng.integers(1, 51))
            qty = max(1, int(rng.geometric(0.45)))
            amount = round(prices[pid] * qty * rng.uniform(0.9, 1.1), 2)
            if rng.random() < 0.10:  # 单位误记为分
                amount = round(amount * 100, 2)
            seq += 1
            order_id = f"SO{2025000000 + seq}"
            if rng.random() < 0.001:  # 重复订单号
                order_id = f"SO{2025000000 + max(1, seq - int(rng.integers(1, 500)))}"
            batch.append(
                (
                    order_id,
                    ts.isoformat(sep=" "),
                    int(rng.integers(1, n_cust + 1)),
                    pid,
                    qty,
                    amount,
                    "app" if rng.random() < 0.6 else "web",
                )
            )
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", batch)
        if (d + 1) % 30 == 0:
            conn.commit()
            print(f"  orders day {d + 1}/{ORDER_DAYS}: cum {seq:,}")
    # 脏数据: qty <= 0 少量
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
        [
            (f"BAD{i}", (ANCHOR + timedelta(days=i)).isoformat(sep=" "), 1, 1, 0, 99.0, "app")
            for i in range(5)
        ],
    )
    conn.commit()
    conn.close()


def gen_master(raw_dir: Path) -> None:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "equipment"
    ws.append(
        [
            "device_id",
            "model",
            "site",
            "vendor",
            "install_date",
            "warranty_years",
            "rated_voltage_v",
            "rated_temp_c",
            "notes",
        ]
    )
    models = ["A100", "A200", "B300"]
    vendors = ["VendorX", "VendorY", "VendorZ"]
    for i, dev in enumerate(device_ids(), start=1):
        ws.append(
            [
                dev,
                models[i % 3],
                f"site-{i % 4 + 1}",
                vendors[i % 3],
                (ANCHOR - timedelta(days=int(rng.integers(200, 1200)))).date().isoformat(),
                2 + i % 3,
                "12.0",
                "25.0",
                "" if i % 5 else "firmware pending",
            ]
        )
    out = raw_dir / "master" / "equipment_master.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"  wrote {out.relative_to(raw_dir)}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="generate demo raw data")
    parser.add_argument("--only", choices=["all", "sensors", "orders", "master"], default="all")
    args = parser.parse_args()

    lake = lake_config()
    raw = Path(lake.raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    print(f"[gen] raw dir: {raw}")
    if args.only in ("all", "sensors"):
        print("[gen] sensors ...")
        gen_sensors(raw)
    if args.only in ("all", "orders"):
        print("[gen] orders ...")
        gen_orders(raw)
    if args.only in ("all", "master"):
        print("[gen] master ...")
        gen_master(raw)
    print("[gen] done")


if __name__ == "__main__":
    main()
