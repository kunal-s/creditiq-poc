import { useSyncExternalStore } from "react";
import { api, ApiError, configureAuth } from "@/api/client";
import type { SessionUser } from "@/api/types";

const STORAGE_KEY = "creditiq.session";

type SessionState = { token: string; user: SessionUser } | null;

let state: SessionState = null;
let hydrated = false;
let revalidated = false;
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
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

function clear() {
  if (!state) return;
  state = null;
  persist();
  notify();
}

configureAuth(() => state?.token ?? null, clear);

function hydrate() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) state = JSON.parse(raw) as SessionState;
  } catch {
    state = null;
  }
  // A stored token may have expired or been signed out elsewhere: confirm it
  // once with the server and refresh the user (roles and permissions).
  if (state && !revalidated) {
    revalidated = true;
    api
      .session()
      .then((user) => {
        if (state) {
          state = { token: state.token, user };
          persist();
          notify();
        }
      })
      // Only a rejected session signs out; a failed request keeps the
      // stored one (the next 401 from any endpoint clears it anyway).
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) clear();
      });
  }
}

export async function signIn(email: string, password: string) {
  const { token, user } = await api.login(email, password);
  state = { token, user };
  revalidated = true;
  persist();
  notify();
}

export async function signOut() {
  if (state) await api.logout().catch(() => undefined);
  clear();
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

/** Whether the signed-in user's role includes a permission (re-renders on change). */
export function useCan(permission: string): boolean {
  return useSession()?.user.permissions.includes(permission) ?? false;
}

export function can(permission: string): boolean {
  return state?.user.permissions.includes(permission) ?? false;
}
