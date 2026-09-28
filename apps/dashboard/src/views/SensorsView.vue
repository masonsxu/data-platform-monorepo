<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, type SensorAnomaly, type SensorSeriesPoint } from "@data-platform/api-client";
import type { EChartsOption } from "echarts";
import { useEChart } from "@/composables/useEChart";

const devices = Array.from({ length: 48 }, (_, i) => `D-${String(i + 1).padStart(2, "0")}`);
const device = ref("D-07");
const from = ref("2025-04-01");
const to = ref("2025-04-30");
const anomalies = ref<SensorAnomaly[]>([]);
const error = ref("");

async function load() {
  try {
    error.value = "";
    const [series, anom] = await Promise.all([
      api.sensorSeries(device.value, from.value, to.value),
      api.sensorAnomalies(2),
    ]);
    seriesData.value = series;
    anomalies.value = anom.filter((a) => a.device_id === device.value);
  } catch (e) {
    error.value = String(e);
  }
}
onMounted(load);

const seriesData = ref<SensorSeriesPoint[]>([]);
const seriesOption = computed<EChartsOption>(() => {
  const pts = seriesData.value;
  return {
    tooltip: { trigger: "axis" },
    legend: {},
    grid: { left: 50, right: 60, top: 40, bottom: 60 },
    dataZoom: [{ type: "slider" }],
    xAxis: { type: "category", data: pts.map((p) => p.ts.slice(0, 13)) },
    yAxis: [
      { type: "value", name: "温度(C)", scale: true },
      { type: "value", name: "电压(V)", scale: true },
    ],
    series: [
      {
        name: "温度 min-max",
        type: "line",
        data: pts.map((p) => [p.temp_min, p.temp_max]),
        areaStyle: { opacity: 0.15 },
        lineStyle: { opacity: 0 },
        symbol: "none",
        tooltip: { show: false },
      },
      {
        name: "均温",
        type: "line",
        data: pts.map((p) => p.temp_avg),
        showSymbol: false,
      },
      {
        name: "电压",
        type: "line",
        yAxisIndex: 1,
        data: pts.map((p) => p.voltage_avg),
        showSymbol: false,
        lineStyle: { width: 1, opacity: 0.6 },
      },
    ],
  };
});
const seriesEl = useEChart(seriesOption);
</script>

<template>
  <div>
    <div class="controls">
      <label>设备</label>
      <select v-model="device" @change="load">
        <option v-for="d in devices" :key="d" :value="d">{{ d }}</option>
      </select>
      <label>从</label>
      <input v-model="from" type="date" @change="load" />
      <label>到</label>
      <input v-model="to" type="date" @change="load" />
      <button
        @click="load"
        style="padding: 4px 14px; border: none; border-radius: 6px; background: #3370ff; color: #fff"
      >
        查询
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="card">
      <h3>{{ device }} 小时级温度/电压(数据湖 1244 万行读数按需聚合)</h3>
      <div ref="seriesEl" class="chart"></div>
    </div>

    <div class="card">
      <h3>异常日(设备内日均值 z-score &gt; 2 且绝对偏离 &gt; 0.5C)</h3>
      <table v-if="anomalies.length">
        <thead>
          <tr><th>日期</th><th>日均温度(C)</th><th>z-score</th></tr>
        </thead>
        <tbody>
          <tr v-for="a in anomalies" :key="a.date">
            <td>{{ a.date }}</td>
            <td>{{ a.temp_avg }}</td>
            <td>{{ a.z }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="font-size: 13px; color: #646a73">该设备在查询条件下无异常日</p>
    </div>
  </div>
</template>
