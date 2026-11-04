import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ClipboardPaste,
  Files,
  KeyRound,
  MessageSquareText,
  Paperclip,
  Pencil,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";
import type { CaseProposal, CaseSummary, Meta } from "@/api/types";
import { api, ApiError } from "@/api/client";
import { PageHeader } from "@/components/shell/PageHeader";
import { Panel, Chip } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { ProposedStatusChip } from "@/components/documents/chips";
import { UploadZone } from "@/components/documents/UploadZone";
import { t } from "@/config/terminology";
import { formatInr, useCases, useCreateCase, useMeta, useProposeCase } from "@/domain/cases";
import { errorKind } from "@/domain/errors";
import {
  draftFrom,
  fieldKeys,
  markRuns,
  missingMinimum,
  normalise,
  toCaseCreate,
  unsettled,
  type Draft,
  type Mark,
} from "@/domain/proposal";
import { formatBytes } from "@/domain/documents";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/new")({
  head: () => ({
    meta: [{ title: `${t("page.newApplication.title")} — ${t("tenant.product.name")}` }],
  }),
  component: NewApplication,
});

const inputClass =
  "mt-1 h-9 w-full min-w-0 rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-primary/60 focus:ring-1 focus:ring-ring";

function NewApplication() {
  const navigate = useNavigate();
  const meta = useMeta();
  const propose = useProposeCase();
  const create = useCreateCase();
  const [channel, setChannel] = useState<string>("");
  const [text, setText] = useState("");
  const [ids, setIds] = useState("");
  const [proposal, setProposal] = useState<CaseProposal | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [override, setOverride] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [creating, setCreating] = useState(false);

  const channelId = channel || meta.data?.channels[0]?.id || "";

  // What is read: the message, with any identifiers typed on their own after it.
  const combined = ids.trim()
    ? text.trim()
      ? `${text.trimEnd()}\n${ids.trim()}`
      : ids.trim()
    : text;

  async function read() {
    try {
      setText(combined);
      setIds("");
      const result = await propose.mutateAsync({ channel: channelId, text: combined });
      setProposal(result);
      setDraft(draftFrom(result, meta.data));
      setSelected(null);
      setOverride(false);
      setOverrideReason("");
    } catch {
      // Shown inline from the mutation's error state.
    }
  }

  function discard() {
    setProposal(null);
    setDraft(null);
    setSelected(null);
    setText("");
    setAttachments([]);
    setOverride(false);
    setOverrideReason("");
    propose.reset();
    create.reset();
  }

  async function submit() {
    if (!proposal || !draft) return;
    setCreating(true);
    try {
      const created = await create.mutateAsync(
        toCaseCreate(proposal, draft, channelId, override ? overrideReason.trim() : null, text),
      );
      toast.success(t("newApplication.created", { id: created.id }));
      if (attachments.length > 0) {
        try {
          await api.uploadFiles(created.id, attachments);
        } catch (error) {
          toast(t("newApplication.attachmentsLater"), {
            description: t(`state.${errorKind(error)}.description`),
          });
        }
        // Processing has started: the Overview shows it.
        void navigate({ to: "/appraisals/$caseId", params: { caseId: created.id } });
      } else {
        void navigate({ to: "/appraisals/$caseId/documents", params: { caseId: created.id } });
      }
    } catch (error) {
      // A duplicate found at creation (409) shows as the duplicate warning;
      // anything else is shown inline from the mutation's error state.
      const found = duplicatesIn(error);
      if (found) {
        const known = new Set((proposal.duplicates ?? []).map((d) => d.id));
        setProposal({
          ...proposal,
          duplicates: [...(proposal.duplicates ?? []), ...found.filter((d) => !known.has(d.id))],
        });
        setOverride(false);
      }
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={t("page.newApplication.eyebrow")}
        title={t("page.newApplication.title")}
        purpose={t("page.newApplication.purpose")}
        actions={
          !proposal && (
            <button
              type="button"
              disabled={!combined.trim() || propose.isPending || !channelId}
              onClick={() => void read()}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              <ClipboardPaste className="h-3.5 w-3.5" />
              {propose.isPending ? t("newApplication.reading") : t("newApplication.read")}
            </button>
          )
        }
      />

      <div className="space-y-4 px-4 py-5 sm:px-6">
        {!proposal && (
          <IntakeStart
            text={text}
            onText={setText}
            ids={ids}
            onIds={setIds}
            attachments={attachments}
            onAttach={(files) => setAttachments((prev) => [...prev, ...files])}
            onRemove={(i) => setAttachments((prev) => prev.filter((_, j) => j !== i))}
            channels={meta.data?.channels ?? []}
            channel={channelId}
            onChannel={setChannel}
            error={propose.isError ? propose.error : null}
          />
        )}

        {proposal && draft && (
          <div className="grid gap-4 lg:grid-cols-2">
            <MessagePanel
              text={text}
              proposal={proposal}
              draft={draft}
              selected={selected}
              onEdit={discardProposalKeepText}
            />

            {meta.data ? (
              <ProposedCase
                proposal={proposal}
                draft={draft}
                meta={meta.data}
                selected={selected}
                onSelect={setSelected}
                onChange={setDraft}
              />
            ) : (
              <Panel title={t("newApplication.proposed")}>
                {meta.isError ? (
                  <div className="p-4">
                    <ErrorState error={meta.error} compact />
                  </div>
                ) : (
                  <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
                    {t("newApplication.proposedEmpty")}
                  </p>
                )}
              </Panel>
            )}
          </div>
        )}

        {proposal && draft && meta.data && (
          <>
            {(proposal.duplicates ?? []).length > 0 && (
              <div
                className="rounded border border-flag/40 bg-flag-soft px-4 py-3"
                data-testid="duplicate-warning"
              >
                <div className="flex flex-wrap items-start gap-2 text-[12.5px] text-flag-foreground">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="min-w-0 flex-1 space-y-1.5">
                    {(proposal.duplicates ?? []).map((d) => (
                      <p key={d.id} className="flex flex-wrap items-center gap-2">
                        <span>
                          {t("newApplication.duplicate", { id: d.id, borrower: d.borrower })}
                        </span>
                        <Link
                          to="/appraisals/$caseId"
                          params={{ caseId: d.id }}
                          className="rounded border border-border bg-surface px-2 py-0.5 text-[12px] font-medium text-foreground hover:bg-muted"
                        >
                          {t("newApplication.openIt")}
                        </Link>
                      </p>
                    ))}
                  </div>
                  {!override && (
                    <button
                      type="button"
                      onClick={() => setOverride(true)}
                      className="rounded border border-border bg-surface px-2 py-0.5 text-[12px] font-medium text-foreground hover:bg-muted"
                    >
                      {t("newApplication.createAnyway")}
                    </button>
                  )}
                </div>
                {override && (
                  <label className="mt-2 block">
                    <span className="field-label">{t("newApplication.overrideReason")}</span>
                    <input
                      className={inputClass}
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      data-testid="override-reason"
                    />
                  </label>
                )}
              </div>
            )}

            <Panel
              title={t("newApplication.attachments")}
              subtitle={t("newApplication.attachmentsHelp")}
            >
              <div className="space-y-2 p-4">
                <UploadZone
                  compact
                  onFiles={(files) => setAttachments((prev) => [...prev, ...files])}
                />
                {attachments.length > 0 && (
                  <ul className="space-y-1 text-[12px]" data-testid="attachments">
                    {attachments.map((f, i) => (
                      <li key={`${f.name}-${i}`} className="flex items-center gap-2">
                        <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 flex-1 break-all">{f.name}</span>
                        <span className="text-muted-foreground">{formatBytes(f.size)}</span>
                        <button
                          type="button"
                          aria-label={t("action.remove")}
                          onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))}
                          className="rounded p-0.5 text-muted-foreground hover:bg-muted"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>

            <CreateBar
              proposal={proposal}
              draft={draft}
              meta={meta.data}
              duplicateBlocked={
                (proposal.duplicates ?? []).length > 0 && (!override || !overrideReason.trim())
              }
              creating={creating}
              error={duplicatesIn(create.error) ? null : create.error}
              onDiscard={discard}
              onCreate={() => void submit()}
            />
          </>
        )}
      </div>
    </div>
  );

  function discardProposalKeepText() {
    setProposal(null);
    setDraft(null);
    setSelected(null);
    propose.reset();
  }
}

/** The duplicates a 409 from case creation carries (F-04.5), if any. */
function duplicatesIn(error: unknown): CaseSummary[] | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.detail as { duplicates?: unknown } | null;
  return Array.isArray(detail?.duplicates) ? (detail.duplicates as CaseSummary[]) : null;
}

function MessagePanel({
  text,
  proposal,
  draft,
  selected,
  onEdit,
}: {
  text: string;
  proposal: CaseProposal;
  draft: Draft;
  selected: string | null;
  onEdit: () => void;
}) {
  const selectedRef = useRef<HTMLElement | null>(null);
  const marks = useMemo(() => {
    const out: Mark[] = (proposal.stripped ?? []).map((s) => ({ ...s.span, level: "stripped" }));
    for (const [key, span] of Object.entries(draft.spans)) {
      if (!span) continue;
      out.push({ ...span, level: key === selected ? "selected" : "found" });
    }
    if (selected) {
      for (const c of proposal.fields[selected]?.candidates ?? []) {
        out.push({ ...c.span, level: "candidate" });
      }
    }
    return out;
  }, [draft.spans, proposal.fields, proposal.stripped, selected]);
  const runs = markRuns(text, marks);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selected]);

  return (
    <Panel
      title={t("newApplication.message")}
      subtitle={t("newApplication.messageClickHelp")}
      action={
        <button
          type="button"
          onClick={onEdit}
          className="flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-muted"
        >
          <Pencil className="h-3 w-3" /> {t("newApplication.editMessage")}
        </button>
      }
    >
      <pre
        className="max-h-[520px] overflow-auto whitespace-pre-wrap break-words px-4 py-3 font-sans text-[12.5px] leading-relaxed text-foreground"
        data-testid="message-view"
      >
        {runs.map((run) =>
          run.level ? (
            <mark
              key={run.start}
              ref={
                run.level === "selected"
                  ? (el) => {
                      if (el) selectedRef.current = el;
                    }
                  : undefined
              }
              data-mark={run.level}
              title={run.level === "stripped" ? t("newApplication.strippedHelp") : undefined}
              className={cn(
                "rounded-[2px] text-foreground",
                run.level === "selected" && "bg-primary/25 ring-1 ring-primary",
                run.level === "candidate" && "bg-flag/35 ring-1 ring-flag",
                run.level === "found" && "bg-accent",
                run.level === "stripped" && "bg-transparent text-muted-foreground/60",
              )}
            >
              {run.text}
            </mark>
          ) : (
            <span key={run.start}>{run.text}</span>
          ),
        )}
      </pre>
    </Panel>
  );
}

function ProposedCase({
  proposal,
  draft,
  meta,
  selected,
  onSelect,
  onChange,
}: {
  proposal: CaseProposal;
  draft: Draft;
  meta: Meta;
  selected: string | null;
  onSelect: (key: string) => void;
  onChange: (draft: Draft) => void;
}) {
  const keys = fieldKeys(proposal);
  const pending = unsettled(proposal, draft);

  const set = (key: string, value: string, span?: { start: number; end: number } | null) =>
    onChange({
      values: { ...draft.values, [key]: value },
      spans: span !== undefined ? { ...draft.spans, [key]: span } : draft.spans,
      settled: { ...draft.settled, [key]: true },
    });
  const settle = (key: string) =>
    onChange({ ...draft, settled: { ...draft.settled, [key]: true } });

  return (
    <Panel title={t("newApplication.proposed")} testId="proposed-case">
      <ul className="divide-y divide-border">
        {keys.map((key) => {
          const f = proposal.fields[key]!;
          const value = draft.values[key] ?? "";
          const needs = pending.includes(key);
          return (
            <li
              key={key}
              data-field={key}
              data-testid={`field-${key}`}
              onClick={() => onSelect(key)}
              className={cn(
                "cursor-pointer px-4 py-2.5",
                selected === key ? "bg-primary/5" : "hover:bg-surface-muted/60",
                needs && "border-l-2 border-l-flag",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[12px] font-medium text-muted-foreground">
                  {t(`proposalField.${key}`)}
                </span>
                <span className="flex items-center gap-1.5">
                  {draft.settled[key] && (f.status === "unclear" || f.status === "invalid") && (
                    <Chip tone="positive">
                      <Check className="h-3 w-3" /> {t("newApplication.confirmedByYou")}
                    </Chip>
                  )}
                  <ProposedStatusChip status={f.status} />
                </span>
              </div>
              <FieldEditor
                field={key}
                value={value}
                meta={meta}
                onChange={(v) => set(key, v)}
                onFocus={() => onSelect(key)}
              />
              {key === "amount_inr" && Number(value) > 0 && (
                <p className="mt-0.5 text-[11px] text-muted-foreground tabular">
                  {formatInr(Number(value))}
                </p>
              )}
              {f.note && <p className="mt-1 text-[11.5px] text-flag-foreground">{f.note}</p>}
              {(f.status === "unclear" || f.status === "invalid") &&
                (f.candidates ?? []).length > 0 && (
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span className="text-[11px] text-muted-foreground">
                      {t("newApplication.candidates")}
                    </span>
                    {(f.candidates ?? []).map((c) => (
                      <button
                        key={`${c.span.start}-${c.value}`}
                        type="button"
                        data-testid="candidate"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(key);
                          set(key, normalise(key, c.value, meta), c.span);
                        }}
                        className="rounded border border-flag/40 bg-surface px-1.5 py-0.5 text-[11.5px] font-medium text-foreground hover:bg-flag-soft"
                      >
                        {candidateLabel(key, c.value, meta)}
                      </button>
                    ))}
                  </div>
                )}
              {needs && (
                <button
                  type="button"
                  data-testid={`confirm-${key}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    settle(key);
                  }}
                  className="mt-1.5 inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-0.5 text-[11.5px] font-medium text-foreground hover:bg-muted"
                >
                  <Check className="h-3 w-3" /> {t("newApplication.confirmValue")}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {pending.length > 0 && (
        <p
          className="flex items-center gap-1.5 border-t border-border bg-flag-soft px-4 py-2 text-[12px] text-flag-foreground"
          data-testid="needs-confirmation"
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          {t("newApplication.needConfirmation", { n: pending.length })}
        </p>
      )}
    </Panel>
  );
}

/** A candidate as the RM reads it: a configured id shows its label. */
function candidateLabel(field: string, value: string, meta: Meta): string {
  const list =
    field === "constitution" ? meta.constitutions : field === "facilities" ? meta.facilities : [];
  return list.find((o) => o.id === value)?.label ?? value.replace(/_/g, " ");
}

function FieldEditor({
  field,
  value,
  meta,
  onChange,
  onFocus,
}: {
  field: string;
  value: string;
  meta: Meta;
  onChange: (value: string) => void;
  onFocus: () => void;
}) {
  const label = t(`proposalField.${field}`);
  if (field === "constitution") {
    return (
      <select
        aria-label={label}
        className={inputClass}
        value={value}
        onFocus={onFocus}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{t("term.notConfirmed")}</option>
        {meta.constitutions
          .filter((c) => c.id !== "unknown")
          .map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
      </select>
    );
  }
  if (field === "facilities") {
    const ids = value.split(",").filter(Boolean);
    return (
      <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label={label}>
        {meta.facilities.map((f) => {
          const on = ids.includes(f.id);
          return (
            <button
              key={f.id}
              type="button"
              aria-pressed={on}
              onClick={(e) => {
                e.stopPropagation();
                onFocus();
                onChange((on ? ids.filter((i) => i !== f.id) : [...ids, f.id]).join(","));
              }}
              className={cn(
                "rounded border px-2 py-0.5 text-[11.5px]",
                on
                  ? "border-primary/50 bg-primary/10 font-medium text-primary"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              {f.label}
            </button>
          );
        })}
      </div>
    );
  }
  const numeric =
    field === "amount_inr" || field === "declared_turnover_inr" || field === "proposed_emi_inr";
  const upper = field === "pan" || field === "gstin" || field === "cin" || field === "udyam";
  return (
    <input
      aria-label={label}
      className={cn(inputClass, (numeric || upper) && "tabular", upper && "uppercase")}
      value={value}
      inputMode={numeric ? "numeric" : undefined}
      onFocus={onFocus}
      onChange={(e) =>
        onChange(
          numeric
            ? e.target.value.replace(/[^\d]/g, "")
            : upper
              ? e.target.value.toUpperCase()
              : e.target.value,
        )
      }
    />
  );
}

function CreateBar({
  proposal,
  draft,
  meta,
  duplicateBlocked,
  creating,
  error,
  onDiscard,
  onCreate,
}: {
  proposal: CaseProposal;
  draft: Draft;
  meta: Meta;
  duplicateBlocked: boolean;
  creating: boolean;
  error: unknown;
  onDiscard: () => void;
  onCreate: () => void;
}) {
  const missing = missingMinimum(meta.case_create_minimum, draft);
  const pending = unsettled(proposal, draft);
  const blocked = missing.length > 0 || pending.length > 0 || duplicateBlocked;

  return (
    <div className="space-y-2">
      {error ? <ErrorState error={error} compact /> : null}
      <div className="flex flex-wrap items-center justify-end gap-2">
        {missing.length > 0 && (
          <p className="mr-auto text-[12px] text-muted-foreground" data-testid="missing-minimum">
            {t("newApplication.stillNeeded", {
              fields: missing.map((k) => t(`proposalField.${k}`)).join(", "),
            })}
          </p>
        )}
        <button
          type="button"
          onClick={onDiscard}
          className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
        >
          {t("newApplication.discard")}
        </button>
        <button
          type="button"
          disabled={blocked || creating}
          onClick={onCreate}
          data-testid="create-application"
          className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
        >
          {creating ? t("newApplication.creating") : t("newApplication.create")}
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

/** The start of an application, as the original design: three ways in (paste the message, drop
 * the documents, type an identifier), where it came from, how reading works, and the borrowers
 * already on the desk. */
function IntakeStart({
  text,
  onText,
  ids,
  onIds,
  attachments,
  onAttach,
  onRemove,
  channels,
  channel,
  onChannel,
  error,
}: {
  text: string;
  onText: (v: string) => void;
  ids: string;
  onIds: (v: string) => void;
  attachments: File[];
  onAttach: (files: File[]) => void;
  onRemove: (i: number) => void;
  channels: Meta["channels"];
  channel: string;
  onChannel: (id: string) => void;
  error: unknown;
}) {
  const cases = useCases();
  const recent = [...(cases.data ?? [])]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 4);
  const step = (n: number, icon: ReactNode, title: string, help: string, body: ReactNode) => (
    <div className="flex min-w-0 flex-col rounded border border-border bg-surface p-3">
      <div className="flex items-start gap-2">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded bg-accent text-primary">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-foreground">
            {n}. {title}
          </p>
          <p className="text-[11.5px] text-muted-foreground">{help}</p>
        </div>
      </div>
      <div className="mt-3 flex-1">{body}</div>
    </div>
  );
  return (
    <div className="grid items-start gap-4 @min-[60rem]/main:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
      <div className="min-w-0 space-y-4">
        <div className="grid gap-3 @min-[42rem]/main:grid-cols-3">
          {step(
            1,
            <MessageSquareText className="h-3.5 w-3.5" />,
            t("newApplication.start.message"),
            t("newApplication.messageHelp"),
            <textarea
              rows={8}
              value={text}
              onChange={(e) => onText(e.target.value)}
              placeholder={t("newApplication.messagePlaceholder")}
              aria-label={t("newApplication.message")}
              data-testid="message-input"
              className="h-full w-full resize-y rounded border border-border bg-surface p-2.5 text-[12.5px] leading-relaxed outline-none focus:ring-1 focus:ring-ring"
            />,
          )}
          {step(
            2,
            <Files className="h-3.5 w-3.5" />,
            t("newApplication.start.documents"),
            t("newApplication.attachmentsHelp"),
            <div className="space-y-2">
              <UploadZone compact onFiles={onAttach} />
              {attachments.length > 0 && (
                <ul className="space-y-1 text-[12px]" data-testid="attachments">
                  {attachments.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="flex items-center gap-2">
                      <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 break-all">{f.name}</span>
                      <button
                        type="button"
                        aria-label={t("action.remove")}
                        onClick={() => onRemove(i)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-muted"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>,
          )}
          {step(
            3,
            <KeyRound className="h-3.5 w-3.5" />,
            t("newApplication.start.identifiers"),
            t("newApplication.start.identifiersHelp"),
            <input
              value={ids}
              onChange={(e) => onIds(e.target.value)}
              placeholder={t("newApplication.start.identifiersPlaceholder")}
              aria-label={t("newApplication.start.identifiers")}
              data-testid="identifiers-input"
              className={inputClass}
            />,
          )}
        </div>
        <Panel
          title={t("newApplication.start.provenance")}
          subtitle={t("newApplication.start.provenanceHelp")}
        >
          <div className="px-4 py-3">
            <p className="field-label">{t("newApplication.channel")}</p>
            <div
              className="mt-1.5 flex flex-wrap gap-1.5"
              role="radiogroup"
              aria-label={t("newApplication.channel")}
            >
              {channels.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  role="radio"
                  aria-checked={c.id === channel}
                  onClick={() => onChannel(c.id)}
                  data-testid={`channel-${c.id}`}
                  className={cn(
                    "rounded border px-2.5 py-1 text-[12px] font-medium transition-colors",
                    c.id === channel
                      ? "border-primary bg-accent text-primary"
                      : "border-border bg-surface text-muted-foreground hover:bg-muted",
                  )}
                >
                  {c.label}
                </button>
              ))}
            </div>
            <p className="mt-3 text-[11.5px] text-muted-foreground">
              {t("newApplication.nothingStored")}
            </p>
          </div>
        </Panel>
        {error ? <ErrorState error={error} compact /> : null}
      </div>
      <div className="min-w-0 space-y-4">
        <div className="rounded border border-primary/20 bg-accent px-4 py-3">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-accent-foreground">
            <ShieldCheck className="h-4 w-4" aria-hidden /> {t("newApplication.start.howTitle")}
          </p>
          <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
            {t("newApplication.start.how")}
          </p>
        </div>
        <Panel
          title={t("newApplication.start.recent")}
          subtitle={t("newApplication.start.recentHelp")}
        >
          {recent.length === 0 ? (
            <p className="px-4 py-3 text-[12px] text-muted-foreground">
              {t("newApplication.start.recentNone")}
            </p>
          ) : (
            <ul className="divide-y divide-border" data-testid="recent-borrowers">
              {recent.map((c) => (
                <li key={c.id} className="px-4 py-2.5">
                  <Link
                    to="/appraisals/$caseId"
                    params={{ caseId: c.id }}
                    className="text-[13px] font-medium text-foreground hover:text-primary hover:underline"
                  >
                    {c.borrower}
                  </Link>
                  <p className="tabular text-[11px] text-muted-foreground">
                    {c.id} · {formatInr(c.amount_inr)} · {c.rm}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
