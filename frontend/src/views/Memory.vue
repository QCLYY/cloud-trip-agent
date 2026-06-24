<script setup lang="ts">
import { message } from "ant-design-vue";
import { onMounted, ref } from "vue";

import { clearMemory, deleteMemory, fetchMemory, updateMemoryEnabled } from "../services/api";
import type { UserMemoryItem } from "../types";

const loading = ref(false);
const saving = ref(false);
const enabled = ref(false);
const items = ref<UserMemoryItem[]>([]);

async function loadMemory() {
  loading.value = true;
  try {
    const response = await fetchMemory();
    enabled.value = response.enabled;
    items.value = response.items;
  } catch (error) {
    console.error(error);
    message.error("长期记忆加载失败。");
  } finally {
    loading.value = false;
  }
}

async function toggleMemory() {
  saving.value = true;
  try {
    const response = await updateMemoryEnabled(!enabled.value);
    enabled.value = response.enabled;
    items.value = response.items;
    message.success(enabled.value ? "长期记忆已开启。" : "长期记忆已关闭。");
  } catch (error) {
    console.error(error);
    message.error("长期记忆设置失败。");
  } finally {
    saving.value = false;
  }
}

async function removeItem(memoryId: number) {
  try {
    await deleteMemory(memoryId);
    items.value = items.value.filter((item) => item.id !== memoryId);
    message.success("记忆已删除。");
  } catch (error) {
    console.error(error);
    message.error("删除记忆失败。");
  }
}

async function clearAll() {
  if (!window.confirm("确定清空全部长期记忆吗？")) {
    return;
  }
  try {
    await clearMemory();
    items.value = [];
    message.success("长期记忆已清空。");
  } catch (error) {
    console.error(error);
    message.error("清空记忆失败。");
  }
}

onMounted(() => {
  void loadMemory();
});
</script>

<template>
  <section class="memory-page">
    <div class="memory-header">
      <div>
        <h2>长期记忆管理</h2>
        <p>只保存你明确表达的稳定旅行偏好，关闭后不读取、不新增跨会话记忆。</p>
      </div>
      <button class="primary-button" :disabled="saving" @click="toggleMemory">
        {{ enabled ? "关闭长期记忆" : "开启长期记忆" }}
      </button>
    </div>

    <div v-if="loading" class="memory-state">正在加载长期记忆...</div>
    <div v-else class="memory-card">
      <div class="memory-card__status">
        <span>当前状态</span>
        <strong>{{ enabled ? "已开启" : "已关闭" }}</strong>
      </div>
      <button class="secondary-button" :disabled="items.length === 0" @click="clearAll">
        清空全部
      </button>
    </div>

    <div v-if="!loading && items.length === 0" class="memory-state">
      暂无长期记忆。开启后，系统会从你明确填写的偏好中保存稳定信息。
    </div>

    <div v-else class="memory-list">
      <article v-for="item in items" :key="item.id" class="memory-item">
        <div>
          <div class="memory-item__type">{{ item.memory_type }}</div>
          <div class="memory-item__content">{{ item.content }}</div>
        </div>
        <button class="danger-button" @click="removeItem(item.id)">删除</button>
      </article>
    </div>
  </section>
</template>

<style scoped>
.memory-page {
  display: grid;
  gap: 18px;
}

.memory-header,
.memory-card,
.memory-state,
.memory-item {
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 22px 55px rgba(98, 116, 164, 0.12);
}

.memory-header,
.memory-card,
.memory-item {
  padding: 22px;
}

.memory-header,
.memory-card,
.memory-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.memory-header h2 {
  margin: 0 0 8px;
  color: #31456a;
}

.memory-header p,
.memory-state,
.memory-item__type {
  color: #667085;
}

.memory-state {
  padding: 26px;
  text-align: center;
}

.primary-button,
.secondary-button,
.danger-button {
  border: none;
  border-radius: 14px;
  padding: 11px 15px;
  font-weight: 800;
  cursor: pointer;
}

.primary-button {
  background: linear-gradient(135deg, #7386e0 0%, #8f71d8 100%);
  color: #fff;
}

.secondary-button {
  background: rgba(59, 130, 246, 0.12);
  color: #3568d4;
}

.danger-button {
  background: rgba(239, 68, 68, 0.12);
  color: #c2410c;
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.memory-card__status {
  display: grid;
  gap: 4px;
}

.memory-card__status strong {
  color: #42558d;
}

.memory-list {
  display: grid;
  gap: 12px;
}

.memory-item__content {
  margin-top: 6px;
  color: #334155;
  font-weight: 700;
}
</style>
