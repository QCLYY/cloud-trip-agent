<script setup lang="ts">
import axios from "axios";
import { message } from "ant-design-vue";
import { computed, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";


const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const formState = reactive({
  username: "",
  password: "",
});
const submitting = ref(false);

const redirectTarget = computed(() => {
  return typeof route.query.redirect === "string" ? route.query.redirect : "/";
});


async function handleSubmit() {
  const username = formState.username.trim();
  if (!username || !formState.password) {
    message.warning("请输入用户名和密码。");
    return;
  }

  submitting.value = true;
  try {
    await authStore.login({
      username,
      password: formState.password,
    });
    message.success("登录成功。");
    await router.replace(redirectTarget.value);
  } catch (error) {
    console.error(error);
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      message.error("用户名或密码错误。");
    } else {
      message.error("登录失败，请稍后重试。");
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section class="auth-page">
    <div class="auth-card">
      <div class="auth-card__eyebrow">云程智绘图</div>
      <h1>登录</h1>
      <p>使用用户名和密码进入旅行规划工作台。</p>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <label class="auth-field">
          <span>用户名</span>
          <a-input
            v-model:value="formState.username"
            autocomplete="username"
            placeholder="请输入用户名"
          />
        </label>

        <label class="auth-field">
          <span>密码</span>
          <a-input-password
            v-model:value="formState.password"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>

        <button class="auth-submit" :disabled="submitting" type="submit">
          {{ submitting ? "登录中..." : "登录" }}
        </button>
      </form>

      <div class="auth-switch">
        还没有账号？
        <RouterLink :to="{ name: 'register', query: route.query }">去注册</RouterLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.auth-page {
  display: grid;
  place-items: center;
  min-height: calc(100vh - 120px);
  padding: 24px;
}

.auth-card {
  width: min(440px, 100%);
  padding: 32px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 22px 55px rgba(98, 116, 164, 0.14);
}

.auth-card__eyebrow {
  color: #5c6ac4;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.auth-card h1 {
  margin: 12px 0 8px;
  color: #31456a;
  font-size: 32px;
}

.auth-card p {
  margin: 0 0 22px;
  color: #667085;
}

.auth-form {
  display: grid;
  gap: 16px;
}

.auth-field {
  display: grid;
  gap: 8px;
  color: #465467;
  font-weight: 700;
}

.auth-submit {
  border: none;
  border-radius: 14px;
  padding: 13px 18px;
  background: linear-gradient(135deg, #7386e0 0%, #8f71d8 100%);
  color: #ffffff;
  font-size: 15px;
  font-weight: 800;
  cursor: pointer;
}

.auth-submit:disabled {
  opacity: 0.7;
  cursor: wait;
}

.auth-switch {
  margin-top: 18px;
  color: #667085;
  text-align: center;
}

.auth-switch a {
  color: #5b5bd6;
  font-weight: 800;
}
</style>
