<script setup lang="ts">
defineProps<{
  confirmationId: number;
  loading: boolean;
}>();

const emit = defineEmits<{
  confirm: [confirmationId: number];
  cancel: [confirmationId: number];
}>();
</script>

<template>
  <div class="assistant-action-card">
    <div>
      <strong>需要人工确认</strong>
      <p>此操作会影响当前行程或版本，请确认是否继续。</p>
    </div>
    <div class="assistant-action-card__actions">
      <button type="button" :disabled="loading" @click="emit('confirm', confirmationId)">
        {{ loading ? "处理中..." : "确认执行" }}
      </button>
      <button type="button" :disabled="loading" class="secondary" @click="emit('cancel', confirmationId)">
        取消
      </button>
    </div>
  </div>
</template>

<style scoped>
.assistant-action-card {
  display: grid;
  gap: 10px;
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255, 251, 235, 0.95);
  color: #78350f;
}

.assistant-action-card p {
  margin: 4px 0 0;
  color: #92400e;
  line-height: 1.6;
}

.assistant-action-card__actions {
  display: flex;
  gap: 8px;
}

.assistant-action-card button {
  border: none;
  border-radius: 10px;
  padding: 8px 10px;
  background: #f59e0b;
  color: #ffffff;
  font-weight: 800;
  cursor: pointer;
}

.assistant-action-card button.secondary {
  background: rgba(120, 53, 15, 0.12);
  color: #78350f;
}

.assistant-action-card button:disabled {
  opacity: 0.65;
  cursor: wait;
}
</style>
