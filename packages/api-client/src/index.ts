/** Dashboard 后端 API 的类型化客户端(通过 Vite proxy / 同源部署直连)。 */

export interface DailyOrders {
  date: string;
  orders: number;
  revenue: number;
}

export interface CategoryRevenue {
  category: string;
  revenue: number;
  orders: number;
}

export interface SensorSummary {
  total_devices: number;
  online_ratio: number;
  total_readings: number;
}

export interface Overview {
  days: number;
  daily_orders: DailyOrders[];
  category_revenue: CategoryRevenue[];
  sensor_summary: SensorSummary;
}

export interface SensorSeriesPoint {
  ts: string;
  temp_avg: number;
  temp_min: number;
  temp_max: number;
  voltage_avg: number;
}

export interface SensorAnomaly {
  device_id: string;
  date: string;
  temp_avg: number;
  z: number;
}

export interface ForecastPoint {
  ts: string;
  orders: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string; engine: string }>("/api/health"),
  overview: (days = 30) => get<Overview>(`/api/overview?days=${days}`),
  sensorSeries: (device: string, from: string, to: string) =>
    get<SensorSeriesPoint[]>(
      `/api/sensors/series?device=${device}&date_from=${from}&date_to=${to}`,
    ),
  sensorAnomalies: (z = 2) => get<SensorAnomaly[]>(`/api/sensors/anomalies?z=${z}`),
  forecast: () => get<ForecastPoint[]>("/api/forecast"),
};
