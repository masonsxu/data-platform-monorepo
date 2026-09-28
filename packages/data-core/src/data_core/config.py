"""配置加载: config/settings.toml + 环境变量覆盖。

优先级: 环境变量 DP_* > config/settings.toml > 内置默认值。
真实 StarRocks 与对象存储凭据只放环境变量或 settings.toml(已 gitignore)。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# config.py 位于 packages/data-core/src/data_core/ 下, 4 层上溯到 monorepo 根
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.toml"


@dataclass(frozen=True)
class LakeConfig:
    # 本地目录或 s3://bucket/prefix; s3 模式需配置 endpoint/region/ak/sk
    root: str = str(PROJECT_ROOT / "lake")
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    @property
    def raw_dir(self) -> str:
        return f"{self.root.rstrip('/')}/raw"

    @property
    def clean_dir(self) -> str:
        return f"{self.root.rstrip('/')}/clean"

    @property
    def is_s3(self) -> bool:
        return self.root.startswith("s3://")


@dataclass(frozen=True)
class StarRocksConfig:
    host: str = "127.0.0.1"
    port: int = 9030
    user: str = "root"
    password: str = ""
    database: str = "dp_dw"
    # False 时 Engine 回退 DuckDB 直查 Parquet, 无集群也能完整运行
    enabled: bool = False


@dataclass(frozen=True)
class Settings:
    lake: LakeConfig = field(default_factory=LakeConfig)
    starrocks: StarRocksConfig = field(default_factory=StarRocksConfig)


def _load_toml(path: Path) -> dict:
    if path.exists():
        with path.open("rb") as f:
            return tomllib.load(f)
    return {}


def load_settings(path: Path | None = None) -> Settings:
    raw = _load_toml(path or DEFAULT_SETTINGS_PATH)
    lake_raw = raw.get("lake", {})
    sr_raw = raw.get("starrocks", {})
    env = os.environ

    lake = LakeConfig(
        root=env.get("DP_LAKE_ROOT", lake_raw.get("root", str(PROJECT_ROOT / "lake"))),
        s3_endpoint=env.get("DP_LAKE_S3_ENDPOINT", lake_raw.get("s3_endpoint", "")),
        s3_region=env.get("DP_LAKE_S3_REGION", lake_raw.get("s3_region", "")),
        s3_access_key=env.get("DP_LAKE_AK", lake_raw.get("s3_access_key", "")),
        s3_secret_key=env.get("DP_LAKE_SK", lake_raw.get("s3_secret_key", "")),
    )
    starrocks = StarRocksConfig(
        host=env.get("DP_SR_HOST", sr_raw.get("host", "127.0.0.1")),
        port=int(env.get("DP_SR_PORT", sr_raw.get("port", 9030))),
        user=env.get("DP_SR_USER", sr_raw.get("user", "root")),
        password=env.get("DP_SR_PASSWORD", sr_raw.get("password", "")),
        database=env.get("DP_SR_DB", sr_raw.get("database", "dp_dw")),
        enabled=str(env.get("DP_SR_ENABLED", sr_raw.get("enabled", False))).lower()
        in ("1", "true", "yes"),
    )
    return Settings(lake=lake, starrocks=starrocks)
