import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, Upload, X } from "lucide-react";
import type { ChecklistItemState } from "@/api/types";
import { RegisterCell } from "@/components/documents/FileTree";
import { useRegisterRow } from "@/components/documents/registerRow";
import { useFeature } from "@/domain/features";
import { StageTrack } from "@/components/documents/StageTrack";
import { t } from "@/config/terminology";
import { bandOf, useChecklist } from "@/domain/checklist";
import { ACCEPT } from "@/domain/documents";
import { cn } from "@/lib/utils";
import { StatusMark } from "./checklist/Readiness";
import { useFileDrag } from "./checklist/useFileDrag";
import { useRowUploads, type Outcome, type RowUploads } from "./checklist/useRowUploads";

// The documents this appraisal needs that have not been uploaded, at the head of the files
// received: one row each, in the register's columns, so what is missing is seen before what has
// come in. The rows are white like every other row: the colour is only in each row's mark and its
// blocking note. With no file there are no pages, confidence or checks, so the document and what is
// missing of it run across those columns and the row stays short. A file is uploaded from
// the row (picked or dropped on it); its content decides where it counts, and the row says what
// it was read as and which requirement it now counts toward. A row a file was sent from stays
// until the page is left, so that answer is read where the file was sent. A role that cannot
// upload sees the rows without the upload.
//
// Test ids: register-missing (the section; data-count), register-missing-row (data-item),
// register-missing-upload and register-missing-upload-input, register-missing-outcome
// (data-state).

export function NotUploaded({ caseId }: { caseId: string }) {
  const checklist = useChecklist(caseId);
  const uploads = useRowUploads(caseId);
  const dragging = useFileDrag();
  const items = (checklist.data?.items ?? []).filter(
    (i) => i.status === "missing" || uploads.pinned[i.item_id] !== undefined,
  );
  if (items.length === 0) return null;
  const missing = items.filter((i) => i.status === "missing").length;
  return (
    <section data-testid="register-missing" data-count={missing}>
      <h3 className="flex items-center gap-1.5 border-b border-border px-4 py-1.5 text-[11.5px] font-semibold text-foreground">
        <X className="h-3.5 w-3.5 text-critical-text" aria-hidden />
        {t("documents.missing.section", { n: missing })}
      </h3>
      <ul className="divide-y divide-border">
        {items.map((item) => (
          <MissingRow key={item.item_id} item={item} uploads={uploads} dragging={dragging} />
        ))}
      </ul>
    </section>
  );
}

function MissingRow({
  item,
  uploads,
  dragging,
}: {
  item: ChecklistItemState;
  uploads: RowUploads;
  dragging: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const row = useRegisterRow();
  const integrityOn = useFeature("integrity_checks");
  const id = item.item_id;
  const pending = uploads.pendingFor(id);
  const droppable = uploads.can;
  const send = (list: File[]) => void uploads.send(item, bandOf(item), list);
  const outcomes = uploads.outcomesFor(id);
  return (
    <li
      className={cn(
        "relative transition-colors",
        dragging &&
          droppable &&
          !over &&
          "outline-1 -outline-offset-4 outline-dashed outline-info/50",
        over && "bg-info-soft outline-2 -outline-offset-4 outline-dashed outline-info",
      )}
      data-testid="register-missing-row"
      data-item={id}
      data-status={item.status}
      onDragOver={
        droppable
          ? (e) => {
              e.preventDefault();
              e.dataTransfer.dropEffect = "copy";
              setOver(true);
            }
          : undefined
      }
      onDragLeave={
        droppable
          ? (e) => {
              if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
            }
          : undefined
      }
      onDrop={
        droppable
          ? (e) => {
              e.preventDefault();
              setOver(false);
              send(Array.from(e.dataTransfer.files));
            }
          : undefined
      }
    >
      <div className={row}>
        {/* The file: none yet, and the upload for it. */}
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5">
          <StatusMark status={item.status} />
          <span className="text-[12.5px] italic text-muted-foreground">
            {t("documents.missing.notUploaded")}
          </span>
          {droppable && (
            <>
              <input
                ref={input}
                type="file"
                multiple
                accept={ACCEPT}
                className="hidden"
                data-testid="register-missing-upload-input"
                onChange={(e) => {
                  send(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
              />
              {/* Not disabled while it uploads (that would drop the focus), only marked so. */}
              <button
                type="button"
                onClick={() => {
                  if (!pending) input.current?.click();
                }}
                aria-disabled={pending || undefined}
                aria-label={t(pending ? "journey.uploadingFor" : "journey.uploadFor", {
                  name: item.name,
                })}
                title={t("journey.uploadHelp")}
                className="inline-flex h-8 items-center gap-1.5 rounded border border-primary/40 bg-surface px-2.5 text-[12px] font-medium text-primary hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring aria-disabled:cursor-default aria-disabled:opacity-50"
                data-testid="register-missing-upload"
              >
                {pending ? (
                  <Loader2
                    className="size-3.5 animate-spin motion-reduce:animate-none"
                    aria-hidden
                  />
                ) : (
                  <Upload className="size-3.5" aria-hidden />
                )}
                <span>{t(pending ? "journey.uploading" : "journey.upload")}</span>
              </button>
            </>
          )}
        </span>
        {/* What is needed and what exactly is missing of it, across the columns a file would fill. */}
        <RegisterCell
          column="type"
          className={integrityOn ? "md:col-span-3 md:col-start-3" : "md:col-span-2 md:col-start-3"}
        >
          <span className="block text-[12.5px] font-medium text-foreground">{item.name}</span>
          {item.deficiency && (
            <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
              {item.deficiency}
            </span>
          )}
        </RegisterCell>
        <RegisterCell column="satisfies">
          <span className="block text-[12px] text-muted-foreground">{item.section}</span>
          {item.blocking && item.status === "missing" && (
            <span className="block text-[11px] text-critical-text">
              {t("journey.status.blocks")}
            </span>
          )}
        </RegisterCell>
      </div>
      {outcomes.length > 0 && <Outcomes outcomes={outcomes} />}
      {over && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <span className="rounded-full bg-surface px-3 py-1 text-[12px] font-semibold text-info shadow-sm">
            {t("journey.dropHere", { name: item.name })}
          </span>
        </div>
      )}
    </li>
  );
}

/** What became of each file sent from the row: still being read, or what it was read as and where
 * it counts. */
function Outcomes({ outcomes }: { outcomes: Outcome[] }) {
  return (
    <ul className="space-y-1 px-4 pb-2.5" aria-live="polite">
      {outcomes.map((o) => (
        <li
          key={o.id}
          className={cn(
            "flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11.5px]",
            o.state === "reading" && "text-info",
            o.state === "counted" && "text-positive",
            (o.state === "unidentified" || o.state === "unasked") && "text-flag-foreground",
            o.state === "turnedAway" && "text-critical-text",
          )}
          data-testid="register-missing-outcome"
          data-state={o.state}
        >
          {o.state === "reading" ? (
            <CircleDashed
              className="size-3 shrink-0 animate-spin motion-reduce:animate-none"
              aria-hidden
            />
          ) : o.state === "counted" ? (
            <CheckCircle2 className="size-3 shrink-0" aria-hidden />
          ) : (
            <AlertTriangle className="size-3 shrink-0" aria-hidden />
          )}
          <span className="min-w-0">
            <span className="font-medium">{o.name}</span>
            {": "}
            {o.state === "reading"
              ? t("journey.outcome.reading")
              : o.state === "unidentified"
                ? t("journey.outcome.unidentified")
                : o.state === "turnedAway"
                  ? t("journey.outcome.turnedAway", { reason: o.text })
                  : o.text}
          </span>
          {o.state === "reading" && <StageTrack doc={o.doc} />}
        </li>
      ))}
    </ul>
  );
}
