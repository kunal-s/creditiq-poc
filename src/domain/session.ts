import { useSyncExternalStore } from "react";
import { api } from "@/api/client";
import type { SessionUser } from "@/api/types";

const STORAGE_KEY = "creditiq.session";

type SessionState = { token: string; user: SessionUser } | null;

let state: SessionState = null;
let hydrated = false;
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

function hydrate() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) state = JSON.parse(raw) as SessionState;
  } catch {
    state = null;
  }
}

function persist() {
  if (typeof window === "undefined") return;
  try {
    if (state) window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Private browsing / storage blocked: session just won't survive reload.
  }
}

export async function signIn(email: string, password: string) {
  const { token, user } = await api.login(email, password);
  state = { token, user };
  persist();
  notify();
}

export async function signOut() {
  if (state) await api.logout(state.token).catch(() => undefined);
  state = null;
  persist();
  notify();
}

export function getToken(): string | null {
  hydrate();
  return state?.token ?? null;
}

export function useSession() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => {
      hydrate();
      return state;
    },
    () => null, // SSR: no session on the server render; the client hydrates and re-renders.
  );
}
