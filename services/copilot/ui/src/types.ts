/** Everything the panel shows comes from here: the host application supplies the wording. */
export interface ChatLabels {
  title: string;
  placeholder: string;
  send: string;
  newConversation: string;
  close: string;
  copy: string;
  copied: string;
  /** A line under the message box, for example how to send and how to start a new line. */
  hint: string;
  /** Shown above an empty conversation. */
  intro: string;
  thinking: string;
  sources: string;
  /** Table header per column key the service returns; an unlisted key is shown as it comes. */
  columns: Record<string, string>;
  /** The card that asks the user to confirm an action before it runs. */
  action: {
    /** Label per field key the service returns (for example to, subject, body); an unlisted key is shown as it comes. */
    fields: Record<string, string>;
    confirm: string;
    cancel: string;
    working: string;
  };
  errors: {
    signedOut: string;
    unavailable: string;
    network: string;
    tooLong: string;
    notDone: string;
  };
}

export type Terminal = "answer" | "ask_user" | "cannot_do" | "confirm";

/** An action waiting for the user: the values to check and the id it is confirmed under. */
export interface PendingAction {
  id: string;
  fields: Record<string, string>;
}

export interface SourceRef {
  tool: string;
  fetched_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  terminal?: Terminal;
  columns?: string[];
  rows?: Record<string, string>[];
  sources?: SourceRef[];
  /** How to show the text: as a message preview ("draft") or plainly. */
  format?: "text" | "table" | "draft";
  /** Next steps offered under the answer; only the latest message shows them. */
  followUps?: string[];
  /** The message reports an action that has run. */
  done?: boolean;
}

export type ErrorKey = keyof ChatLabels["errors"];

export interface TurnResult {
  session_id: string;
  terminal: Terminal;
  text: string;
  columns: string[];
  rows: Record<string, string>[];
  sources: SourceRef[];
  action: PendingAction | null;
  format: "text" | "table" | "draft";
  followUps: string[];
}

/** How a value is shown when it matches (compared in lower case): a coloured chip for a status word. */
export type Tone = "danger" | "warning" | "success" | "neutral";

export interface SseEvent {
  event: string;
  data: unknown;
}
