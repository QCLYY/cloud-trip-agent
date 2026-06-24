import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";


const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("../views/Login.vue"),
      meta: { publicOnly: true },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("../views/Register.vue"),
      meta: { publicOnly: true },
    },
    {
      path: "/",
      name: "home",
      component: () => import("../views/Home.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/result",
      name: "result",
      component: () => import("../views/Result.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/result/sources",
      name: "sources",
      component: () => import("../views/Result.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/result/agent-status",
      name: "agentStatus",
      component: () => import("../views/Result.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/history",
      name: "history",
      component: () => import("../views/History.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/memory",
      name: "memory",
      component: () => import("../views/Memory.vue"),
      meta: { requiresAuth: true },
    },
  ],
});


router.beforeEach(async (to) => {
  const authStore = useAuthStore();

  if (!authStore.initialized) {
    await authStore.loadCurrentUser();
  }

  if (to.meta.requiresAuth === true && !authStore.isAuthenticated) {
    return {
      name: "login",
      query: { redirect: to.fullPath },
    };
  }

  if (to.meta.publicOnly === true && authStore.isAuthenticated) {
    return { name: "home" };
  }

  return true;
});


export default router;
