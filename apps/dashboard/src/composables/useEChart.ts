import { onBeforeUnmount, onMounted, ref, type Ref, watch } from "vue";
import * as echarts from "echarts";

/** EChart 实例绑定: 挂载到 ref 指向的 DOM, option 变化自动更新, 组件卸载释放。 */
export function useEChart(option: Ref<echarts.EChartsOption>) {
  const el = ref<HTMLDivElement>();
  let chart: echarts.ECharts | null = null;

  onMounted(() => {
    chart = echarts.init(el.value!);
    chart.setOption(option.value);
  });

  watch(option, (opt) => chart?.setOption(opt, true), { deep: true });

  const resize = () => chart?.resize();
  window.addEventListener("resize", resize);
  onBeforeUnmount(() => {
    window.removeEventListener("resize", resize);
    chart?.dispose();
  });

  return el;
}
