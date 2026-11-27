// Test ids: review-panel, review-minimum, review-files, review-duplicates, review-identifiers,
// review-sources (each check with data-state ok | missing | warn | checking), duplicate-warning,
// more-duplicates, override-reason.
import { Link } from "@tanstack/react-router";
import { AlertTriangle, Plus } from "lucide-react";
import { useRef, type ReactNode } from "react";
import type { CaseCreate, CaseProposal, CaseSummary, IntakeProduct } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { StatusMark } from "@/components/case/checklist/Readiness";
import { t, tOr } from "@/config/terminology";
import { ACCEPT } from "@/domain/documents";
import { minFiles, SOURCE_KINDS } from "@/domain/intake";
import { countsBySource } from "@/domain/intakeCreate";
import { fieldLabel, inputClass } from "./labels";
import { identifierLabel } from "./labels";
import { rowLabel } from "./labels";
import { FileList } from "./StartPanel";

/** How many matching applications the duplicate warning names; the rest are counted. */
const SHOWN_DUPLICATES = 3;

type State = "ok" | "missing" | "warn" | "checking";
const MARK = {
  ok: "satisfied",
  missing: "missing",
  warn: "insufficient",
  checking: "in_review",
} as const;

/** Step 4: whether the application can be created — the product's minimum, the documents going
 * with it, a matching application already on file (the engine's duplicate check, with or without
 * a message), identifiers the engine finds wrong, and where the values came from. A duplicate is
 * named with a link to it; creating another one anyway needs a reason. */
export function ReviewPanel({
  product,
  form,
  body,
  missing,
  gaps,
  files,
  onAttach,
  onRemove,
  review,
  fresh,
  duplicates,
  override,
  reason,
  onOverride,
  onReason,
}: {
  product: string;
  form: IntakeProduct;
  body: CaseCreate;
  missing: string[];
  gaps: { section: string; row: number; field: string }[];
  files: File[];
  onAttach: (files: File[]) => void;
  onRemove: (index: number) => void;
  review: { data?: CaseProposal | undefined; isError: boolean };
  /** The engine's answer is for the values on screen now (not an earlier one). */
  fresh: boolean;
  duplicates: CaseSummary[];
  override: boolean;
  reason: string;
  onOverride: () => void;
  onReason: (reason: string) => void;
}) {
  const counts = countsBySource(body);
  const needed = [
    ...missing.map((k) => tOr(`intake.minimum.${k}`, k)),
    ...gaps.map((g) =>
      t("intake.review.rowGap", { row: rowLabel(g.section, g.row), field: fieldLabel(g.field) }),
    ),
  ];
  const wrong = Object.entries((fresh && review.data?.fields) || {}).filter(
    ([, f]) => f.status === "invalid" && f.source === "identifier" && f.note,
  );
  const duplicateState: State =
    duplicates.length || review.isError ? "warn" : fresh ? "ok" : "checking";
  const minimumState: State = needed.length ? "missing" : fresh ? "ok" : "checking";
  return (
    <Panel
      title={t("intake.review.title")}
      subtitle={t("intake.review.help")}
      testId="review-panel"
    >
      <ul className="divide-y divide-border">
        <Check id="review-minimum" state={minimumState}>
          {needed.length
            ? t("intake.review.minimumMissing", { fields: needed.join(", ") })
            : minimumState === "checking"
              ? t("intake.review.minimumChecking")
              : t("intake.review.minimumMet")}
        </Check>
        <Check id="review-files" state={files.length >= minFiles(form) ? "ok" : "missing"}>
          {files.length > 0
            ? t("intake.review.files", { n: files.length })
            : t("intake.review.filesNone")}
          <div className="mt-1.5 space-y-2">
            <FileList files={files} onRemove={onRemove} counted={false} />
            <AddFiles onFiles={onAttach} />
          </div>
        </Check>
        <Check id="review-duplicates" state={duplicateState}>
          {duplicates.length
            ? t("intake.review.duplicate")
            : review.isError
              ? t("intake.review.checkUnavailable")
              : duplicateState === "checking"
                ? t("intake.review.checking")
                : t("intake.review.noDuplicate")}
        </Check>
        {wrong.length > 0 && (
          <Check id="review-identifiers" state="warn">
            {wrong.map(([key, f]) => (
              <span key={key} className="block">
                {t("intake.review.identifier", {
                  field: identifierLabel(product, key),
                  note: f.note!,
                })}
              </span>
            ))}
          </Check>
        )}
        <li
          className="px-4 py-2 text-[11.5px] text-muted-foreground tabular"
          data-testid="review-sources"
        >
          {t("intake.review.sources", {
            counts: SOURCE_KINDS.filter((k) => counts[k] > 0)
              .map((k) => t(`intake.review.source.${k}`, { n: counts[k] }))
              .join(" · "),
          })}
        </li>
      </ul>
      {duplicates.length > 0 && (
        <DuplicateWarning
          duplicates={duplicates}
          override={override}
          reason={reason}
          onOverride={onOverride}
          onReason={onReason}
        />
      )}
    </Panel>
  );
}

function Check({ id, state, children }: { id: string; state: State; children: ReactNode }) {
  return (
    <li
      className="flex items-start gap-2 px-4 py-2 text-[12.5px] text-foreground"
      data-testid={id}
      data-state={state}
    >
      <StatusMark status={MARK[state]} className="mt-px" />
      <span className="min-w-0 flex-1">{children}</span>
    </li>
  );
}

/** A matching application on file (F-04.5): open it, or create another with a reason. */
function DuplicateWarning({
  duplicates,
  override,
  reason,
  onOverride,
  onReason,
}: {
  duplicates: CaseSummary[];
  override: boolean;
  reason: string;
  onOverride: () => void;
  onReason: (reason: string) => void;
}) {
  return (
    <div className="border-t border-flag/40 bg-flag-soft px-4 py-3" data-testid="duplicate-warning">
      <div className="flex flex-wrap items-start gap-2 text-[12.5px] text-flag-foreground">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1 space-y-1.5">
          {duplicates.slice(0, SHOWN_DUPLICATES).map((d) => (
            <p key={d.id} className="flex flex-wrap items-center gap-2">
              <span>{t("newApplication.duplicate", { id: d.id, borrower: d.borrower })}</span>
              <Link
                to="/appraisals/$caseId"
                params={{ caseId: d.id }}
                className="rounded border border-border bg-surface px-2 py-0.5 text-[12px] font-medium text-foreground hover:bg-muted"
              >
                {t("newApplication.openIt")}
              </Link>
            </p>
          ))}
          {duplicates.length > SHOWN_DUPLICATES && (
            <p data-testid="more-duplicates">
              {t("newApplication.moreDuplicates", { n: duplicates.length - SHOWN_DUPLICATES })}
            </p>
          )}
        </div>
        {!override && (
          <button
            type="button"
            onClick={onOverride}
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
            value={reason}
            onChange={(e) => onReason(e.target.value)}
            data-testid="override-reason"
          />
        </label>
      )}
    </div>
  );
}

/** More documents for the application, from a small text button (files, several or a ZIP). */
function AddFiles({ onFiles }: { onFiles: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-[12px] font-medium text-primary hover:bg-accent"
      >
        <Plus className="h-3.5 w-3.5" aria-hidden /> {t("intake.review.addFiles")}
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        data-testid="upload-input"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onFiles(files);
          e.target.value = "";
        }}
      />
    </>
  );
}
