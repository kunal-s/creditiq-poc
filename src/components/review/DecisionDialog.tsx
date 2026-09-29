import { useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";
import type { FieldValue, ReviewDecision, ReviewDecisionRequest, ReviewItem } from "@/api/types";
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
import { formatValue, useParties } from "@/domain/extraction";
import { DECISIONS_BY_KIND, needsReason, useDecideReview } from "@/domain/review";
import { cn } from "@/lib/utils";

const inputClass =
  "mt-1 h-9 w-full min-w-0 rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";

type Scalar = string | number | boolean | null;

/** A typed value keeps a number a number (the engine stores it as given). */
function asScalar(raw: string, like?: Scalar): Scalar {
  const s = raw.trim();
  if (typeof like === "number" || (like === undefined && /^-?\d+(\.\d+)?$/.test(s))) {
    const n = Number(s.replace(/,/g, ""));
    if (!Number.isNaN(n)) return n;
  }
  return s;
}

/** Confirm, correct, waive or assign, with a reason where required (F-17.5).
 * "Correct" means: a new value (field), another party (party), or manual
 * entry of the document's values by a maker (quality, F-07.5). */
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
  const [decision, setDecision] = useState<ReviewDecision>(options[0] ?? "confirm");
  const [value, setValue] = useState("");
  const [rows, setRows] = useState<{ name: string; value: string }[]>([{ name: "", value: "" }]);
  const [reason, setReason] = useState("");
  const decide = useDecideReview();
  const types = useDocumentTypes();
  const manual = item.kind === "quality" && decision === "correct";
  const partyCorrect = item.kind === "party" && decision === "correct";
  const parties = useParties(item.case_id);

  const entries = rows.filter((r) => r.name.trim() !== "");
  const valueNeeded = decision === "assign" || (decision === "correct" && !manual);
  const reasonNeeded = needsReason(decision);
  const ready =
    (!valueNeeded || value.trim() !== "") &&
    (!manual || entries.length > 0) &&
    (!reasonNeeded || reason.trim() !== "");

  const submit = () => {
    const body: ReviewDecisionRequest = { decision, reason: reason.trim() || null, value: null };
    if (valueNeeded) body.value = item.kind === "field" ? asScalar(value, field?.value) : value;
    if (manual) {
      body.values = Object.fromEntries(entries.map((r) => [r.name.trim(), asScalar(r.value)]));
      if (value) body.value = value;
    }
    decide.mutate(
      { id: item.id, body },
      {
        onSuccess: () => {
          toast.success(t("review.recorded"));
          onClose();
        },
      },
    );
  };

  const typeSelect = (label: string) => (
    <label className="block">
      <span className="field-label">{label}</span>
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
  );

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-lg overflow-y-auto"
        data-testid="decision-dialog"
      >
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
                {item.kind === "quality" && d === "correct"
                  ? t("review.manualEntry")
                  : t(`reviewDecision.${d}`)}
              </label>
            ))}
          </div>
        </fieldset>

        {decision === "assign" && typeSelect(t("review.assignType"))}

        {decision === "correct" && item.kind === "field" && (
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

        {partyCorrect && (
          <label className="block">
            <span className="field-label">{t("review.party")}</span>
            <select
              className={inputClass}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              data-testid="correct-party"
            >
              <option value="">{t("review.chooseParty")}</option>
              {(parties.data ?? [])
                .filter((p) => p.role !== "borrower")
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} · {t(`partyRole.${p.role}`)}
                  </option>
                ))}
              <option value="none">{t("review.noParty")}</option>
            </select>
            {parties.isError && <ErrorState error={parties.error} compact />}
          </label>
        )}

        {manual && (
          <div className="space-y-2" data-testid="manual-entry">
            <p className="text-[12px] text-muted-foreground">{t("review.manualEntryHelp")}</p>
            {rows.map((r, i) => (
              <div key={i} className="flex items-end gap-2">
                <label className="block min-w-0 flex-1">
                  <span className="field-label">{t("review.fieldName")}</span>
                  <input
                    className={inputClass}
                    value={r.name}
                    onChange={(e) =>
                      setRows(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
                    }
                  />
                </label>
                <label className="block min-w-0 flex-1">
                  <span className="field-label">{t("review.fieldValue")}</span>
                  <input
                    className={inputClass}
                    value={r.value}
                    onChange={(e) =>
                      setRows(rows.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))
                    }
                  />
                </label>
                <button
                  type="button"
                  aria-label={t("action.remove")}
                  onClick={() => setRows(rows.filter((_, j) => j !== i))}
                  className="mb-1 rounded p-1.5 text-muted-foreground hover:bg-muted"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setRows([...rows, { name: "", value: "" }])}
              className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-[12px] font-medium hover:bg-muted"
            >
              <Plus className="h-3 w-3" /> {t("review.addField")}
            </button>
            {typeSelect(t("review.manualType"))}
          </div>
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
