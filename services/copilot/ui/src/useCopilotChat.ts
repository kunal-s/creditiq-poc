import { useCallback, useEffect, useRef, useState } from "react";
import { ActionRefused, cancelAction, ChatError, confirmAction, loadTranscript, sendTurn } from "./client.ts";
import type { ChatMessage, ErrorKey, PendingAction } from "./types.ts";

export interface UseCopilotChatOptions {
  endpoint: string;
  getToken: () => string | null;
  /** What is open in the host screen (for example the case). A different context is a different conversation. */
  context: Record<string, string>;
  /** Remember the session id in this tab under this key; leave out to keep nothing. */
  storageKey?: string;
}

const stable = (o: Record<string, string>): string => JSON.stringify(Object.entries(o).sort(([a], [b]) => a.localeCompare(b)));

function remembered(key: string | null, set?: string | null): string | null {
  if (!key) return null;
  try {
    if (set === null) sessionStorage.removeItem(key);
    else if (set !== undefined) sessionStorage.setItem(key, set);
    return sessionStorage.getItem(key);
  } catch {
    return null; // private windows and blocked storage: carry on without it
  }
}

export function useCopilotChat({ endpoint, getToken, context, storageKey }: UseCopilotChatOptions) {
  const contextKey = stable(context);
  const slot = storageKey ? `${storageKey}:${contextKey}` : null;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorKey | null>(null);
  const [action, setAction] = useState<PendingAction | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  /** Why the service refused the values on the card; shown on the card so the user can fix them. */
  const [actionError, setActionError] = useState<string | null>(null);
  const sessionId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const counter = useRef(0);
  const contextRef = useRef(context);
  contextRef.current = context;
  const tokenRef = useRef(getToken);
  tokenRef.current = getToken;

  // Open (or restore) the conversation for this context.
  useEffect(() => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setMessages([]);
    setError(null);
    setBusy(false);
    setAction(null);
    setActionError(null);
    sessionId.current = remembered(slot);
    const id = sessionId.current;
    if (id) {
      void loadTranscript(endpoint, tokenRef.current(), id, controller.signal).then((history) => {
        if (controller.signal.aborted) return;
        if (history) {
          setMessages(history.messages);
          setAction(history.action);
        } else {
          sessionId.current = null;
          remembered(slot, null);
        }
      });
    }
    return () => controller.abort();
  }, [endpoint, slot]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message) return;
      const controller = new AbortController();
      abort.current = controller;
      setError(null);
      setBusy(true);
      setMessages((m) => [...m, { id: `u${++counter.current}`, role: "user", text: message }]);
      const attempt = async (id: string | null) =>
        sendTurn({
          endpoint,
          token: tokenRef.current(),
          message,
          sessionId: id,
          context: contextRef.current,
          signal: controller.signal,
          onSession: (s) => {
            sessionId.current = s;
            remembered(slot, s);
          },
        });
      try {
        let result;
        try {
          result = await attempt(sessionId.current);
        } catch (e) {
          if (!(e instanceof ChatError && e.status === 404 && sessionId.current)) throw e;
          sessionId.current = null; // the stored session is gone: start again once
          remembered(slot, null);
          result = await attempt(null);
        }
        if (controller.signal.aborted) return;
        setMessages((m) => [
          ...m,
          {
            id: `a${++counter.current}`,
            role: "assistant",
            text: result.text,
            terminal: result.terminal,
            columns: result.columns,
            rows: result.rows,
            sources: result.sources,
            format: result.format,
            followUps: result.followUps,
          },
        ]);
        if (result.action) {
          setAction(result.action);
          setActionError(null);
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setError(e instanceof ChatError ? e.key : "network");
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    },
    [endpoint, slot],
  );

  /** Run or drop the action on the card. Both end with a message from the service. */
  const settle = useCallback(
    async (run: (id: string, session: string, token: string | null) => Promise<{ terminal: ChatMessage["terminal"]; text: string; sources: ChatMessage["sources"]; done: boolean }>) => {
      if (!action || !sessionId.current) return;
      setActionBusy(true);
      setActionError(null);
      try {
        const reply = await run(action.id, sessionId.current, tokenRef.current());
        setMessages((m) => [...m, { id: `a${++counter.current}`, role: "assistant", text: reply.text, ...(reply.terminal ? { terminal: reply.terminal } : {}), ...(reply.sources ? { sources: reply.sources } : {}), ...(reply.done ? { done: true } : {}) }]);
        setAction(null);
      } catch (e) {
        if (e instanceof ActionRefused) setActionError(e.message || "");
        else setError(e instanceof ChatError ? e.key : "network");
      } finally {
        setActionBusy(false);
      }
    },
    [action, endpoint],
  );

  const confirm = useCallback(
    (values: Record<string, string>) =>
      settle((actionId, sessionId_, token) => confirmAction({ endpoint, token, sessionId: sessionId_, actionId, context: contextRef.current, values })),
    [settle, endpoint],
  );
  const cancel = useCallback(
    () => settle((actionId, sessionId_, token) => cancelAction({ endpoint, token, sessionId: sessionId_, actionId })),
    [settle, endpoint],
  );

  const reset = useCallback(() => {
    abort.current?.abort();
    sessionId.current = null;
    remembered(slot, null);
    setMessages([]);
    setError(null);
    setBusy(false);
    setAction(null);
    setActionError(null);
  }, [slot]);

  return { messages, busy, error, send, reset, action, actionBusy, actionError, confirm, cancel };
}
