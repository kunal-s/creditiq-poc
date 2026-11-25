import { useState } from "react";
import type { LogicalDocument } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t, tOr } from "@/config/terminology";
import { useDocumentTypes, useRetypePage, useSetDocumentPeriod } from "@/domain/documents";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { GradeChip } from "./chips";

// Test ids: document-period, period-set-open, period-start, period-end, period-reason, period-save,
// document-pages, document-page, page-also-in, page-type-open, page-type-select, page-type-reason,
// page-type-save, page-type-queued.

const FIELD =
  "w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] focus:outline-none focus:ring-2 focus:ring-primary/40";

function Action({
  children,
  disabled,
  testId,
}: {
  children: string;
  disabled: boolean;
  testId: string;
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      data-testid={testId}
      className={cn(
        "rounded px-3 py-1.5 text-[12.5px] font-medium",
        disabled
          ? "cursor-not-allowed border border-border text-muted-foreground"
          : "bg-primary text-primary-foreground hover:opacity-90",
      )}
    >
      {children}
    </button>
  );
}

function Cancel({ onClick, children }: { onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded border border-border px-3 py-1.5 text-[12.5px] text-muted-foreground hover:bg-surface-muted"
    >
      {children}
    </button>
  );
}

/** The period the document covers, as read from it or as a person set it; a person who may decide sets it where
 * none was found or where its title and its columns disagree, with a reason the engine records. */
export function DocumentPeriodRow({ caseId, doc }: { caseId: string; doc: LogicalDocument }) {
  const period = doc.period;
  const mayDecide = useCan("review.decide");
  const save = useSetDocumentPeriod(caseId, doc.id);
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(period?.start ?? "");
  const [end, setEnd] = useState(period?.end ?? "");
  const [reason, setReason] = useState("");
  if (!period || period.status === "none") return null;
  const shown =
    period.start && period.end
      ? t("validation.period.range", { start: period.start, end: period.end })
      : t("validation.period.none");
  const needsPerson = period.status === "not_found" || period.status === "conflict";
  const ready = Boolean(start && end && start <= end && reason.trim()) && !save.isPending;
  return (
    <div data-testid="document-period" data-status={period.status}>
      <p className="field-label">{t("validation.period.label")}</p>
      <p className="mt-0.5 text-[12.5px] text-foreground">
        <span className="tabular">{shown}</span>
        {period.start && period.end && (
          <span className="text-muted-foreground">
            {" · "}
            {t(`validation.period.status.${period.status}`)}
          </span>
        )}
      </p>
      {period.status === "set" && period.note && (
        <p className="text-[12px] text-muted-foreground">
          {t("validation.period.reason", { reason: period.note })}
        </p>
      )}
      {mayDecide && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-1 text-[12px] font-medium text-primary hover:underline"
          data-testid="period-set-open"
        >
          {needsPerson ? t("validation.period.set") : t("validation.period.change")}
        </button>
      )}
      {open && (
        <form
          className="mt-2 grid max-w-md gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready)
              save.mutate(
                { start, end, reason: reason.trim() },
                { onSuccess: () => setOpen(false) },
              );
          }}
        >
          <div className="grid grid-cols-2 gap-2">
            <label className="grid gap-1">
              <span className="field-label">{t("validation.period.start")}</span>
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className={FIELD}
                data-testid="period-start"
              />
            </label>
            <label className="grid gap-1">
              <span className="field-label">{t("validation.period.end")}</span>
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className={FIELD}
                data-testid="period-end"
              />
            </label>
          </div>
          <label className="grid gap-1">
            <span className="field-label">{t("validation.period.reasonLabel")}</span>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              maxLength={2000}
              placeholder={t("validation.period.reasonPlaceholder")}
              className={FIELD}
              data-testid="period-reason"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Action disabled={!ready} testId="period-save">
              {t("validation.period.save")}
            </Action>
            <Cancel onClick={() => setOpen(false)}>{t("validation.period.cancel")}</Cancel>
          </div>
          {save.isError && (
            <p className="text-[12px] text-critical-text">{t("validation.period.failed")}</p>
          )}
        </form>
      )}
    </div>
  );
}

/** Every page of the document: its readability, the other documents of the file that hold the same page, and, for a
 * person who may decide, reading one page as another type in a document of its own. */
export function DocumentPages({
  caseId,
  doc,
  siblings,
}: {
  caseId: string;
  doc: LogicalDocument;
  /** The other documents read from the same file. */
  siblings: LogicalDocument[];
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const mayDecide = useCan("review.decide");
  const retype = useRetypePage(caseId, doc.id);
  const [editing, setEditing] = useState<number | null>(null);
  const [typeId, setTypeId] = useState("");
  const [reason, setReason] = useState("");
  const [queued, setQueued] = useState<number | null>(null);
  const holders = (n: number) =>
    siblings.filter(
      (s) =>
        s.id !== doc.id &&
        !["superseded", "duplicate"].includes(s.status) &&
        (s.pages.some((p) => p.n === n) ||
          (s.pages.length === 0 && s.page_from <= n && n <= s.page_to)),
    );
  const typeName = (d: LogicalDocument) =>
    (d.classification?.types ?? []).map((id) => types.name(id)).join(" + ") ||
    t("documents.table.none");
  const choices = (types.data?.types ?? []).filter(
    (x) => !(doc.classification?.types ?? []).includes(x.id),
  );
  const ready = Boolean(typeId && reason.trim()) && !retype.isPending;

  return (
    <div className="min-w-0" data-testid="document-pages">
      <p className="field-label">{t("validation.pages")}</p>
      <ul className="mt-1 divide-y divide-border border-y border-border text-[12px]">
        {doc.pages.map((p) => {
          const also = holders(p.n);
          return (
            <li key={p.n} className="py-1.5" data-testid="document-page" data-page={p.n}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <button
                  type="button"
                  className="tabular text-primary hover:underline"
                  onClick={() => viewer.open({ caseId, documentId: doc.id, page: p.n })}
                >
                  {t("validation.page")} {p.n}
                </button>
                <GradeChip grade={p.grade} />
                {(p.reasons ?? []).length > 0 && (
                  <span className="text-muted-foreground" data-testid="page-reasons">
                    {(p.reasons ?? []).map((r) => tOr(`gradeReason.${r}`, r)).join(", ")}
                  </span>
                )}
                {also.length > 0 && (
                  <span className="text-muted-foreground" data-testid="page-also-in">
                    {t("validation.alsoIn")}: {also.map(typeName).join(", ")}
                  </span>
                )}
                {mayDecide && editing !== p.n && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(p.n);
                      setTypeId("");
                      setReason("");
                    }}
                    className="ml-auto text-[12px] font-medium text-primary hover:underline"
                    data-testid="page-type-open"
                  >
                    {t("validation.pageType.action")}
                  </button>
                )}
              </div>
              {queued === p.n && (
                <p
                  className="mt-1 text-[12px] text-muted-foreground"
                  data-testid="page-type-queued"
                >
                  {t("validation.pageType.queued")}
                </p>
              )}
              {editing === p.n && (
                <form
                  className="mt-2 grid max-w-md gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (ready)
                      retype.mutate(
                        { page: p.n, typeId, reason: reason.trim() },
                        {
                          onSuccess: () => {
                            setEditing(null);
                            setQueued(p.n);
                          },
                        },
                      );
                  }}
                >
                  <p className="text-[12.5px] font-semibold text-foreground">
                    {t("validation.pageType.title", { page: p.n })}
                  </p>
                  <p className="text-muted-foreground">{t("validation.pageType.help")}</p>
                  <label className="grid gap-1">
                    <span className="field-label">{t("validation.pageType.type")}</span>
                    <select
                      value={typeId}
                      onChange={(e) => setTypeId(e.target.value)}
                      className={FIELD}
                      data-testid="page-type-select"
                    >
                      <option value="">{t("validation.pageType.choose")}</option>
                      {choices.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1">
                    <span className="field-label">{t("validation.pageType.reasonLabel")}</span>
                    <input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      maxLength={2000}
                      placeholder={t("validation.pageType.reasonPlaceholder")}
                      className={FIELD}
                      data-testid="page-type-reason"
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Action disabled={!ready} testId="page-type-save">
                      {t("validation.pageType.save")}
                    </Action>
                    <Cancel onClick={() => setEditing(null)}>
                      {t("validation.pageType.cancel")}
                    </Cancel>
                  </div>
                  {retype.isError && (
                    <p className="text-critical-text">{t("validation.pageType.failed")}</p>
                  )}
                </form>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
