"""日订单量预测模型: 特征工程 + 训练 + MLflow tracking。

数据: lake/clean/orders 的日聚合(120 天)
特征: lag_1/7/14, day_of_week, is_weekend, promo(规则: 第45/90天, 真实场景来自营销日历)
切分: 时间前向切分, 前 106 天训练 / 后 14 天验证(防泄漏)
模型: HistGradientBoostingRegressor(CPU, 125 万行聚合后仅 120 行日数据, 训练 <1s)
产物: MLflow run(local mlruns) + 注册 latest 模型
"""

from __future__ import annotations

from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import polars as pl
from data_core.config import PROJECT_ROOT
from data_core.lake import lake_config
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

TRAIN_DAYS = 106  # 120 天中前 106 训练, 后 14 验证
PROMO_DAYS = {45, 90}
TRACKING_URI = f"sqlite:///{PROJECT_ROOT / 'mlflow.db'}"
MODEL_SNAPSHOT = "models/daily_orders_hgb.joblib"


def load_daily() -> pl.DataFrame:
    lake = lake_config()
    df = pl.read_parquet(f"{lake.clean_dir}/orders/**/*.parquet", hive_partitioning=True)
    return (
        df.sort("ts")
        .group_by_dynamic("ts", every="1d")
        .agg(pl.len().alias("orders"), pl.col("amount").sum().alias("revenue"))
        .sort("ts")
        .with_columns(pl.col("ts").dt.epoch("d").alias("day_index"))
        .with_columns(
            pl.col("day_index").diff(1).alias("lag_1"),
            pl.col("orders").shift(1).alias("lag_1_orders"),
            pl.col("orders").shift(7).alias("lag_7"),
            pl.col("orders").shift(14).alias("lag_14"),
            pl.col("ts").dt.weekday().alias("dow"),
        )
        .with_columns((pl.col("dow") >= 6).cast(pl.Int8).alias("is_weekend"))
        .with_columns(pl.col("day_index").is_in(sorted(PROMO_DAYS)).cast(pl.Int8).alias("promo"))
        .drop_nulls(["lag_14"])
    )


FEATURES = ["lag_1_orders", "lag_7", "lag_14", "dow", "is_weekend", "promo"]


def main() -> None:
    df = load_daily()
    print(f"[train] daily rows: {df.height}")
    train, valid = df.head(TRAIN_DAYS - 14), df.tail(14)
    Xtr, ytr = train[FEATURES].to_numpy(), train["orders"].to_numpy()
    Xva, yva = valid[FEATURES].to_numpy(), valid["orders"].to_numpy()

    model = HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.06, max_depth=4, random_state=42
    )
    model.fit(Xtr, ytr)
    pred = model.predict(Xva)
    mae = mean_absolute_error(yva, pred)
    mape = float((abs(yva - pred) / yva).mean() * 100)
    r2 = r2_score(yva, pred)
    print(f"[train] valid MAE={mae:.0f} MAPE={mape:.2f}% R2={r2:.3f}")

    mlflow.set_tracking_uri(TRACKING_URI)
    model_artifact = lake_config().clean_dir + "/models/daily_orders_hgb.joblib"
    Path(model_artifact).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"features": FEATURES, "model": model}, model_artifact)
    with mlflow.start_run(run_name="daily-orders-hgb") as run:
        mlflow.log_params(
            {
                "model": "HistGradientBoosting",
                "features": FEATURES,
                "train_days": TRAIN_DAYS - 14,
                "valid_days": 14,
            }
        )
        mlflow.log_metrics({"mae": mae, "mape": mape, "r2": r2})
        mlflow.sklearn.log_model(model, name="model")
        mlflow.set_tag("artifact", model_artifact)
        print(f"[train] mlflow run_id={run.info.run_id}")
        print(f"[train] inference snapshot: {model_artifact}")


if __name__ == "__main__":
    main()
