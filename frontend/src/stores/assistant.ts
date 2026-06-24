import { computed, reactive, ref } from "vue";
import { defineStore } from "pinia";

import {
  clearTripMessages,
  getTripMessages,
  sendAssistantMessage as postAssistantMessage,
} from "../services/assistant";
import type {
  AssistantMessageResponse,
  ConversationMessageItem,
} from "../types";


function createLocalUserMessage(tripId: string, content: string): ConversationMessageItem {
  return {
    id: `local_${Date.now()}_${Math.random().toString(16).slice(2)}`,
    conversation_id: `local_${tripId}`,
    role: "user",
    message_type: "text",
    content,
    structured_payload: {},
    created_at: new Date().toISOString(),
    optimistic: true,
  };
}


export const useAssistantStore = defineStore("assistant", () => {
  const messagesByTrip = reactive<Record<string, ConversationMessageItem[]>>({});
  const loadingTrips = reactive<Record<string, boolean>>({});
  const sendingTrips = reactive<Record<string, boolean>>({});
  const errorsByTrip = reactive<Record<string, string>>({});
  const activeTripId = ref<string | null>(null);

  const activeMessages = computed(() => {
    if (!activeTripId.value) {
      return [];
    }
    return messagesByTrip[activeTripId.value] || [];
  });

  function ensureTrip(tripId: string) {
    if (!messagesByTrip[tripId]) {
      messagesByTrip[tripId] = [];
    }
  }

  async function loadMessages(tripId: string) {
    activeTripId.value = tripId;
    ensureTrip(tripId);
    loadingTrips[tripId] = true;
    errorsByTrip[tripId] = "";
    try {
      const response = await getTripMessages(tripId);
      messagesByTrip[tripId] = response.items;
    } catch {
      errorsByTrip[tripId] = "聊天记录加载失败。";
    } finally {
      loadingTrips[tripId] = false;
    }
  }

  async function sendAssistantMessage(
    tripId: string,
    message: string,
    candidateId?: string | null,
  ): Promise<AssistantMessageResponse> {
    ensureTrip(tripId);
    const localMessage = createLocalUserMessage(tripId, message);
    messagesByTrip[tripId] = [...messagesByTrip[tripId], localMessage];
    sendingTrips[tripId] = true;
    errorsByTrip[tripId] = "";
    try {
      const response = await postAssistantMessage({
        trip_id: tripId,
        message,
        candidate_id: candidateId || null,
      });
      if (response.message) {
        messagesByTrip[tripId] = [...messagesByTrip[tripId], response.message];
      }
      return response;
    } catch (error) {
      errorsByTrip[tripId] = "AI 旅行顾问暂时无法处理，请稍后再试。";
      throw error;
    } finally {
      sendingTrips[tripId] = false;
    }
  }

  async function confirmAssistantAction(
    tripId: string,
    confirmationId: number,
  ): Promise<AssistantMessageResponse> {
    return sendAssistantAction(tripId, confirmationId, "confirmed", "确认执行");
  }

  async function cancelAssistantAction(
    tripId: string,
    confirmationId: number,
  ): Promise<AssistantMessageResponse> {
    return sendAssistantAction(tripId, confirmationId, "rejected", "取消本次操作");
  }

  async function sendAssistantAction(
    tripId: string,
    confirmationId: number,
    action: "confirmed" | "rejected",
    label: string,
  ): Promise<AssistantMessageResponse> {
    ensureTrip(tripId);
    messagesByTrip[tripId] = [...messagesByTrip[tripId], createLocalUserMessage(tripId, label)];
    sendingTrips[tripId] = true;
    errorsByTrip[tripId] = "";
    try {
      const response = await postAssistantMessage({
        trip_id: tripId,
        message: label,
        confirmation_id: confirmationId,
        action,
      });
      if (response.message) {
        messagesByTrip[tripId] = [...messagesByTrip[tripId], response.message];
      }
      return response;
    } catch (error) {
      errorsByTrip[tripId] = "确认操作失败，请稍后再试。";
      throw error;
    } finally {
      sendingTrips[tripId] = false;
    }
  }

  async function clearMessages(tripId: string) {
    await clearTripMessages(tripId);
    messagesByTrip[tripId] = [];
  }

  function isLoading(tripId: string) {
    return Boolean(loadingTrips[tripId]);
  }

  function isSending(tripId: string) {
    return Boolean(sendingTrips[tripId]);
  }

  function errorForTrip(tripId: string) {
    return errorsByTrip[tripId] || "";
  }

  return {
    activeTripId,
    activeMessages,
    messagesByTrip,
    loadMessages,
    sendAssistantMessage,
    confirmAssistantAction,
    cancelAssistantAction,
    clearMessages,
    isLoading,
    isSending,
    errorForTrip,
  };
});
