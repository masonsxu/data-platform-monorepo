.PHONY: gen-data etl train predict sr-schema sr-load sr-verify api web build fmt check pipeline

# 全链路: 生成 -> 清洗 -> 训练 -> 预测
pipeline: gen-data etl train predict

gen-data:
	uv run gen-data

etl:
	uv run etl-clean

train:
	uv run train

predict:
	uv run predict

# StarRocks 接入(需 config/settings.toml 配置集群与 s3 湖根)
sr-schema:
	uv run sr-load --mode schema

sr-load:
	uv run sr-load --mode load

sr-verify:
	uv run sr-load --mode verify

api:
	uv run uvicorn api.main:app --port 8001 --reload

web:
	pnpm --filter @data-platform/dashboard dev

build:
	pnpm run build

fmt:
	uv run ruff format apps packages
	uv run ruff check --fix apps packages

check:
	uv run ruff check apps packages
	pnpm run check
