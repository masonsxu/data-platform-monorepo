<script setup lang="ts">
import { ref, onMounted } from "vue";
import { api } from "@data-platform/api-client";

const engine = ref("...");
onMounted(async () => {
  try {
    engine.value = (await api.health()).engine;
  } catch {
    engine.value = "unreachable";
  }
});
</script>

<template>
  <div class="shell">
    <header>
      <span class="brand">Data Platform Demo</span>
      <nav>
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/sensors">传感器分析</RouterLink>
        <RouterLink to="/forecast">订单预测</RouterLink>
      </nav>
      <span class="engine">engine: {{ engine }}</span>
    </header>
    <main>
      <RouterView />
    </main>
  </div>
</template>

<style>
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family: "PingFang SC", "Helvetica Neue", Arial, sans-serif;
  background: #f5f6f8;
  color: #1f2329;
}
.shell {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 24px 40px;
}
header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 0;
}
.brand {
  font-weight: 700;
  font-size: 18px;
}
nav {
  display: flex;
  gap: 16px;
  flex: 1;
}
nav a {
  color: #3370ff;
  text-decoration: none;
  padding: 4px 10px;
  border-radius: 6px;
}
nav a.router-link-active {
  background: #e8f0ff;
}
.engine {
  font-size: 12px;
  color: #646a73;
  font-family: ui-monospace, monospace;
}
.card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.card h3 {
  margin: 0 0 12px;
  font-size: 14px;
  color: #646a73;
  font-weight: 600;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}
.kpi .value {
  font-size: 26px;
  font-weight: 700;
}
.kpi .label {
  font-size: 12px;
  color: #646a73;
}
.chart {
  width: 100%;
  height: 380px;
}
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.controls label {
  font-size: 13px;
  color: #646a73;
}
.controls select,
.controls input {
  padding: 4px 8px;
  border: 1px solid #d0d3d6;
  border-radius: 6px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th,
td {
  text-align: left;
  padding: 6px 10px;
  border-bottom: 1px solid #f0f1f3;
}
th {
  color: #646a73;
  font-weight: 600;
}
.error {
  color: #d83931;
  font-size: 13px;
}
</style>
