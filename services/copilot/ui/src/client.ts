import { asAction, asFormat, asTurnResult, parseSse } from "./sse.ts";
import type { ChatMessage, ErrorKey, PendingAction, SourceRef, Terminal, TurnResult } from "./types.ts";

export class ChatError extends Error {
  readonly key: ErrorKey;
  readonly status: number | undefined;
  constructor(key: ErrorKey, status?: number) {
    super(key);
    this.key = key;
    this.status = status;
  }
}

export interface SendOptions {
  endpoint: string;
  token: string | null;
  message: string;
  sessionId: string | null;
  context: Record<string, string>;
  signal?: AbortSignal;
  onSession?: (sessionId: string) => void;
}

const fail = (status: number): ChatError =>
  new ChatError(status === 401 ? "signedOut" : status === 422 ? "tooLong" : "unavailable", status);

/** One turn: POST the message, read the events, return the result. Throws ChatError. */
export async function sendTurn(o: SendOptions): Promise<TurnResult> {
  let response: Response;
  try {
    response = await fetch(`${o.endpoint}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(o.token ? { Authorization: `Bearer ${o.token}` } : {}) },
      body: JSON.stringify({ message: o.message, session_id: o.sessionId, context: o.context }),
      ...(o.signal ? { signal: o.signal } : {}),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ChatError("network");
  }
  if (!response.ok || !response.body) throw fail(response.status);
  try {
    for await (const { event, data } of parseSse(response.body)) {
      if (event === "session") {
        const id = (data as { session_id?: unknown }).session_id;
        if (typeof id === "string") o.onSession?.(id);
      } else if (event === "result") {
        const result = asTurnResult(data);
        if (result) return result;
      } else if (event === "error") {
        throw new ChatError("unavailable");
      }
    }
  } catch (e) {
    if (e instanceof ChatError || (e instanceof DOMException && e.name === "AbortError")) throw e;
    throw new ChatError("network");
  }
  throw new ChatError("unavailable");
}

export interface ActionReply {
  terminal: Terminal;
  text: string;
  sources: SourceRef[];
  done: boolean;
}

/** The action stays open (the user can fix the values and press again) when the service refuses the values. */
export class ActionRefused extends Error {
  constructor(message: string) {
    super(message);
  }
}

async function post(o: { endpoint: string; token: string | null; path: string; body: unknown; signal?: AbortSignal }): Promise<ActionReply> {
  let response: Response;
  try {
    response = await fetch(`${o.endpoint}${o.path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(o.token ? { Authorization: `Bearer ${o.token}` } : {}) },
      body: JSON.stringify(o.body),
      ...(o.signal ? { signal: o.signal } : {}),
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ChatError("network");
  }
  if (response.status === 422 || response.status === 503) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      /* no readable reason: the card falls back to its generic message */
    }
    throw new ActionRefused(detail);
  }
  if (!response.ok) throw fail(response.status);
  const d = (await response.json()) as Record<string, unknown>;
  return {
    terminal: d["terminal"] as Terminal,
    text: String(d["text"] ?? ""),
    sources: Array.isArray(d["sources"]) ? (d["sources"] as SourceRef[]) : [],
    done: d["done"] === true,
  };
}

export const confirmAction = (o: { endpoint: string; token: string | null; sessionId: string; actionId: string; context: Record<string, string>; values: Record<string, string>; signal?: AbortSignal }) =>
  post({ endpoint: o.endpoint, token: o.token, path: `/actions/${encodeURIComponent(o.actionId)}/confirm`, body: { session_id: o.sessionId, context: o.context, values: o.values }, ...(o.signal ? { signal: o.signal } : {}) });

export const cancelAction = (o: { endpoint: string; token: string | null; sessionId: string; actionId: string; signal?: AbortSignal }) =>
  post({ endpoint: o.endpoint, token: o.token, path: `/actions/${encodeURIComponent(o.actionId)}/cancel`, body: { session_id: o.sessionId }, ...(o.signal ? { signal: o.signal } : {}) });

/** The caller's own transcript and the action still waiting for them, or null when the session no longer exists. */
export async function loadTranscript(
  endpoint: string,
  token: string | null,
  sessionId: string,
  signal?: AbortSignal,
): Promise<{ messages: ChatMessage[]; action: PendingAction | null } | null> {
  try {
    const response = await fetch(`${endpoint}/sessions/${encodeURIComponent(sessionId)}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      ...(signal ? { signal } : {}),
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { messages?: Record<string, unknown>[]; action?: unknown };
    const messages: ChatMessage[] = (body.messages ?? []).map((m, i) => ({
      id: `h${i}`,
      role: m["role"] === "user" ? "user" : "assistant",
      text: String(m["text"] ?? ""),
      ...(typeof m["terminal"] === "string" ? { terminal: m["terminal"] as Terminal } : {}),
      ...(Array.isArray(m["columns"]) ? { columns: m["columns"] as string[] } : {}),
      ...(Array.isArray(m["rows"]) ? { rows: m["rows"] as Record<string, string>[] } : {}),
      ...(Array.isArray(m["sources"]) ? { sources: m["sources"] as SourceRef[] } : {}),
      format: asFormat(m["format"]),
      ...(Array.isArray(m["follow_ups"])
        ? { followUps: (m["follow_ups"] as unknown[]).filter((f): f is string => typeof f === "string") }
        : {}),
      ...(m["done"] === true ? { done: true } : {}),
    }));
    return { messages, action: asAction(body.action) };
  } catch {
    return null;
  }
}
