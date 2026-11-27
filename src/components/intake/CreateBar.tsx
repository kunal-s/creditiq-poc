// Test ids: create-blockers, missing-minimum, row-gaps, need-files, pending-confirmation,
// duplicate-blocker, create-application.
import { ArrowRight } from "lucide-react";
import { ErrorState } from "@/components/common/States";
import { t, tOr } from "@/config/terminology";
import { fieldLabel } from "./labels";
import { rowLabel } from "./labels";

/** Step 5: Create, with what still stops it said beside the button — the minimum, rows missing a
 * required value, the documents, values to confirm and a duplicate without a reason. The case and
 * its files are sent together; when that fails nothing is created and the error shows here. On a
 * phone the bar stays at the foot of the screen. */
export function CreateBar({
  checking,
  missing,
  gaps,
  needFiles,
  pending,
  duplicateBlocked,
  creating,
  error,
  onDiscard,
  onCreate,
}: {
  /** The engine has not yet answered for the values on screen. */
  checking: boolean;
  missing: string[];
  gaps: { section: string; row: number; field: string }[];
  needFiles: boolean;
  pending: string[];
  duplicateBlocked: boolean;
  creating: boolean;
  error: unknown;
  onDiscard: () => void;
  onCreate: () => void;
}) {
  const blocked =
    checking ||
    missing.length > 0 ||
    gaps.length > 0 ||
    needFiles ||
    pending.length > 0 ||
    duplicateBlocked;
  return (
    <div className="sticky bottom-0 z-10 -mx-4 space-y-2 border-t border-border bg-surface/95 px-4 py-2.5 backdrop-blur-sm sm:-mx-6 sm:px-6">
      {error ? <ErrorState error={error} compact /> : null}
      <div className="flex flex-wrap items-center justify-end gap-2">
        {blocked && (
          <ul
            className="mr-auto min-w-0 space-y-0.5 text-[12px] text-flag-foreground"
            data-testid="create-blockers"
          >
            {checking && <li data-testid="create-checking">{t("intake.create.checking")}</li>}
            {missing.length > 0 && (
              <li data-testid="missing-minimum">
                {t("newApplication.stillNeeded", {
                  fields: missing.map((k) => tOr(`intake.minimum.${k}`, k)).join(", "),
                })}
              </li>
            )}
            {gaps.length > 0 && (
              <li data-testid="row-gaps">
                {t("intake.create.stillRows", {
                  fields: gaps
                    .map((g) =>
                      t("intake.review.rowGap", {
                        row: rowLabel(g.section, g.row),
                        field: fieldLabel(g.field),
                      }),
                    )
                    .join(", "),
                })}
              </li>
            )}
            {needFiles && <li data-testid="need-files">{t("intake.create.needFiles")}</li>}
            {pending.length > 0 && (
              <li data-testid="pending-confirmation">
                {t("newApplication.stillToConfirm", {
                  fields: pending.map((k) => fieldLabel(k)).join(", "),
                })}
              </li>
            )}
            {duplicateBlocked && (
              <li data-testid="duplicate-blocker">{t("newApplication.duplicateBlocker")}</li>
            )}
          </ul>
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
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </div>
  );
}
