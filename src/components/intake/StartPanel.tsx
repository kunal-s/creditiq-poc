// Test ids: message-input, upload-zone/upload-input (UploadZone), suggested-documents,
// attachments, identifier-fields, channel-<id>, start-continue, start-hint, recent-borrowers.
import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import {
  ArrowRight,
  ClipboardPaste,
  Files,
  KeyRound,
  MessageSquareText,
  Paperclip,
  ShieldCheck,
  X,
} from "lucide-react";
import type { IntakeProduct, Meta } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { UploadZone } from "@/components/documents/UploadZone";
import { t, tOr } from "@/config/terminology";
import { formatInr, useCases } from "@/domain/cases";
import { formatBytes } from "@/domain/documents";
import { canContinue, minFiles, startChoiceKeys, type Start } from "@/domain/intake";
import { cn } from "@/lib/utils";
import { IdentifierFields, StartChoices } from "./IdentifierFields";
import { onRadioKeys, radioTabIndex } from "./labels";

/** Step 2, the start of an application, as the original design: three boxes side by side (paste
 * the message, drop the documents, type the identifiers) at one height, Provenance and hints (the
 * channel, and the choices that bring up the right identifier boxes), how reading works and the
 * borrowers already on the desk — beside the boxes on a wide screen, under them otherwise. The
 * message and identifiers are optional; the documents are required: the button in the page
 * header (StartButton) waits for them. */
export function StartPanel({
  meta,
  form,
  start,
  onStart,
  error,
}: {
  meta: Meta;
  form: IntakeProduct;
  start: Start;
  onStart: (patch: Partial<Start>) => void;
  error: unknown;
}) {
  const channel = start.channel || meta.channels[0]?.id || "";
  const need = minFiles(form);
  const suggested = form.start.documents.suggested ?? [];
  return (
    <div className="grid items-start gap-4 @min-[70rem]/main:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="min-w-0 space-y-4">
        <div className="grid gap-3 @min-[48rem]/main:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.35fr)]">
          <Box
            n={1}
            icon={<MessageSquareText className="h-3.5 w-3.5" />}
            title={t("newApplication.start.message")}
            required={false}
            help={t("intake.start.messageHelp")}
          >
            <textarea
              rows={6}
              value={start.text}
              onChange={(e) => onStart({ text: e.target.value })}
              placeholder={t("newApplication.messagePlaceholder")}
              aria-label={t("newApplication.message")}
              data-testid="message-input"
              className="h-full min-h-32 w-full resize-y rounded border border-border bg-surface p-2.5 text-[12.5px] leading-relaxed outline-none focus:ring-1 focus:ring-ring"
            />
          </Box>
          <Box
            n={2}
            icon={<Files className="h-3.5 w-3.5" />}
            title={t("newApplication.start.documents")}
            required={need > 0}
            help={t(need > 1 ? "intake.start.documentsHelpMany" : "intake.start.documentsHelp", {
              n: Math.max(need, 1),
            })}
          >
            <div className="space-y-2">
              <UploadZone
                compact
                onFiles={(files) => onStart({ files: [...start.files, ...files] })}
              />
              {suggested.length > 0 && start.files.length === 0 && (
                <SuggestedDocuments ids={suggested} />
              )}
              <FileList
                files={start.files}
                onRemove={(i) => onStart({ files: start.files.filter((_, j) => j !== i) })}
              />
            </div>
          </Box>
          <Box
            n={3}
            icon={<KeyRound className="h-3.5 w-3.5" />}
            title={t("newApplication.start.identifiers")}
            required={false}
            help={t("newApplication.start.identifiersHelp")}
          >
            <IdentifierFields
              product={start.product}
              form={form}
              values={start.identifiers}
              choices={start.choices}
              onValue={(id, v) => onStart({ identifiers: { ...start.identifiers, [id]: v } })}
            />
          </Box>
        </div>
        <Panel
          title={t("newApplication.start.provenance")}
          subtitle={t("newApplication.start.provenanceHelp")}
        >
          <div
            className={cn(
              "grid gap-x-6 gap-y-3 px-4 py-3",
              startChoiceKeys(form).length > 0 &&
                "@min-[48rem]/main:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]",
            )}
          >
            <div className="min-w-0">
              <p className="field-label">{t("newApplication.channel")}</p>
              <div
                className="mt-1.5 flex flex-wrap gap-1.5"
                role="radiogroup"
                aria-label={t("newApplication.channel")}
                onKeyDown={onRadioKeys}
              >
                {meta.channels.map((c, i) => (
                  <button
                    key={c.id}
                    type="button"
                    role="radio"
                    aria-checked={c.id === channel}
                    tabIndex={radioTabIndex(c.id === channel, i, true)}
                    onClick={() => onStart({ channel: c.id })}
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
            </div>
            <div className="grid min-w-0 gap-x-3 gap-y-2 @min-[34rem]/main:grid-cols-2">
              <StartChoices
                meta={meta}
                product={start.product}
                form={form}
                choices={start.choices}
                onChoice={(key, v) => onStart({ choices: { ...start.choices, [key]: v } })}
              />
            </div>
          </div>
          <p className="border-t border-border px-4 py-2 text-[11.5px] text-muted-foreground">
            {t("newApplication.nothingStored")}
          </p>
        </Panel>
        {error ? <ErrorState error={error} compact /> : null}
      </div>
      <StartRail />
    </div>
  );
}

/** The start button, for the page header: Continue, or Read the message when there is one; it
 * waits for the product's documents, and says so beside it. */
export function StartButton({
  meta,
  form,
  start,
  reading,
  onContinue,
}: {
  meta: Meta;
  form: IntakeProduct;
  start: Start;
  reading: boolean;
  onContinue: () => void;
}) {
  const need = minFiles(form);
  const ready = canContinue(start, form) && Boolean(start.channel || meta.channels[0]?.id);
  const hasText = start.text.trim() !== "";
  const hint =
    start.files.length < need
      ? need > 1
        ? t("intake.start.needDocumentsMany", { n: need })
        : t("intake.start.needDocuments")
      : null;
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {hint && (
        <p className="text-[12px] text-flag-foreground" data-testid="start-hint">
          {hint}
        </p>
      )}
      <button
        type="button"
        disabled={!ready || reading}
        onClick={onContinue}
        data-testid="start-continue"
        title={hint ?? undefined}
        className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
      >
        {hasText && <ClipboardPaste className="h-3.5 w-3.5" aria-hidden />}
        {reading
          ? t("newApplication.reading")
          : hasText
            ? t("newApplication.read")
            : t("intake.start.continue")}
        {!hasText && <ArrowRight className="h-3.5 w-3.5" aria-hidden />}
      </button>
    </div>
  );
}

/** The documents the product suggests starting with, under the drop area. */
export function SuggestedDocuments({ ids }: { ids: string[] }) {
  return (
    <p
      className="text-[11.5px] leading-snug text-muted-foreground"
      data-testid="suggested-documents"
    >
      {t("intake.start.suggested", {
        documents: ids.map((id) => tOr(`intake.start.suggestedDoc.${id}`, id)).join(" · "),
      })}
    </p>
  );
}

function Box({
  n,
  icon,
  title,
  required,
  help,
  children,
}: {
  n: number;
  icon: ReactNode;
  title: string;
  required: boolean;
  help: string;
  children: ReactNode;
}) {
  return (
    <div className="@container/box flex min-w-0 flex-col rounded border border-border bg-surface p-3">
      <div className="flex items-start gap-2">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded bg-accent text-primary">
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-1.5 text-[13px] font-semibold text-foreground">
            {n}. {title}
            <Chip tone={required ? "flag" : "muted"} upper>
              <span data-testid={`box-${n}-rule`}>
                {required ? t("intake.start.required") : t("intake.start.optional")}
              </span>
            </Chip>
          </p>
          <p className="text-[11.5px] text-muted-foreground">{help}</p>
        </div>
      </div>
      <div className="mt-3 flex-1">{children}</div>
    </div>
  );
}

/** The files dropped so far, by name, each with its remove button. */
export function FileList({
  files,
  onRemove,
  counted = true,
}: {
  files: File[];
  onRemove: (i: number) => void;
  /** Name the count above the list (left out where a line beside it already says it). */
  counted?: boolean;
}) {
  if (files.length === 0) return null;
  return (
    <div>
      {counted && <p className="field-label">{t("intake.start.files", { n: files.length })}</p>}
      <ul className="mt-1 max-h-48 space-y-1 overflow-auto text-[12px]" data-testid="attachments">
        {files.map((f, i) => (
          <li key={`${f.name}-${i}`} className="flex items-center gap-2">
            <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 break-all">{f.name}</span>
            <span className="tabular text-[11px] text-muted-foreground">{formatBytes(f.size)}</span>
            <button
              type="button"
              aria-label={t("action.remove")}
              onClick={() => onRemove(i)}
              className="rounded p-0.5 text-muted-foreground hover:bg-muted"
            >
              <X className="h-3 w-3" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** How reading works, and the borrowers already on the desk. */
function StartRail() {
  const cases = useCases();
  const recent = [...(cases.data ?? [])]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 4);
  return (
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
  );
}
