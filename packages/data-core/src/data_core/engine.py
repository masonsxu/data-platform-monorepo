"""双引擎查询抽象: DuckDB(本地 Parquet) | StarRocks(集群内表)。

引擎选择规则: settings.starrocks.enabled 且连接成功 -> starrocks, 否则 duckdb。
业务方言差异集中在 SQL 模板层, 本模块只负责执行与结果归一。
"""

from __future__ import annotations

import logging
from typing import Literal

import polars as pl

from data_core.config import load_settings
from data_core.lake import get_duckdb

log = logging.getLogger(__name__)

EngineName = Literal["duckdb", "starrocks"]


class Engine:
    """统一 query(sql) -> pl.DataFrame 入口。"""

    def __init__(self, force: EngineName | None = None) -> None:
        settings = load_settings()
        self._settings = settings
        if force == "duckdb" or not settings.starrocks.enabled:
            self.name: EngineName = "duckdb"
        else:
            self.name = self._probe_starrocks() or "duckdb"
        if force and force != self.name:
            raise RuntimeError(f"engine {force} requested but {self.name} active")
        log.info("query engine: %s", self.name)

    def _probe_starrocks(self) -> EngineName | None:
        import pymysql

        try:
            pymysql.connect(
                host=self._settings.starrocks.host,
                port=self._settings.starrocks.port,
                user=self._settings.starrocks.user,
                password=self._settings.starrocks.password,
                connect_timeout=3,
            ).close()
            return "starrocks"
        except Exception as exc:  # noqa: BLE001 - 回退场景需捕获一切连接错误
            log.warning("StarRocks unreachable (%s), fallback to DuckDB", exc)
            return None

    def query(self, sql: str) -> pl.DataFrame:
        if self.name == "starrocks":
            return self._query_starrocks(sql)
        return get_duckdb().execute(sql).pl()

    def _query_starrocks(self, sql: str) -> pl.DataFrame:
        import pymysql

        conn = pymysql.connect(
            host=self._settings.starrocks.host,
            port=self._settings.starrocks.port,
            user=self._settings.starrocks.user,
            password=self._settings.starrocks.password,
            database=self._settings.starrocks.database,
            connect_timeout=5,
        )
        try:
            return pl.read_database(sql, connection=conn)
        finally:
            conn.close()
