<script setup lang="ts">
import type { ConversationMessageItem } from "../types";

defineProps<{
  message: ConversationMessageItem;
}>();

const typeLabels: Record<string, string> = {
  text: "文本",
  trip_update: "行程更新",
  explanation: "解释",
  confirmation: "确认",
  error: "提示",
};
</script>

<template>
  <article :class="['chat-message', `chat-message--${message.role}`]">
    <div class="chat-message__meta">
      <span>{{ message.role === "user" ? "你" : "AI 旅行顾问" }}</span>
      <span>{{ typeLabels[message.message_type] || message.message_type }}</span>
    </div>
    <div class="chat-message__bubble">
      {{ message.content }}
    </div>
  </article>
</template>

<style scoped>
.chat-message {
  display: grid;
  gap: 6px;
}

.chat-message--user {
  justify-items: end;
}

.chat-message__meta {
  display: flex;
  gap: 8px;
  color: #8a94a6;
  font-size: 12px;
}

.chat-message__bubble {
  max-width: 88%;
  border-radius: 14px;
  padding: 10px 12px;
  background: #f5f7ff;
  color: #344054;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-message--user .chat-message__bubble {
  background: linear-gradient(135deg, #6d82de 0%, #8a67cf 100%);
  color: #ffffff;
}
</style>
