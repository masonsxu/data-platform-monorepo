<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type Overview } from "@data-platform/api-client";
import type { EChartsOption } from "echarts";
import { useEChart } from "@/composables/useEChart";

const data = ref<Overview | null>(null);
const days = ref(30);
const error = ref("");

async function load() {
  try {
    error.value = "";
    data.value = await api.overview(days.value);
  } catch (e) {
    error.value = String(e);
  }
}
onMounted(load);

const trendOption = computed<EChartsOption>(
  () => ({
    tooltip: { trigger: "axis" },
    legend: {},
    grid: { left: 60, right: 70, top: 40, bottom: 40 },
    xAxis: { type: "category", data: data.value?.daily_orders.map((d) => d.date) ?? [] },
    yAxis: [
      { type: "value", name: "订单量" },
      { type: "value", name: "收入(元)", axisLabel: { formatter: (v: number) => `${(v / 1e6).toFixed(0)}M` } },
    ],
    series: [
      { name: "订单量", type: "bar", data: data.value?.daily_orders.map((d) => d.orders) ?? [] },
      {
        name: "收入",
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        data: data.value?.daily_orders.map((d) => d.revenue) ?? [],
      },
    ],
  }),
);
const trendEl = useEChart(trendOption);

const categoryOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 80, right: 40, top: 20, bottom: 40 },
  xAxis: { type: "value", name: "收入(元)", axisLabel: { formatter: (v: number) => `${(v / 1e6).toFixed(0)}M` } },
  yAxis: { type: "category", data: (data.value?.category_revenue ?? []).map((c) => c.category) },
  series: [
    {
      name: "收入",
      type: "bar",
      data: (data.value?.category_revenue ?? []).map((c) => c.revenue),
      itemStyle: { color: "#3370ff" },
    },
  ],
}));
const categoryEl = useEChart(categoryOption);

const fmtInt = (v: number | undefined) => (v ?? 0).toLocaleString("zh-CN");
const fmtPct = (v: number | undefined) => `${((v ?? 0) * 100).toFixed(1)}%`;
</script>

<template>
  <div>
    <div class="controls">
      <label>时间范围</label>
      <select v-model.number="days" @change="load">
        <option :value="7">最近 7 天</option>
        <option :value="30">最近 30 天</option>
        <option :value="90">最近 90 天</option>
      </select>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="kpis" v-if="data">
      <div class="card kpi">
        <div class="value">{{ fmtInt(data.daily_orders.reduce((s, d) => s + d.orders, 0)) }}</div>
        <div class="label">订单总量</div>
      </div>
      <div class="card kpi">
        <div class="value">
          {{ (data.daily_orders.reduce((s, d) => s + d.revenue, 0) / 1e6).toFixed(1) }}M
        </div>
        <div class="label">总收入(元)</div>
      </div>
      <div class="card kpi">
        <div class="value">{{ data.sensor_summary.total_devices }}</div>
        <div class="label">接入设备</div>
      </div>
      <div class="card kpi">
        <div class="value">{{ fmtPct(data.sensor_summary.online_ratio) }}</div>
        <div class="label">设备在线率(全程)</div>
      </div>
    </div>

    <div class="card">
      <h3>日订单量与收入</h3>
      <div ref="trendEl" class="chart"></div>
    </div>

    <div class="card">
      <h3>品类收入</h3>
      <div ref="categoryEl" class="chart" style="height: 300px"></div>
    </div>
  </div>
</template>
