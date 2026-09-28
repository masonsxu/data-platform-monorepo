"""批量预测: 加载 MLflow 最新模型, 递归预测未来 7 天日订单量, 结果落湖。

产物: lake/clean/forecast/daily_orders_forecast.parquet
  列: ts, orders(历史实际, 预测行为空), forecast/lower/upper(预测行, 历史行为空)
区间: 拟合残差 1.96 sigma 近似 95% 置信带。
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import joblib
import mlflow
import numpy as np
import polars as pl
from data_core.lake import lake_config

from training.train import MODEL_SNAPSHOT, TRACKING_URI, load_daily

HORIZON = 7


def load_model_snapshot():
    """加载训练落湖的 joblib 快照(含特征清单), 并返回最新 mlflow run 的验证指标。"""
    path = Path(lake_config().clean_dir) / MODEL_SNAPSHOT
    if not path.exists():
        raise RuntimeError(f"model snapshot not found: {path}; run `train` first")
    snap = joblib.load(path)
    mlflow.set_tracking_uri(TRACKING_URI)
    client = mlflow.tracking.MlflowClient()
    exp = client.get_experiment_by_name("Default")
    runs = client.search_runs(
        [exp.experiment_id], order_by=["attributes.start_time DESC"], max_results=1
    )
    metrics = runs[0].data.metrics if runs else {}
    return snap["model"], snap["features"], metrics


def main() -> None:
    model, features, metrics = load_model_snapshot()
    print(f"[predict] metrics from mlflow: { {k: round(v, 3) for k, v in metrics.items()} }")
    df = load_daily()

    orders = df["orders"].to_list()
    lag14_list = orders[-14:]
    lag7_list = lag14_list[-7:]
    lag1 = orders[-1]
    fitted = model.predict(df[features].to_numpy())
    sigma = float(np.std(df["orders"].to_numpy() - fitted))

    last_ts = df["ts"][-1]
    rows = []
    for step in range(1, HORIZON + 1):
        day = last_ts + dt.timedelta(days=step)
        feat = [
            lag1,
            lag7_list[-7],
            lag14_list[-14],
            day.weekday() + 1,
            int(day.weekday() >= 5),
            0,  # 未来窗口无已知促销; 接营销日历后替换
        ]
        pred = float(model.predict(np.array([feat]))[0])
        rows.append(
            {
                "ts": day,
                "orders": None,
                "forecast": round(pred),
                "lower": round(max(0.0, pred - 1.96 * sigma)),
                "upper": round(pred + 1.96 * sigma),
            }
        )
        lag1 = pred
        lag7_list.append(pred)
        lag14_list.append(pred)

    hist_out = (
        df.select("ts", "orders", "revenue")
        .with_columns(
            forecast=pl.lit(None, dtype=pl.Float64),
            lower=pl.lit(None, dtype=pl.Float64),
            upper=pl.lit(None, dtype=pl.Float64),
            orders=pl.col("orders").cast(pl.Float64),
        )
        .select("ts", "orders", "forecast", "lower", "upper")
    )

    out_dir = Path(lake_config().clean_dir) / "forecast"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "daily_orders_forecast.parquet"
    fc = pl.DataFrame(rows).with_columns(
        pl.col("ts").cast(pl.Datetime("us")),
        pl.col("forecast").cast(pl.Float64),
        pl.col("lower").cast(pl.Float64),
        pl.col("upper").cast(pl.Float64),
        pl.col("orders").cast(pl.Float64),
    )
    pl.concat([hist_out, fc], how="diagonal").write_parquet(out_path)

    print(f"[predict] horizon={HORIZON}d residual_sigma={sigma:.0f}")
    print(f"[predict] wrote {out_path}")
    with pl.Config(tbl_rows=10, fmt_str_lengths=20):
        print(pl.DataFrame(rows).select("ts", "forecast", "lower", "upper"))


if __name__ == "__main__":
    main()
