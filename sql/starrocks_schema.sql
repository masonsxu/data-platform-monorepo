-- StarRocks 仓库层 DDL: 湖(clean Parquet) -> 内表, 供 10 人并发查询。
-- 执行入口: uv run sr-load --mode schema|load|verify  (连接配置见 config/settings.toml)

CREATE DATABASE IF NOT EXISTS dp_dw;
USE dp_dw;

-- 传感器读数: 1244 万行, 按天分区 180 个, hash(device_id) 8 桶
CREATE TABLE IF NOT EXISTS device_readings (
    device_id    VARCHAR NOT NULL,
    ts           DATETIME NOT NULL,
    temp_c       DOUBLE,
    humidity_pct DOUBLE,
    voltage_v    DOUBLE,
    current_a    DOUBLE,
    status       VARCHAR
)
DUPLICATE KEY(device_id, ts)
PARTITION BY date_trunc('day', ts)
DISTRIBUTED BY HASH(device_id) BUCKETS 8
PROPERTIES ("replication_num" = "3");

-- 订单: 125 万行, 按天分区
CREATE TABLE IF NOT EXISTS orders (
    order_id    VARCHAR NOT NULL,
    ts          DATETIME NOT NULL,
    customer_id INT,
    product_id  INT,
    qty         INT,
    amount      DOUBLE,
    channel     VARCHAR
)
DUPLICATE KEY(order_id, ts)
PARTITION BY date_trunc('day', ts)
DISTRIBUTED BY HASH(order_id) BUCKETS 4
PROPERTIES ("replication_num" = "3");

-- 维表(小表, 主键模型)
CREATE TABLE IF NOT EXISTS products (
    product_id INT NOT NULL,
    name       VARCHAR,
    category   VARCHAR,
    unit_price DOUBLE
)
PRIMARY KEY (product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES ("replication_num" = "3");

CREATE TABLE IF NOT EXISTS customers (
    customer_id INT NOT NULL,
    name   VARCHAR,
    tier   VARCHAR,
    city   VARCHAR
)
PRIMARY KEY (customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES ("replication_num" = "3");
