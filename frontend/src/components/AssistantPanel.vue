<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { message as antdMessage } from "ant-design-vue";

import AssistantActionCard from "./AssistantActionCard.vue";
import ChatMessage from "./ChatMessage.vue";
import { useAssistantStore } from "../stores/assistant";
import type { AssistantMessageResponse, ConversationMessageItem, Itinerary } from "../types";

const props = defineProps<{
  itinerary: Itinerary;
}>();

const emit = defineEmits<{
  updated: [itinerary: Itinerary, versionNumber?: number | null];
}>();

const assistantStore = useAssistantStore();
const panelOpen = ref(false);
const inputText = ref("");
const messageListRef = ref<HTMLElement | null>(null);

const tripId = computed(() => props.itinerary.trip_id);
const messages = computed(() => assistantStore.messagesByTrip[tripId.value] || []);
const loading = computed(() => assistantStore.isLoading(tripId.value));
const sending = computed(() => assistantStore.isSending(tripId.value));
const errorText = computed(() => assistantStore.errorForTrip(tripId.value));

const quickQuestions = [
  "为什么推荐这个方案？",
  "帮我把第二天安排得轻松一些",
  "当前总预算是多少？",
  "哪些信息来自外部检索？",
];

function scrollToBottom() {
  void nextTick(() => {
    const element = messageListRef.value;
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  });
}

watch(
  () => tripId.value,
  async (nextTripId) => {
    if (!nextTripId) {
      return;
    }
    await assistantStore.loadMessages(nextTripId);
    scrollToBottom();
  },
  { immediate: true },
);

watch(
  () => messages.value.length,
  () => {
    scrollToBottom();
  },
);

function handleResponse(response: AssistantMessageResponse) {
  if (response.itinerary) {
    emit("updated", response.itinerary, response.new_version_number);
  }
  if (response.new_version_number) {
    antdMessage.success(`已生成新版本 ${response.new_version_number}`);
  }
}

async function sendMessage(text?: string) {
  const content = (text ?? inputText.value).trim();
  if (!content || sending.value) {
    return;
  }

  inputText.value = "";
  try {
    const response = await assistantStore.sendAssistantMessage(
      tripId.value,
      content,
      "balanced",
    );
    handleResponse(response);
  } catch {
    antdMessage.error("AI 旅行顾问处理失败。");
  }
}

function confirmationIdFor(message: ConversationMessageItem): number | null {
  const payload = message.structured_payload || {};
  if (message.role !== "assistant" || message.message_type !== "confirmation") {
    return null;
  }
  if (payload.status === "confirmed" || payload.status === "rejected") {
    return null;
  }
  const confirmationId = payload.confirmation_id;
  return typeof confirmationId === "number" ? confirmationId : null;
}

async function confirmAction(confirmationId: number) {
  try {
    const response = await assistantStore.confirmAssistantAction(tripId.value, confirmationId);
    handleResponse(response);
  } catch {
    antdMessage.error("确认操作失败。");
  }
}

async function cancelAction(confirmationId: number) {
  try {
    await assistantStore.cancelAssistantAction(tripId.value, confirmationId);
    antdMessage.success("已取消本次操作。");
  } catch {
    antdMessage.error("取消操作失败。");
  }
}

async function clearMessages() {
  if (sending.value) {
    return;
  }
  await assistantStore.clearMessages(tripId.value);
}
</script>

<template>
  <div class="assistant-shell" :class="{ 'assistant-shell--open': panelOpen }">
    <button type="button" class="assistant-toggle" @click="panelOpen = !panelOpen">
      {{ panelOpen ? "收起顾问" : "AI 旅行顾问" }}
    </button>

    <aside v-if="panelOpen" class="assistant-panel">
      <header class="assistant-panel__header">
        <div>
          <h2>AI 旅行顾问</h2>
          <p>{{ itinerary.destination }} · {{ itinerary.trip_id }}</p>
        </div>
        <button type="button" class="assistant-panel__clear" @click="clearMessages">清空</button>
      </header>

      <div ref="messageListRef" class="assistant-panel__messages">
        <div v-if="loading" class="assistant-panel__state">正在加载历史对话...</div>
        <div v-else-if="!messages.length" class="assistant-panel__empty">
          <strong>你好，我是你的 AI 旅行顾问。</strong>
          <p>你可以让我修改行程、解释方案、查询预算，或恢复历史版本。</p>
          <div class="assistant-panel__quick">
            <button
              v-for="question in quickQuestions"
              :key="question"
              type="button"
              @click="sendMessage(question)"
            >
              {{ question }}
            </button>
          </div>
        </div>

        <template v-for="item in messages" :key="item.id">
          <ChatMessage :message="item" />
          <AssistantActionCard
            v-if="confirmationIdFor(item)"
            :confirmation-id="confirmationIdFor(item)!"
            :loading="sending"
            @confirm="confirmAction"
            @cancel="cancelAction"
          />
        </template>

        <div v-if="sending" class="assistant-panel__state">正在处理...</div>
      </div>

      <div v-if="errorText" class="assistant-panel__error">{{ errorText }}</div>

      <footer class="assistant-panel__footer">
        <textarea
          v-model="inputText"
          rows="3"
          placeholder="例如：第二天不要安排博物馆，换成自然景点"
          @keydown.ctrl.enter.prevent="sendMessage()"
        ></textarea>
        <button type="button" :disabled="sending || !inputText.trim()" @click="sendMessage()">
          {{ sending ? "处理中..." : "发送" }}
        </button>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.assistant-shell {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 30;
}

.assistant-toggle {
  border: none;
  border-radius: 999px;
  padding: 12px 18px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #ffffff;
  font-weight: 900;
  box-shadow: 0 18px 45px rgba(37, 99, 235, 0.24);
  cursor: pointer;
}

.assistant-shell--open {
  top: 22px;
  bottom: 22px;
}

.assistant-shell--open .assistant-toggle {
  position: absolute;
  right: 0;
  bottom: 0;
}

.assistant-panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  gap: 12px;
  width: min(420px, calc(100vw - 32px));
  height: calc(100vh - 84px);
  margin-bottom: 58px;
  border: 1px solid rgba(98, 116, 164, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.2);
  overflow: hidden;
}

.assistant-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  background: #f8faff;
  border-bottom: 1px solid rgba(98, 116, 164, 0.1);
}

.assistant-panel__header h2 {
  margin: 0;
  color: #263a75;
  font-size: 18px;
}

.assistant-panel__header p {
  margin: 4px 0 0;
  color: #667085;
  font-size: 12px;
  word-break: break-all;
}

.assistant-panel__clear {
  align-self: start;
  border: none;
  border-radius: 10px;
  padding: 7px 10px;
  background: rgba(15, 23, 42, 0.06);
  color: #475467;
  font-weight: 800;
  cursor: pointer;
}

.assistant-panel__messages {
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 16px;
  overflow-y: auto;
}

.assistant-panel__empty,
.assistant-panel__state,
.assistant-panel__error {
  border-radius: 14px;
  padding: 12px;
  background: #f8faff;
  color: #667085;
  line-height: 1.65;
}

.assistant-panel__empty strong {
  color: #263a75;
}

.assistant-panel__empty p {
  margin: 6px 0 12px;
}

.assistant-panel__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.assistant-panel__quick button {
  border: none;
  border-radius: 999px;
  padding: 7px 10px;
  background: rgba(37, 99, 235, 0.1);
  color: #2655c8;
  font-weight: 700;
  cursor: pointer;
}

.assistant-panel__error {
  margin: 0 16px;
  background: rgba(239, 68, 68, 0.1);
  color: #b42318;
}

.assistant-panel__footer {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-top: 1px solid rgba(98, 116, 164, 0.1);
}

.assistant-panel__footer textarea {
  width: 100%;
  resize: vertical;
  min-height: 76px;
  border: 1px solid rgba(98, 116, 164, 0.18);
  border-radius: 14px;
  padding: 10px 12px;
  color: #344054;
  font: inherit;
  line-height: 1.6;
  outline: none;
}

.assistant-panel__footer textarea:focus {
  border-color: rgba(37, 99, 235, 0.55);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.assistant-panel__footer button {
  border: none;
  border-radius: 14px;
  padding: 11px 14px;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  color: #ffffff;
  font-weight: 900;
  cursor: pointer;
}

.assistant-panel__footer button:disabled {
  opacity: 0.6;
  cursor: wait;
}

@media (max-width: 720px) {
  .assistant-shell {
    right: 12px;
    bottom: 12px;
  }

  .assistant-shell--open {
    top: 12px;
    bottom: 12px;
  }

  .assistant-panel {
    height: calc(100vh - 72px);
  }
}
</style>
