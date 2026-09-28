<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type ForecastPoint } from "@data-platform/api-client";
import type { EChartsOption } from "echarts";
import { useEChart } from "@/composables/useEChart";

const points = ref<ForecastPoint[]>([]);
const error = ref("");

onMounted(async () => {
  try {
    points.value = await api.forecast();
  } catch (e) {
    error.value = String(e);
  }
});

const option = computed<EChartsOption>(() => {
  const pts = points.value;
  return {
    tooltip: { trigger: "axis" },
    legend: {},
    grid: { left: 70, right: 40, top: 40, bottom: 40 },
    xAxis: { type: "category", data: pts.map((p) => p.ts.slice(0, 10)) },
    yAxis: { type: "value", name: "日订单量", scale: true },
    series: [
      {
        name: "预测上界",
        type: "line",
        data: pts.map((p) => p.upper),
        lineStyle: { opacity: 0 },
        stack: "band",
        symbol: "none",
      },
      {
        name: "95% 置信带",
        type: "line",
        data: pts.map((p) => (p.upper != null && p.lower != null ? p.upper - p.lower : null)),
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0.15, color: "#3370ff" },
        stack: "band",
        symbol: "none",
      },
      {
        name: "实际订单",
        type: "line",
        data: pts.map((p) => p.orders),
        showSymbol: false,
      },
      {
        name: "预测",
        type: "line",
        data: pts.map((p) => p.forecast),
        showSymbol: false,
        lineStyle: { type: "dashed", color: "#e02020" },
      },
    ],
  };
});
const chartEl = useEChart(option);
</script>

<template>
  <div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="card">
      <h3>日订单量: 历史(实线) 与模型预测(虚线, 未来 7 天, 95% 置信带)</h3>
      <div ref="chartEl" class="chart"></div>
    </div>
    <div class="card">
      <h3>链路说明</h3>
      <p style="font-size: 13px; color: #646a73; line-height: 1.8">
        lake/clean/orders(Parquet) → 日聚合 → lag/dow 特征 → HistGradientBoosting 训练(MLflow
        记录指标: 验证集 MAPE 7.5%) → joblib 快照落湖 → 递归预测未来 7 天 →
        lake/clean/forecast/daily_orders_forecast.parquet → 本页展示。
      </p>
    </div>
  </div>
</template>
