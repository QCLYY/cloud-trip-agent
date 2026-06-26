import axios from "axios";

import type {
  AuthRequestPayload,
  AuthUser,
  BrowserNavigatePayload,
  BrowserNavigateResponse,
  HumanConfirmationItem,
  HumanConfirmationListResponse,
  Itinerary,
  TokenResponse,
  TripDetailResponse,
  TripEditPayload,
  TripListResponse,
  TripRequestPayload,
  TripSaveResponse,
  TripVersionCompareResponse,
  TripVersionDetailResponse,
  TripVersionListResponse,
  TripVersionRestoreResponse,
  UserMemoryResponse,
  WeatherForecastResponse,
} from "../types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

type TokenProvider = () => string | null;
type AuthFailureHandler = () => void;

let tokenProvider: TokenProvider | null = null;
let authFailureHandler: AuthFailureHandler | null = null;

export function setTokenProvider(provider: TokenProvider) {
  tokenProvider = provider;
}

export function setAuthFailureHandler(handler: AuthFailureHandler) {
  authFailureHandler = handler;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = tokenProvider?.();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      authFailureHandler?.();
    }
    return Promise.reject(error);
  },
);

export async function registerUser(payload: AuthRequestPayload): Promise<AuthUser> {
  const response = await api.post<AuthUser>("/auth/register", payload);
  return response.data;
}

export async function loginUser(payload: AuthRequestPayload): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>("/auth/login", payload);
  return response.data;
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await api.get<AuthUser>("/auth/me");
  return response.data;
}

export async function generateTrip(payload: TripRequestPayload): Promise<Itinerary> {
  const response = await api.post<Itinerary>("/trip/generate", payload);
  return response.data;
}

export async function editTrip(payload: TripEditPayload): Promise<Itinerary> {
  const response = await api.post<Itinerary>("/trip/edit", payload);
  return response.data;
}

export async function saveTrip(
  itinerary: Itinerary,
  changeType = "manual_save",
): Promise<TripSaveResponse> {
  const response = await api.post<TripSaveResponse>("/trip/save", {
    trip_id: itinerary.trip_id,
    itinerary,
    change_type: changeType,
  });
  return response.data;
}

export async function listTrips(): Promise<TripListResponse> {
  const response = await api.get<TripListResponse>("/trip");
  return response.data;
}

export async function getTripDetail(tripId: string): Promise<TripDetailResponse> {
  const response = await api.get<TripDetailResponse>(
    `/trip/${encodeURIComponent(tripId)}`,
  );
  return response.data;
}

export async function deleteTrip(tripId: string): Promise<void> {
  await api.delete(`/trip/${encodeURIComponent(tripId)}`);
}

export async function listTripVersions(tripId: string): Promise<TripVersionListResponse> {
  const response = await api.get<TripVersionListResponse>(
    `/trip/${encodeURIComponent(tripId)}/versions`,
  );
  return response.data;
}

export async function getTripVersion(
  tripId: string,
  versionNumber: number,
): Promise<TripVersionDetailResponse> {
  const response = await api.get<TripVersionDetailResponse>(
    `/trip/${encodeURIComponent(tripId)}/versions/${versionNumber}`,
  );
  return response.data;
}

export async function compareTripVersions(
  tripId: string,
  fromVersion: number,
  toVersion: number,
): Promise<TripVersionCompareResponse> {
  const response = await api.get<TripVersionCompareResponse>(
    `/trip/${encodeURIComponent(tripId)}/versions/compare`,
    { params: { from_version: fromVersion, to_version: toVersion } },
  );
  return response.data;
}

export async function restoreTripVersion(
  tripId: string,
  versionNumber: number,
): Promise<TripVersionRestoreResponse> {
  const response = await api.post<TripVersionRestoreResponse>(
    `/trip/${encodeURIComponent(tripId)}/versions/${versionNumber}/restore`,
  );
  return response.data;
}

export async function fetchMemory(): Promise<UserMemoryResponse> {
  const response = await api.get<UserMemoryResponse>("/memory");
  return response.data;
}

export async function updateMemoryEnabled(enabled: boolean): Promise<UserMemoryResponse> {
  const response = await api.put<UserMemoryResponse>("/memory", { enabled });
  return response.data;
}

export async function deleteMemory(memoryId: number): Promise<void> {
  await api.delete(`/memory/${memoryId}`);
}

export async function clearMemory(): Promise<void> {
  await api.delete("/memory");
}

export async function listConfirmations(
  tripId?: string,
): Promise<HumanConfirmationListResponse> {
  const response = await api.get<HumanConfirmationListResponse>("/confirmations", {
    params: tripId ? { trip_id: tripId } : undefined,
  });
  return response.data;
}

export async function createConfirmation(payload: {
  trip_id?: string | null;
  confirmation_type: string;
  payload: Record<string, unknown>;
}): Promise<HumanConfirmationItem> {
  const response = await api.post<HumanConfirmationItem>("/confirmations", payload);
  return response.data;
}

export async function updateConfirmation(
  confirmationId: number,
  action: "confirmed" | "rejected",
): Promise<HumanConfirmationItem> {
  const response = await api.post<HumanConfirmationItem>(`/confirmations/${confirmationId}`, {
    action,
  });
  return response.data;
}

export async function fetchWeatherForecast(city: string): Promise<WeatherForecastResponse> {
  const response = await api.get<WeatherForecastResponse>("/weather/forecast", {
    params: { city },
  });
  return response.data;
}

export async function exportTripMarkdown(tripId: string): Promise<Blob> {
  const response = await api.get<Blob>(
    `/export/${encodeURIComponent(tripId)}/markdown`,
    { responseType: "blob" },
  );
  return response.data;
}

export async function exportTripPdf(tripId: string): Promise<Blob> {
  const response = await api.get<Blob>(
    `/export/${encodeURIComponent(tripId)}/pdf`,
    { responseType: "blob" },
  );
  return response.data;
}

export async function navigateBrowser(
  payload: BrowserNavigatePayload,
): Promise<BrowserNavigateResponse> {
  const response = await api.post<BrowserNavigateResponse>("/browser/navigate", payload);
  return response.data;
}

export default api;
