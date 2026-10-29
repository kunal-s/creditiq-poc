import type { PendingAction, SseEvent, Terminal, TurnResult } from "./types.ts";

export function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (data.length === 0) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) as unknown };
  } catch {
    return null;
  }
}

/** Server-sent events from a fetch body (EventSource cannot POST or send a bearer token). */
export async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
    for (let i = buffer.indexOf("\n\n"); i >= 0; i = buffer.indexOf("\n\n")) {
      const event = parseBlock(buffer.slice(0, i));
      buffer = buffer.slice(i + 2);
      if (event) yield event;
    }
  }
  const last = parseBlock(buffer.trim());
  if (last) yield last;
}

const TERMINALS: Terminal[] = ["answer", "ask_user", "cannot_do", "confirm"];

export function asFormat(v: unknown): "text" | "table" | "draft" {
  return v === "table" || v === "draft" ? v : "text";
}

/** A pending action from the service, or null when it is absent or not shaped as expected. */
export function asAction(data: unknown): PendingAction | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (typeof d["id"] !== "string" || typeof d["fields"] !== "object" || d["fields"] === null) return null;
  const fields: Record<string, string> = {};
  for (const [k, v] of Object.entries(d["fields"])) {
    if (typeof v !== "string") return null;
    fields[k] = v;
  }
  return { id: d["id"], fields };
}

export function asTurnResult(data: unknown): TurnResult | null {
  if (typeof data !== "object" || data === null) return null;
  const d = data as Record<string, unknown>;
  if (typeof d["text"] !== "string" || typeof d["session_id"] !== "string") return null;
  if (!TERMINALS.includes(d["terminal"] as Terminal)) return null;
  const list = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
  return {
    session_id: d["session_id"],
    terminal: d["terminal"] as Terminal,
    text: d["text"],
    columns: list<string>(d["columns"]),
    rows: list<Record<string, string>>(d["rows"]),
    sources: list(d["sources"]),
    action: asAction(d["action"]),
    format: asFormat(d["format"]),
    followUps: list<unknown>(d["follow_ups"]).filter((f): f is string => typeof f === "string"),
  };
}
