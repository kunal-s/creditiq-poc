import { useState } from "react";
import { toast } from "sonner";
import type { FieldValue } from "@/api/types";
import { decisionButton } from "@/components/review/styles";
import { t } from "@/config/terminology";
import { formatValue } from "@/domain/extraction";
import { useConfirmField, useDecideReview, useFieldItem } from "@/domain/review";
import { useCan } from "@/domain/session";

/** In the evidence viewer: confirm, or type the correct value and a reason. */
export function ViewerDecision({ field, correct }: { field: FieldValue; correct: boolean }) {
  const item = useFieldItem(field);
  const canDecide = useCan("review.decide");
  const decide = useDecideReview();
  const [editing, setEditing] = useState(correct);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const { confirm, pending } = useConfirmField(item);
  if (!item || !canDecide) return null;

  const save = () => {
    const like = field.value;
    const raw = value.trim();
    const n = Number(raw.replace(/,/g, ""));
    const typed = typeof like === "number" && !Number.isNaN(n) ? n : raw;
    decide.mutate(
      { id: item.id, body: { decision: "correct", value: typed, reason: reason.trim() } },
      {
        onSuccess: () => {
          toast.success(t("review.recorded"));
          setEditing(false);
        },
        onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
      },
    );
  };
  const input =
    "h-8 w-full min-w-0 rounded border border-border bg-surface px-2 text-[12.5px] outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";

  return (
    <div
      className="rounded border border-flag/40 bg-flag-soft/60 px-3 py-2"
      data-testid="viewer-decision"
    >
      <p className="text-[12px] text-flag-foreground">
        {t("fieldDecision.prompt", { value: formatValue(field.value) })}
      </p>
      {!editing ? (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={pending}
            onClick={confirm}
            className={`${decisionButton} border-positive/40 bg-surface text-positive hover:bg-positive-soft`}
            data-testid="viewer-confirm"
          >
            {t("fieldDecision.confirm")}
          </button>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className={`${decisionButton} border-border bg-surface text-foreground hover:bg-muted`}
            data-testid="viewer-correct"
          >
            {t("fieldDecision.correct")}
          </button>
        </div>
      ) : (
        <div className="mt-1.5 grid gap-1.5 sm:grid-cols-[10rem_minmax(0,1fr)_auto]">
          <input
            className={input}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={t("fieldDecision.value")}
            aria-label={t("fieldDecision.value")}
            data-testid="viewer-value-input"
            autoFocus
          />
          <input
            className={input}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("fieldDecision.reason")}
            aria-label={t("fieldDecision.reason")}
            data-testid="viewer-reason-input"
          />
          <button
            type="button"
            disabled={decide.isPending || value.trim() === "" || reason.trim() === ""}
            onClick={save}
            className="h-8 rounded bg-primary px-3 text-[12px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            data-testid="viewer-save"
          >
            {t("fieldDecision.save")}
          </button>
        </div>
      )}
    </div>
  );
}
