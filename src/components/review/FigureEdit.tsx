import { useRef, useState } from "react";
import { Paperclip, PencilLine, X } from "lucide-react";
import { toast } from "sonner";
import type { FieldValue } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { FieldStatusChip } from "@/components/documents/chips";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { formatBytes } from "@/domain/documents";
import { refusal } from "@/domain/errors";
import { effectiveValue, fieldLabel, formatValue } from "@/domain/extraction";
import {
  ATTACHMENT_ACCEPT,
  CHANGE_REASON_MIN,
  saveAttachment,
  useChangeFigure,
  usePendingChange,
  type PendingChange,
} from "@/domain/figureEdits";
import { useDecideReview, useFieldItem } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";
import { FieldRowDecision } from "./FieldDecision";
import { decisionButton } from "./styles";

// A figure changed on Extracted data, maker and checker (engine/figure_edits.py). The Credit Analyst
// (manual.make) changes a figure with a reason and, optionally, the paper it rests on; until the
// Credit Manager (manual.check, never the maker) approves it, the row says "Awaiting check" with
// what was, what is proposed, why, by whom, and the paper. The figure on record stands meanwhile.
//
// Test ids: figure-edit-open (the button), figure-edit-dialog, figure-edit-value,
// figure-edit-reason-input, figure-edit-file, figure-edit-send, figure-edit-error,
// figure-edit-pending (data-field), figure-edit-change, figure-edit-reason, figure-edit-attachment,
// figure-edit-by, figure-edit-waiting, figure-edit-approve, figure-edit-send-back,
// figure-edit-back-reason, figure-edit-back-confirm.

const inputClass =
  "mt-1 h-9 w-full min-w-0 rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";
const areaClass =
  "mt-1 w-full resize-none rounded border border-border bg-surface p-2.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";

/** A field's status where it is read: the change awaiting its check when there is one; otherwise
 * its status, the review decision when it waits for one, and the way to change it when it is a
 * figure on a financial statement. `quiet` is a table cell: a confirmed value without a chip, and
 * the change offered as a pencil. With `changeBelow`, a waiting change shows only its chip here:
 * the row below carries the change (`PendingChangeRow`). */
export function FieldStatusCell({
  field,
  editable,
  quiet = false,
  changeBelow = false,
}: {
  field: FieldValue;
  editable: boolean;
  quiet?: boolean;
  changeBelow?: boolean;
}) {
  const pending = usePendingChange(field);
  const reviewItem = useFieldItem(field);
  const canMake = useCan("manual.make");
  if (pending && changeBelow) return <Chip tone="flag">{t("figureEdit.awaiting")}</Chip>;
  if (pending) return <PendingChangeNote item={pending} field={field} />;
  return (
    <>
      {!(quiet && field.status === "accepted") && <FieldStatusChip status={field.status} />}
      <FieldRowDecision field={field} />
      {/* Figures only (names and dates are not changed this way); a value still waiting for its
          own review is confirmed or corrected there first. */}
      {editable && canMake && !reviewItem && isChangeable(field) && (
        <ChangeFigure field={field} compact={quiet} />
      )}
    </>
  );
}

/** What kind of value a field holds, for the words and the input: a figure, a date, text, or
 * none read (a field not found on the document). A yes-or-no value is not changed this way. */
type ValueKind = "figure" | "date" | "text" | "none";

function kindOf(field: FieldValue): ValueKind | null {
  if (field.value === null || field.value === undefined) return "none";
  if (typeof field.value === "number") return "figure";
  if (typeof field.value === "boolean") return null;
  return /^\d{4}-\d{2}-\d{2}$/.test(field.value) ? "date" : "text";
}

function isChangeable(field: FieldValue): boolean {
  return kindOf(field) !== null;
}

const CHANGE_LABEL: Record<ValueKind, string> = {
  figure: "figureEdit.change",
  date: "figureEdit.changeValue",
  text: "figureEdit.changeValue",
  none: "figureEdit.enter",
};
const TITLE: Record<ValueKind, string> = {
  figure: "figureEdit.title",
  date: "figureEdit.titleValue",
  text: "figureEdit.titleValue",
  none: "figureEdit.titleEnter",
};
const HELP: Record<ValueKind, string> = {
  figure: "figureEdit.newValueHelp",
  date: "figureEdit.newValueHelpDate",
  text: "figureEdit.newValueHelpText",
  none: "figureEdit.newValueHelpAny",
};

function ChangeFigure({
  field,
  again = false,
  compact = false,
}: {
  field: FieldValue;
  again?: boolean;
  /** In a table cell: the pencil alone, its words as its name. */
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const label = again ? t("figureEdit.changeAgain") : t(CHANGE_LABEL[kindOf(field) ?? "text"]);
  return (
    <>
      <span className={compact ? "inline-flex" : "mt-1 flex"}>
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={compact ? `${label}: ${fieldLabel(field.field)}` : undefined}
          title={compact ? label : undefined}
          className={
            compact
              ? "rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              : `${decisionButton} inline-flex items-center gap-1 border-border bg-surface text-foreground hover:bg-muted`
          }
          data-testid="figure-edit-open"
          data-field={field.field}
        >
          <PencilLine className="size-3" aria-hidden />
          {!compact && label}
        </button>
      </span>
      {open && <ChangeDialog field={field} onClose={() => setOpen(false)} />}
    </>
  );
}

function ChangeDialog({ field, onClose }: { field: FieldValue; onClose: () => void }) {
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const change = useChangeFigure(field);
  const kind = kindOf(field) ?? "text";
  const inForce = field.status === "corrected" ? effectiveValue(field) : field.value;
  const ready = value.trim() !== "" && reason.trim().length >= CHANGE_REASON_MIN;
  const refused = change.isError ? refusal(change.error) : null;
  const clearError = () => {
    if (change.isError) change.reset();
  };

  const submit = () =>
    change.mutate({ value: value.trim(), reason: reason.trim(), file }, { onSuccess: onClose });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-lg overflow-y-auto"
        data-testid="figure-edit-dialog"
      >
        <DialogHeader>
          <DialogTitle>{t(TITLE[kind])}</DialogTitle>
          <DialogDescription>{fieldLabel(field.field)}</DialogDescription>
        </DialogHeader>

        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 rounded border border-border bg-surface-muted px-3 py-2 text-[12.5px]">
          <dt className="text-muted-foreground">{t("figureEdit.inForce")}</dt>
          <dd className="tabular font-medium text-foreground">
            {kind === "none" ? t("fieldStatus.missing") : formatValue(inForce)}
          </dd>
          {field.status === "corrected" && (
            <>
              <dt className="text-muted-foreground">{t("figureEdit.readAs")}</dt>
              <dd className="tabular text-foreground">{formatValue(field.value)}</dd>
            </>
          )}
        </dl>

        <label className="block">
          <span className="field-label">
            {kind === "figure" ? t("figureEdit.newFigure") : t("figureEdit.newValue")}
          </span>
          <input
            className={inputClass}
            value={value}
            inputMode={kind === "figure" ? "decimal" : undefined}
            onChange={(e) => {
              setValue(e.target.value);
              clearError();
            }}
            aria-describedby="figure-edit-value-help"
            data-testid="figure-edit-value"
          />
          <span
            id="figure-edit-value-help"
            className="mt-1 block text-[11.5px] text-muted-foreground"
          >
            {t(HELP[kind])}
          </span>
        </label>

        <label className="block">
          <span className="field-label">{t("figureEdit.reason")}</span>
          <textarea
            rows={3}
            className={areaClass}
            value={reason}
            required
            onChange={(e) => {
              setReason(e.target.value);
              clearError();
            }}
            aria-describedby="figure-edit-reason-help"
            data-testid="figure-edit-reason-input"
          />
          <span
            id="figure-edit-reason-help"
            className="mt-1 block text-[11.5px] text-muted-foreground"
          >
            {t("figureEdit.reasonHelp", { n: CHANGE_REASON_MIN })}
          </span>
        </label>

        <div>
          <span className="field-label">{t("figureEdit.attachment")}</span>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <input
              ref={fileInput}
              type="file"
              accept={ATTACHMENT_ACCEPT}
              aria-label={t("figureEdit.attachment")}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                clearError();
              }}
              className="max-w-full text-[12.5px] text-foreground file:mr-2 file:h-8 file:rounded file:border file:border-border file:bg-surface file:px-2.5 file:text-[12px] file:font-medium file:text-foreground hover:file:bg-muted"
              data-testid="figure-edit-file"
            />
            {file && (
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  if (fileInput.current) fileInput.current.value = "";
                }}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11.5px] text-muted-foreground hover:bg-muted"
              >
                <X className="size-3" aria-hidden /> {t("figureEdit.removeAttachment")}
              </button>
            )}
          </div>
          <p className="mt-1 text-[11.5px] text-muted-foreground">
            {t("figureEdit.attachmentHelp")}
          </p>
        </div>

        <p className="rounded border border-flag/35 bg-flag-soft px-3 py-2 text-[12px] text-flag-foreground">
          {t("figureEdit.checkNote")}
        </p>
        {refused && (
          <p
            role="alert"
            className="text-[12px] text-critical-text"
            data-testid="figure-edit-error"
          >
            {refused}
          </p>
        )}

        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
          >
            {t("figureEdit.cancel")}
          </button>
          <button
            type="button"
            disabled={!ready || change.isPending}
            onClick={submit}
            className="h-9 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            data-testid="figure-edit-send"
          >
            {t("figureEdit.send")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A change awaiting its check, across the width of its field's row (the row below it): what was,
 * what is proposed, why, the paper, who and when; on the right the checker's two answers, or
 * whom it waits for. */
export function PendingChangeRow({ item, field }: { item: PendingChange; field: FieldValue }) {
  return (
    <div
      className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 rounded border border-flag/30 bg-flag-soft/40 px-3 py-2.5"
      data-testid="figure-edit-pending"
      data-field={field.field}
    >
      <div className="min-w-0 flex-1 basis-64 space-y-1">
        <ChangeLine item={item} />
        <p
          className="break-words text-[12.5px] leading-snug text-foreground"
          data-testid="figure-edit-reason"
        >
          {item.edit.reason}
        </p>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <AttachmentLink item={item} />
          <MadeBy item={item} />
        </p>
      </div>
      <div className="flex shrink-0 flex-col items-start gap-1 sm:items-end">
        <Answers item={item} field={field} />
      </div>
    </div>
  );
}

function ChangeLine({ item }: { item: PendingChange }) {
  const { edit } = item;
  return (
    <p className="text-[12.5px] leading-snug" data-testid="figure-edit-change">
      <span className="text-muted-foreground">{t("figureEdit.from")} </span>
      <span className="tabular text-muted-foreground line-through">
        {formatValue(edit.from_value ?? null)}
      </span>
      <span className="text-muted-foreground"> · {t("figureEdit.to")} </span>
      <span className="tabular font-medium text-foreground">
        {formatValue(edit.to_value ?? null)}
      </span>
    </p>
  );
}

function AttachmentLink({ item }: { item: PendingChange }) {
  const paper = item.edit.attachment;
  if (!paper) return null;
  return (
    <button
      type="button"
      onClick={() => void saveAttachment(item)}
      className="inline-flex max-w-full items-center gap-1 text-left text-[11.5px] font-medium text-primary hover:underline"
      data-testid="figure-edit-attachment"
    >
      <Paperclip className="size-3 shrink-0" aria-hidden />
      <span className="min-w-0 break-all">{paper.name}</span>
      <span className="shrink-0 font-normal text-muted-foreground">
        · {formatBytes(paper.size)}
      </span>
    </button>
  );
}

function MadeBy({ item }: { item: PendingChange }) {
  return (
    <span className="text-[11px] text-muted-foreground" data-testid="figure-edit-by">
      {t("figureEdit.by", { name: item.edit.maker_name, at: formatDate(item.edit.at) })}
    </span>
  );
}

/** The checker's answers; anyone else reads whom the change waits for, and its maker may change
 * it again. */
function Answers({ item, field }: { item: PendingChange; field: FieldValue }) {
  const me = useSession()?.user.id;
  const canCheck = useCan("manual.check") && item.maker !== me;
  const canMake = useCan("manual.make");
  return (
    <>
      {canCheck ? (
        <CheckAnswers item={item} />
      ) : (
        <p className="text-[11.5px] text-flag-foreground" data-testid="figure-edit-waiting">
          {t("figureEdit.waiting")}
        </p>
      )}
      {canMake && item.maker === me && <ChangeFigure field={field} again />}
    </>
  );
}

/** The same, in a table cell: stacked under the chip. */
function PendingChangeNote({ item, field }: { item: PendingChange; field: FieldValue }) {
  const { edit } = item;
  return (
    <div className="w-full space-y-1" data-testid="figure-edit-pending" data-field={field.field}>
      <Chip tone="flag">{t("figureEdit.awaiting")}</Chip>
      <p className="text-[12px] leading-snug" data-testid="figure-edit-change">
        <span className="text-muted-foreground">{t("figureEdit.from")} </span>
        <span className="tabular text-muted-foreground line-through">
          {formatValue(edit.from_value ?? null)}
        </span>
        <span className="text-muted-foreground"> · {t("figureEdit.to")} </span>
        <span className="tabular font-medium text-foreground">
          {formatValue(edit.to_value ?? null)}
        </span>
      </p>
      <p
        className="break-words text-[12px] leading-snug text-foreground"
        data-testid="figure-edit-reason"
      >
        {edit.reason}
      </p>
      {item.edit.attachment && (
        <p>
          <AttachmentLink item={item} />
        </p>
      )}
      <p>
        <MadeBy item={item} />
      </p>
      <Answers item={item} field={field} />
    </div>
  );
}

function CheckAnswers({ item }: { item: PendingChange }) {
  const decide = useDecideReview();
  const [back, setBack] = useState(false);
  const [reason, setReason] = useState("");
  const answer = (decision: "confirm" | "waive") =>
    decide.mutate(
      {
        id: item.id,
        body: { decision, value: null, reason: decision === "waive" ? reason.trim() : null },
      },
      {
        onSuccess: () =>
          toast.success(
            decision === "confirm" ? t("figureEdit.approved") : t("figureEdit.sentBack"),
          ),
        onError: (error) =>
          toast.error(refusal(error) ?? (error instanceof Error ? error.message : String(error))),
      },
    );

  if (back) {
    return (
      <div className="w-full min-w-0 space-y-1.5 pt-0.5 sm:w-72">
        <label className="block">
          <span className="field-label">{t("figureEdit.sendBackReason")}</span>
          <textarea
            rows={2}
            className={areaClass}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="figure-edit-back-reason"
          />
        </label>
        <span className="flex flex-wrap gap-1">
          <button
            type="button"
            disabled={reason.trim() === "" || decide.isPending}
            onClick={() => answer("waive")}
            className={`${decisionButton} border-border bg-surface text-foreground hover:bg-muted`}
            data-testid="figure-edit-back-confirm"
          >
            {t("figureEdit.sendBackConfirm")}
          </button>
          <button
            type="button"
            onClick={() => setBack(false)}
            className={`${decisionButton} border-transparent text-muted-foreground hover:bg-muted`}
          >
            {t("figureEdit.cancel")}
          </button>
        </span>
      </div>
    );
  }
  return (
    <span className="flex flex-wrap gap-1 pt-0.5">
      <button
        type="button"
        disabled={decide.isPending}
        onClick={() => answer("confirm")}
        className={`${decisionButton} border-positive/40 bg-surface text-positive hover:bg-positive-soft`}
        data-testid="figure-edit-approve"
      >
        {t("figureEdit.approve")}
      </button>
      <button
        type="button"
        onClick={() => setBack(true)}
        className={`${decisionButton} border-border bg-surface text-foreground hover:bg-muted`}
        data-testid="figure-edit-send-back"
      >
        {t("figureEdit.sendBack")}
      </button>
    </span>
  );
}
