import api from "./api";
import type {
  AssistantMessagePayload,
  AssistantMessageResponse,
  ConversationClearResponse,
  ConversationMessagesResponse,
} from "../types";


export async function sendAssistantMessage(
  payload: AssistantMessagePayload,
): Promise<AssistantMessageResponse> {
  const response = await api.post<AssistantMessageResponse>("/assistant/message", payload);
  return response.data;
}


export async function getTripMessages(tripId: string): Promise<ConversationMessagesResponse> {
  const response = await api.get<ConversationMessagesResponse>(
    `/assistant/trips/${encodeURIComponent(tripId)}/messages`,
  );
  return response.data;
}


export async function clearTripMessages(tripId: string): Promise<ConversationClearResponse> {
  const response = await api.delete<ConversationClearResponse>(
    `/assistant/trips/${encodeURIComponent(tripId)}/messages`,
  );
  return response.data;
}
