import { createApp } from "vue";
import Antd from "ant-design-vue";
import { createPinia } from "pinia";
import "ant-design-vue/dist/reset.css";

import App from "./App.vue";
import router from "./router";
import { setAuthFailureHandler, setTokenProvider } from "./services/api";
import { useAuthStore } from "./stores/auth";


const app = createApp(App);
const pinia = createPinia();

app.use(Antd);
app.use(pinia);

const authStore = useAuthStore(pinia);

setTokenProvider(() => authStore.token);
setAuthFailureHandler(() => {
  authStore.clearSession();

  const currentRoute = router.currentRoute.value;
  if (currentRoute.name !== "login" && currentRoute.name !== "register") {
    void router.push({
      name: "login",
      query: { redirect: currentRoute.fullPath },
    });
  }
});

app.use(router);
app.mount("#app");
