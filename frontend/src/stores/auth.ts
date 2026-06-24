import { computed, ref } from "vue";
import { defineStore } from "pinia";

import { getCurrentUser, loginUser, registerUser } from "../services/api";
import type { AuthRequestPayload, AuthUser } from "../types";


const TOKEN_STORAGE_KEY = "cloud_trip_access_token";


function readStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}


function writeStoredToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }

  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}


export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(readStoredToken());
  const currentUser = ref<AuthUser | null>(null);
  const initialized = ref(false);

  const isAuthenticated = computed(() => Boolean(token.value));

  function setToken(nextToken: string | null) {
    token.value = nextToken;
    writeStoredToken(nextToken);
  }

  function clearSession() {
    setToken(null);
    currentUser.value = null;
    initialized.value = true;
  }

  async function loadCurrentUser(): Promise<AuthUser | null> {
    if (!token.value) {
      currentUser.value = null;
      initialized.value = true;
      return null;
    }

    try {
      currentUser.value = await getCurrentUser();
      return currentUser.value;
    } catch {
      clearSession();
      return null;
    } finally {
      initialized.value = true;
    }
  }

  async function login(payload: AuthRequestPayload) {
    const tokenResponse = await loginUser(payload);
    setToken(tokenResponse.access_token);
    await loadCurrentUser();
  }

  async function register(payload: AuthRequestPayload) {
    await registerUser(payload);
    await login(payload);
  }

  function logout() {
    clearSession();
  }

  return {
    token,
    currentUser,
    initialized,
    isAuthenticated,
    clearSession,
    loadCurrentUser,
    login,
    logout,
    register,
  };
});
