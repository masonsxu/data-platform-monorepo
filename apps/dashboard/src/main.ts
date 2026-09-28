import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "overview", component: () => import("./views/OverviewView.vue") },
    { path: "/sensors", name: "sensors", component: () => import("./views/SensorsView.vue") },
    { path: "/forecast", name: "forecast", component: () => import("./views/ForecastView.vue") },
  ],
});

createApp(App).use(router).mount("#app");
