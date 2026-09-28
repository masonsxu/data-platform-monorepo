"""FastAPI 查询服务: Dashboard 的唯一后端。

dev:   uv run serve -> :8001, vite proxy /api -> :8001
prod:  先 pnpm build (dashboard/dist), 同进程托管 SPA, 单进程部署
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
from data_core.engine import Engine
from data_core.lake import lake_config
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from api import queries

app = FastAPI(title="data-platform api")
engine = Engine()


def _round_frame(df: pl.DataFrame) -> list[dict]:
    return df.with_columns(pl.col(pl.Float64).round(2)).to_dicts()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "engine": engine.name}


@app.get("/api/overview")
def overview(days: int = Query(default=30, ge=1, le=120)) -> dict:
    daily = engine.query(queries.daily_orders(engine.name, days))
    daily = daily.sort("date")
    categories = engine.query(queries.category_revenue(engine.name, days))
    sensors = engine.query(queries.sensor_summary(engine.name))
    return {
        "days": days,
        "daily_orders": _round_frame(daily),
        "category_revenue": _round_frame(categories),
        "sensor_summary": sensors.to_dicts()[0],
    }


@app.get("/api/sensors/series")
def sensor_series(
    device: str = Query(pattern=r"^D-\d{2}$"),
    date_from: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> list[dict]:
    df = engine.query(queries.sensor_series(engine.name, device, date_from, date_to))
    return _round_frame(df)


@app.get("/api/sensors/anomalies")
def sensor_anomalies(z: float = Query(default=2.0, ge=0.5, le=5.0)) -> list[dict]:
    df = engine.query(queries.sensor_anomalies(engine.name, z))
    return _round_frame(df)


@app.get("/api/forecast")
def forecast() -> list[dict]:
    path = Path(lake_config().clean_dir) / "forecast" / "daily_orders_forecast.parquet"
    if not path.exists():
        raise HTTPException(status_code=404, detail="forecast not generated; run `predict` first")
    return (
        pl.read_parquet(path)
        .with_columns(
            pl.col("orders").cast(pl.Float64),
            pl.col("forecast").cast(pl.Float64),
            pl.col("lower").cast(pl.Float64),
            pl.col("upper").cast(pl.Float64),
        )
        .to_dicts()
    )


# prod: 托管 SPA(build 后存在才挂载); /api 外的未知路径回退 index.html(SPA history 路由)
_dist = Path(__file__).resolve().parents[4] / "apps" / "dashboard" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="spa-assets")

    @app.exception_handler(404)
    async def spa_fallback(request, exc):  # noqa: ANN001
        from fastapi.responses import FileResponse, JSONResponse

        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return FileResponse(_dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_root(path: str) -> FileResponse:
        from fastapi.responses import FileResponse

        if path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = _dist / path
        return FileResponse(target if target.is_file() else _dist / "index.html")


def main() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, workers=1)


if __name__ == "__main__":
    main()
