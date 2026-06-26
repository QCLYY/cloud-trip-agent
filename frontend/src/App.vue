<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "./stores/auth";
import { useItineraryStore } from "./stores/itinerary";


const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const itineraryStore = useItineraryStore();

function hasItinerary() {
  return itineraryStore.current !== null;
}

const currentRouteName = computed(() => String(route.name || ""));
const resultRouteNames = ["result", "sources", "agentStatus"];
const isResultRoute = computed(() => resultRouteNames.includes(currentRouteName.value));
const resultMode = computed(() => {
  if (currentRouteName.value === "sources") {
    return "sources";
  }
  if (currentRouteName.value === "agentStatus") {
    return "agent-status";
  }
  return "result";
});
const isAuthPage = computed(() => {
  return currentRouteName.value === "login" || currentRouteName.value === "register";
});


function goToRoute(name: "home" | "result" | "sources" | "agentStatus" | "history" | "memory") {
  if (resultRouteNames.includes(name) && !hasItinerary()) {
    return;
  }
  void router.push({ name });
}


function handleLogout() {
  authStore.logout();
  itineraryStore.clear();
  void router.replace({ name: "login" });
}
</script>

<template>
  <div class="app-shell">
    <div class="app-shell__glow app-shell__glow--left"></div>
    <div class="app-shell__glow app-shell__glow--right"></div>

    <header v-if="!isAuthPage" class="hero">
      <div class="hero__topline">
        <div class="hero__badge">Cloud Trip Agent</div>
        <div class="hero__user">
          <span>{{ authStore.currentUser?.username || "已登录" }}</span>
          <button type="button" @click="handleLogout">退出登录</button>
        </div>
      </div>

      <h1 class="hero__title">云程智绘图</h1>

      <div class="hero__tabs">
        <button
          :class="['hero__tab', { 'hero__tab--active': currentRouteName === 'home' }]"
          type="button"
          @click="goToRoute('home')"
        >
          新建行程
        </button>
        <button
          :class="[
            'hero__tab',
            { 'hero__tab--active': currentRouteName === 'result' },
            { 'hero__tab--disabled': !hasItinerary() }
          ]"
          :disabled="!hasItinerary()"
          type="button"
          @click="goToRoute('result')"
        >
          当前结果
        </button>
        <button
          :class="[
            'hero__tab',
            { 'hero__tab--active': currentRouteName === 'sources' },
            { 'hero__tab--disabled': !hasItinerary() }
          ]"
          :disabled="!hasItinerary()"
          type="button"
          @click="goToRoute('sources')"
        >
          数据来源
        </button>
        <button
          :class="[
            'hero__tab',
            { 'hero__tab--active': currentRouteName === 'agentStatus' },
            { 'hero__tab--disabled': !hasItinerary() }
          ]"
          :disabled="!hasItinerary()"
          type="button"
          @click="goToRoute('agentStatus')"
        >
          Agent状态
        </button>
        <button
          :class="['hero__tab', { 'hero__tab--active': currentRouteName === 'history' }]"
          type="button"
          @click="goToRoute('history')"
        >
          历史行程
        </button>
        <button
          :class="['hero__tab', { 'hero__tab--active': currentRouteName === 'memory' }]"
          type="button"
          @click="goToRoute('memory')"
        >
          长期记忆
        </button>
      </div>
    </header>

    <main :class="['page-content', { 'page-content--auth': isAuthPage }]">
      <RouterView v-slot="{ Component }">
        <component
          :is="Component"
          v-if="currentRouteName === 'home'"
        />
        <component
          :is="Component"
          v-else-if="isResultRoute"
          :itinerary="itineraryStore.current"
          :mode="resultMode"
          @back-home="goToRoute('home')"
          @view-history="goToRoute('history')"
        />
        <component
          :is="Component"
          v-else-if="currentRouteName === 'history'"
          :active="currentRouteName === 'history'"
        />
        <component :is="Component" v-else-if="currentRouteName === 'memory'" />
        <component :is="Component" v-else />
      </RouterView>
    </main>
  </div>
</template>

<style scoped>
:global(body) {
  margin: 0;
  min-width: 320px;
  font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(175, 198, 255, 0.55), transparent 28%),
    radial-gradient(circle at right 18%, rgba(181, 150, 255, 0.3), transparent 20%),
    linear-gradient(180deg, #eef4ff 0%, #edf2f9 100%);
  color: #1f2937;
}

:global(*) {
  box-sizing: border-box;
}

.app-shell {
  position: relative;
  min-height: 100vh;
  padding: 40px 24px 64px;
  overflow: hidden;
}

.app-shell__glow {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  filter: blur(24px);
  opacity: 0.5;
  pointer-events: none;
}

.app-shell__glow--left {
  top: -110px;
  left: -90px;
  background: rgba(113, 132, 255, 0.45);
}

.app-shell__glow--right {
  right: -80px;
  bottom: 120px;
  background: rgba(155, 116, 255, 0.25);
}

.hero {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto 28px;
  text-align: center;
}

.hero__topline {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.hero__badge {
  display: inline-flex;
  align-items: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #5c6ac4;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.04em;
  box-shadow: 0 12px 30px rgba(98, 116, 164, 0.1);
}

.hero__user {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px 7px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #4b5563;
  font-size: 13px;
  font-weight: 700;
}

.hero__user button {
  border: none;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(109, 130, 222, 0.12);
  color: #5b5bd6;
  font-weight: 800;
  cursor: pointer;
}

.hero__title {
  margin: 18px 0 0;
  color: #ffffff;
  font-size: 48px;
  line-height: 1.1;
}

.hero::before {
  content: "";
  position: absolute;
  inset: -24px 0 auto;
  height: 220px;
  z-index: -1;
  border-radius: 36px;
  background: linear-gradient(135deg, #6d82de 0%, #6f72d9 52%, #8c67cf 100%);
  box-shadow: 0 32px 80px rgba(95, 110, 172, 0.3);
}

.hero__tabs {
  display: inline-flex;
  gap: 10px;
  margin-top: 24px;
  padding: 8px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(10px);
}

.hero__tab {
  border: none;
  border-radius: 12px;
  padding: 10px 18px;
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}

.hero__tab--active {
  background: rgba(255, 255, 255, 0.92);
  color: #5f60c8;
}

.hero__tab--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-content {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto;
}

.page-content--auth {
  max-width: none;
}

@media (max-width: 768px) {
  .app-shell {
    padding: 24px 16px 40px;
  }

  .hero__topline {
    align-items: stretch;
    flex-direction: column;
  }

  .hero__user,
  .hero__badge {
    justify-content: center;
  }

  .hero__title {
    font-size: 34px;
  }

  .hero::before {
    inset: -20px 0 auto;
    height: 245px;
  }

  .hero__tabs {
    width: 100%;
    justify-content: center;
    flex-wrap: wrap;
  }
}
</style>
