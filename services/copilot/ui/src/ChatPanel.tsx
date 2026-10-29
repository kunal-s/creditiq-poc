import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { useCopilotChat } from "./useCopilotChat.ts";
import type { ChatLabels, ChatMessage, PendingAction, Tone } from "./types.ts";

export interface ChatPanelProps {
  endpoint: string;
  getToken: () => string | null;
  context: Record<string, string>;
  labels: ChatLabels;
  /** Prompts offered above an empty conversation. */
  suggestions?: string[];
  storageKey?: string;
  className?: string;
  /** Shows a close button in the header; the host decides what closing means. */
  onClose?: () => void;
  /** Focus the message box when the panel appears. */
  autoFocus?: boolean;
  /** What the assistant is talking about (for example the case), shown under the title. */
  contextLabel?: string;
  /** Values (lower case) shown as coloured chips in result cards, for example a status word. */
  tones?: Record<string, Tone>;
}

const Icon = ({ children, size = 16 }: { children: ReactNode; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
    {children}
  </svg>
);
const Spark = () => (
  <Icon>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
    <path d="M19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7L19 16z" />
  </Icon>
);
const Close = () => (
  <Icon>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
);
const Plus = () => (
  <Icon size={14}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
const Arrow = () => (
  <Icon>
    <path d="M12 19V5M5 12l7-7 7 7" />
  </Icon>
);
const Chevron = () => (
  <Icon size={14}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);
const Check = () => (
  <Icon>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
);
const Copy = () => (
  <Icon size={13}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M5 15V6a2 2 0 012-2h9" />
  </Icon>
);
const Mail = () => (
  <Icon size={14}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 7l9 6 9-6" />
  </Icon>
);

const composer =
  "max-h-[132px] min-h-[1.5rem] flex-1 resize-none bg-transparent py-0.5 text-[13px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground";

const TONE: Record<Tone, string> = {
  danger: "bg-critical-soft text-critical",
  warning: "bg-flag-soft text-flag-foreground",
  success: "bg-positive-soft text-positive",
  neutral: "bg-muted text-muted-foreground",
};

/** Rows as stacked cards: the first column is the title and the rest are labelled lines, so nothing is clipped at any width. */
function Rows({ message, labels, tones }: { message: ChatMessage; labels: ChatLabels; tones: Record<string, Tone> }) {
  const columns = message.columns ?? [];
  const rows = message.rows ?? [];
  const [title, ...rest] = columns;
  if (!title || rows.length === 0) return null;
  return (
    <ul className="mt-2.5 flex flex-col gap-2" data-testid="copilot-rows">
      {rows.map((row, i) => (
        <li key={i} data-testid="copilot-row" className="rounded-lg border border-border bg-surface px-3 py-2.5">
          <p className="break-words text-[12.5px] font-medium leading-snug text-foreground">{row[title] ?? ""}</p>
          <dl className="mt-1.5 flex flex-col gap-1 text-[12px] leading-snug">
            {rest.map((c) => (
              <div key={c} className="flex gap-2.5">
                <dt className="w-14 shrink-0 pt-px text-[10.5px] uppercase tracking-wide text-muted-foreground">{labels.columns[c] ?? c}</dt>
                <dd className="min-w-0 flex-1 break-words text-foreground/80">
                  {tones[(row[c] ?? "").toLowerCase()] ? (
                    <span className={"inline-block rounded px-1.5 py-px text-[11px] font-medium " + TONE[tones[(row[c] ?? "").toLowerCase()] as Tone]}>{row[c]}</span>
                  ) : (
                    (row[c] ?? "")
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  );
}

/** Plain text with paragraphs, "- " lists and **bold**, built as elements: nothing is ever inserted as HTML. */
function Rich({ text }: { text: string }) {
  const inline = (line: string) =>
    line.split(/(\*\*[^*]+\*\*)/g).map((part, i) => (part.startsWith("**") && part.endsWith("**") && part.length > 4 ? <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong> : part));
  return (
    <div className="space-y-2">
      {text.split(/\n{2,}/).map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*[-*•] /.test(l))) {
          return (
            <ul key={i} className="list-disc space-y-1 pl-4">
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*•] /, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {inline(l)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function CopyButton({ text, labels }: { text: string; labels: ChatLabels }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(
          () => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          },
          () => undefined,
        );
      }}
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {done ? <Check /> : <Copy />}
      {done ? labels.copied : labels.copy}
    </button>
  );
}

/** A drafted message: the first line is its status, the rest is what would be sent. */
function Draft({ text, labels }: { text: string; labels: ChatLabels }) {
  const [head, ...rest] = text.split("\n");
  const body = rest.join("\n").trim();
  return (
    <div data-testid="copilot-draft" className="overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex items-center justify-between gap-2 border-b border-border bg-muted/50 px-3 py-1.5">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          <Mail />
          {head}
        </span>
        <CopyButton text={body} labels={labels} />
      </div>
      <p className="whitespace-pre-wrap break-words px-3 py-2.5 text-[12.5px] leading-relaxed text-foreground">{body}</p>
    </div>
  );
}

function Bubble({ message, labels, tones }: { message: ChatMessage; labels: ChatLabels; tones: Record<string, Tone> }) {
  const mine = message.role === "user";
  if (mine) {
    return (
      <li className="flex justify-end motion-safe:animate-copilot-in">
        <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-[13px] leading-relaxed text-primary-foreground shadow-sm">
          {message.text}
        </p>
      </li>
    );
  }
  const refused = message.terminal === "cannot_do";
  if (message.done) {
    return (
      <li className="flex items-start gap-2.5 motion-safe:animate-copilot-in">
        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-positive-soft text-positive">
          <Check />
        </span>
        <p data-testid="copilot-done" className="min-w-0 flex-1 break-words rounded-lg border border-positive/30 bg-positive-soft/60 px-3 py-2 text-[13px] leading-relaxed text-foreground">{message.text}</p>
      </li>
    );
  }
  const draft = message.format === "draft";
  return (
    <li className="flex items-start gap-2.5 motion-safe:animate-copilot-in">
      <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
        <Spark />
      </span>
      <div className="min-w-0 flex-1">
        {draft ? (
          <Draft text={message.text} labels={labels} />
        ) : (
          <div className={"text-[13px] leading-relaxed " + (refused ? "text-muted-foreground" : "text-foreground")}>
            <Rich text={message.text} />
          </div>
        )}
        <Rows message={message} labels={labels} tones={tones} />
        {message.sources && message.sources.length > 0 && (
          <p className="mt-2 text-[11px] text-muted-foreground">
            {labels.sources}: {[...new Set(message.sources.map((s) => s.tool))].join(", ")}
          </p>
        )}
      </div>
    </li>
  );
}

function Typing({ label }: { label: string }) {
  return (
    <li role="status" className="flex items-center gap-2.5">
      <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
        <Spark />
      </span>
      <span className="flex items-center gap-1" aria-label={label}>
        {[0, 150, 300].map((d) => (
          <span key={d} style={{ animationDelay: `${d}ms` }} className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 motion-safe:animate-bounce" />
        ))}
        <span className="sr-only">{label}</span>
      </span>
    </li>
  );
}

/** The values the user is asked to check before an action runs, laid out like the message they will send. */
function ActionCard({
  action,
  labels,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  action: PendingAction;
  labels: ChatLabels;
  busy: boolean;
  error: string | null;
  onConfirm: (values: Record<string, string>) => void;
  onCancel: () => void;
}) {
  const [values, setValues] = useState(action.fields);
  useEffect(() => setValues(action.fields), [action]);
  const keys = Object.keys(action.fields);
  const first = useRef<HTMLInputElement>(null);
  useEffect(() => first.current?.focus(), [action.id]);
  return (
    <form
      data-testid="copilot-action"
      aria-label={labels.action.confirm}
      onSubmit={(e) => {
        e.preventDefault();
        if (!busy) onConfirm(values);
      }}
      className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm"
    >
      <div className="divide-y divide-border">
        {keys.map((k, i) => {
          const label = labels.action.fields[k] ?? k;
          const original = action.fields[k] ?? "";
          const long = original.includes("\n") || original.length > 80;
          const set = (v: string) => setValues({ ...values, [k]: v });
          return (
            <label key={k} className="flex items-start gap-3 px-3 py-2">
              <span className="w-14 shrink-0 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
              {long ? (
                <textarea
                  aria-label={label}
                  rows={Math.min(14, Math.max(5, original.split("\n").length + 1))}
                  className="flex-1 resize-y rounded-md border-0 bg-transparent px-0 py-1.5 text-[13px] leading-relaxed text-foreground outline-none focus-visible:ring-0 disabled:opacity-60"
                  value={values[k] ?? ""}
                  disabled={busy}
                  onChange={(e) => set(e.target.value)}
                />
              ) : (
                <input
                  aria-label={label}
                  ref={i === 0 ? first : undefined}
                  className="flex-1 rounded-md border-0 bg-transparent px-0 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-0 disabled:opacity-60"
                  value={values[k] ?? ""}
                  disabled={busy}
                  onChange={(e) => set(e.target.value)}
                />
              )}
            </label>
          );
        })}
      </div>
      {error !== null && (
        <p role="alert" className="border-t border-destructive/30 bg-destructive/5 px-3 py-2 text-[12px] text-destructive">
          {error || labels.errors.notDone}
        </p>
      )}
      <div className="flex items-center justify-end gap-2 border-t border-border bg-muted/40 px-3 py-2">
        <button type="button" disabled={busy} onClick={onCancel} className="rounded-md px-3 py-1.5 text-[12.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50">
          {labels.action.cancel}
        </button>
        <button type="submit" disabled={busy} className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3.5 py-1.5 text-[12.5px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60">
          <Mail />
          {busy ? labels.action.working : labels.action.confirm}
        </button>
      </div>
    </form>
  );
}

export function ChatPanel({ endpoint, getToken, context, labels, suggestions, storageKey, className, onClose, autoFocus, contextLabel, tones = {} }: ChatPanelProps) {
  const { messages, busy, error, send, reset, action, actionBusy, actionError, confirm, cancel } = useCopilotChat({
    endpoint,
    getToken,
    context,
    ...(storageKey ? { storageKey } : {}),
  });
  const [draft, setDraft] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages, busy, error, action]);

  // The message box grows with its text, up to a few lines.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 132)}px`;
  }, [draft]);

  useEffect(() => {
    if (autoFocus) box.current?.focus();
  }, [autoFocus]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (busy || !draft.trim()) return;
    void send(draft);
    setDraft("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };
  const empty = messages.length === 0 && !action;
  const last = messages[messages.length - 1];
  const followUps = last && last.role === "assistant" ? (last.followUps ?? []) : [];

  return (
    <section
      aria-label={labels.title}
      data-testid="copilot-panel"
      onKeyDown={(e) => {
        if (e.key === "Escape" && onClose && !e.defaultPrevented) onClose();
      }}
      className={"flex h-full min-h-0 flex-col bg-surface text-foreground " + (className ?? "")}
    >
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-3">
        <span className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground">
          <Spark />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[13.5px] font-semibold leading-tight tracking-tight">{labels.title}</h2>
          {contextLabel && <p className="truncate text-[11px] leading-tight text-muted-foreground">{contextLabel}</p>}
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            onClick={reset}
            aria-label={labels.newConversation}
            title={labels.newConversation}
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Plus />
          </button>
        )}
        {onClose && (
          <button type="button" onClick={onClose} aria-label={labels.close} className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <Close />
          </button>
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4">
        {empty && (
          <div className="flex flex-col gap-5 pt-4">
            <div className="flex flex-col items-start gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent text-accent-foreground">
                <Spark />
              </span>
              <p className="text-[13px] leading-relaxed text-muted-foreground">{labels.intro}</p>
            </div>
            {suggestions && suggestions.length > 0 && (
              <ul className="flex flex-col gap-2">
                {suggestions.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void send(s)}
                      className="group flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 text-left text-[13px] transition-colors hover:border-primary/40 hover:bg-accent/50 disabled:opacity-50"
                    >
                      <span>{s}</span>
                      <span className="text-muted-foreground transition-transform group-hover:translate-x-0.5">
                        <Chevron />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <ul role="log" aria-live="polite" aria-relevant="additions" className="flex flex-col gap-4">
          {messages.map((m) => (
            <Bubble key={m.id} message={m} labels={labels} tones={tones} />
          ))}
          {busy && <Typing label={labels.thinking} />}
        </ul>
        {followUps.length > 0 && !busy && !action && (
          <ul className="mt-3 flex flex-wrap gap-2" style={{ paddingLeft: 34 }}>
            {followUps.map((f) => (
              <li key={f}>
                <button
                  type="button"
                  onClick={() => void send(f)}
                  className="rounded-full border border-primary/30 bg-accent/40 px-3 py-1.5 text-[12.5px] text-accent-foreground transition-colors hover:bg-accent motion-safe:animate-copilot-in"
                >
                  {f}
                </button>
              </li>
            ))}
          </ul>
        )}
        {action && (
          <div className="mt-4">
            <div className="motion-safe:animate-copilot-in"><ActionCard action={action} labels={labels} busy={actionBusy} error={actionError} onConfirm={confirm} onCancel={cancel} /></div>
          </div>
        )}
        {error && (
          <p role="alert" className="mt-4 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-[12px] text-destructive">
            {labels.errors[error]}
          </p>
        )}
        <div ref={end} />
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-border bg-surface px-3 pb-2.5 pt-3">
        <div className="flex items-end gap-2 rounded-xl border border-input bg-background px-3 py-2 transition-shadow focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30">
          <textarea
            ref={box}
            aria-label={labels.placeholder}
            placeholder={labels.placeholder}
            value={draft}
            rows={1}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            className={composer}
          />
          <button
            type="submit"
            aria-label={labels.send}
            disabled={busy || !draft.trim()}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-30"
          >
            <Arrow />
          </button>
        </div>
        {labels.hint && <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">{labels.hint}</p>}
      </form>
    </section>
  );
}
