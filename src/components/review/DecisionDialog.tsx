import { useState } from "react";
import { toast } from "sonner";
import type { FieldValue, ReviewDecision, ReviewItem } from "@/api/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState } from "@/components/common/States";
import { t } from "@/config/terminology";
import { useDocumentTypes } from "@/domain/documents";
import { formatValue } from "@/domain/extraction";
import { DECISIONS_BY_KIND, needsReason, useDecideReview } from "@/domain/review";
import { cn } from "@/lib/utils";

const inputClass =
  "mt-1 h-9 w-full rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";

/** Confirm, correct, waive or assign a type, with a reason where required (F-17.5, F-09.5). */
export function DecisionDialog({
  item,
  borrower,
  field,
  onClose,
}: {
  item: ReviewItem;
  borrower: string;
  /** For a field item: the extracted value under review, when readable. */
  field: FieldValue | undefined;
  onClose: () => void;
}) {
  const options = DECISIONS_BY_KIND[item.kind];
  const [decision, setDecision] = useState<ReviewDecision>(options[0]!);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const decide = useDecideReview();
  const types = useDocumentTypes();

  const valueNeeded = decision === "correct" || decision === "assign";
  const reasonNeeded = needsReason(decision);
  const ready = (!valueNeeded || value.trim() !== "") && (!reasonNeeded || reason.trim() !== "");

  const submit = () => {
    decide.mutate(
      {
        id: item.id,
        body: {
          decision,
          reason: reason.trim() || null,
          value: valueNeeded ? value.trim() : null,
        },
      },
      {
        onSuccess: () => {
          toast.success(t("review.recorded"));
          onClose();
        },
      },
    );
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg" data-testid="decision-dialog">
        <DialogHeader>
          <DialogTitle>{t(`reviewKind.${item.kind}`)}</DialogTitle>
          <DialogDescription>
            {borrower} · {item.case_id}
          </DialogDescription>
        </DialogHeader>
        <p className="rounded border border-border bg-surface-muted px-3 py-2 text-[12.5px] text-foreground">
          {item.summary}
        </p>
        {field && (
          <p className="text-[12.5px] text-muted-foreground">
            {t("review.systemValue")}{" "}
            <span className="tabular font-medium text-foreground">{formatValue(field.value)}</span>
          </p>
        )}

        <fieldset className="space-y-1.5">
          <legend className="field-label">{t("review.decision")}</legend>
          <div className="flex flex-wrap gap-2">
            {options.map((d) => (
              <label
                key={d}
                className={cn(
                  "flex cursor-pointer items-center gap-1.5 rounded border px-2.5 py-1 text-[12.5px]",
                  decision === d ? "border-primary/50 bg-primary/10 text-primary" : "border-border",
                )}
              >
                <input
                  type="radio"
                  name="decision"
                  value={d}
                  checked={decision === d}
                  onChange={() => {
                    setDecision(d);
                    setValue("");
                  }}
                  className="sr-only"
                />
                {t(`reviewDecision.${d}`)}
              </label>
            ))}
          </div>
        </fieldset>

        {decision === "assign" && (
          <label className="block">
            <span className="field-label">{t("review.assignType")}</span>
            <select
              className={inputClass}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              data-testid="assign-type"
            >
              <option value="">{t("review.chooseType")}</option>
              {(types.data?.types ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
            {types.isError && <ErrorState error={types.error} compact />}
          </label>
        )}
        {decision === "correct" && (
          <label className="block">
            <span className="field-label">{t("review.correctValue")}</span>
            <input
              className={inputClass}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              data-testid="correct-value"
            />
          </label>
        )}
        <label className="block">
          <span className="field-label">
            {reasonNeeded ? t("review.reasonRequired") : t("review.reasonOptional")}
          </span>
          <textarea
            rows={2}
            className="mt-1 w-full resize-none rounded border border-border bg-surface p-2.5 text-[13px] outline-none focus:ring-1 focus:ring-ring"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="decision-reason"
          />
        </label>
        <p className="text-[11.5px] text-muted-foreground">{t("review.overlayNote")}</p>

        {decide.isError && <ErrorState error={decide.error} compact />}

        <DialogFooter>
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
          >
            {t("action.cancel")}
          </button>
          <button
            type="button"
            disabled={!ready || decide.isPending}
            onClick={submit}
            data-testid="record-decision"
            className="h-9 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          >
            {t("review.record")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
