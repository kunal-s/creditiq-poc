import { useState } from "react";
import { toast } from "sonner";
import type { CellSource, EditTarget } from "@/api/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { refusal } from "@/domain/errors";
import { inRupees, useEditStatementLine, useRevertStatementEdit } from "@/domain/statementEdits";
import { cn } from "@/lib/utils";

const field =
  "mt-1 block w-full rounded border border-border bg-surface px-2 py-1.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20";

/** Type a statement figure as the statement prints it, with a reason. The rupee value it comes to is
 * shown as it is typed, so a missing or extra zero is seen before it is saved. */
export function EditFigureDialog({
  caseId,
  label,
  fy,
  target,
  source,
  current,
  onClose,
}: {
  caseId: string;
  label: string;
  fy: string;
  target: EditTarget;
  source: CellSource | null | undefined;
  /** The figure now standing, in the statement's own unit. */
  current: number | null;
  onClose: () => void;
}) {
  const [amount, setAmount] = useState(current === null ? "" : String(current));
  const [reason, setReason] = useState("");
  const save = useEditStatementLine(caseId);
  const value = amount.trim() === "" ? NaN : Number(amount.replace(/,/g, ""));
  const scale = source?.scale ?? 1;
  const refused = save.isError ? refusal(save.error) : null;
  const ready = Number.isFinite(value) && reason.trim().length >= 3;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md" data-testid="figure-edit-dialog">
        <DialogHeader>
          <DialogTitle>{t("spreadPage.edit.title")}</DialogTitle>
          <DialogDescription>
            {fy ? t("spreadPage.edit.subtitle", { label, fy }) : label}
          </DialogDescription>
        </DialogHeader>
        <label className="block">
          <span className="field-label">
            {t("spreadPage.edit.entry", { unit: source?.unit_label ?? "INR" })}
          </span>
          <input
            className={cn(field, "tabular")}
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            data-testid="figure-edit-amount"
          />
          <span className="mt-1 block text-[11.5px] text-muted-foreground">
            {Number.isFinite(value)
              ? t("spreadPage.edit.entryRupees", { rupees: inRupees(value * scale) })
              : t("spreadPage.edit.entryHint")}
          </span>
        </label>
        <label className="block">
          <span className="field-label">{t("spreadPage.edit.reason")}</span>
          <input
            className={field}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="figure-edit-reason"
          />
          <span className="mt-1 block text-[11.5px] text-muted-foreground">
            {t("spreadPage.edit.reasonHint")}
          </span>
        </label>
        {refused && (
          <p
            className="text-[12.5px] text-destructive"
            role="alert"
            data-testid="figure-edit-refused"
          >
            {refused}
          </p>
        )}
        <DialogFooter className="gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border px-3 py-1.5 text-[13px]"
          >
            {t("spreadPage.edit.cancel")}
          </button>
          <button
            type="button"
            disabled={!ready || save.isPending}
            onClick={() =>
              save.mutate(
                { ...target, value, reason: reason.trim() },
                {
                  onSuccess: () => {
                    toast.success(t("spreadPage.edit.saved"));
                    onClose();
                  },
                },
              )
            }
            className="rounded bg-primary px-3 py-1.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
            data-testid="figure-edit-save"
          >
            {t("spreadPage.edit.save")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Put the statement's own figure back, with the reason; the edit stays in the history. */
export function RevertFigureDialog({
  caseId,
  editId,
  onClose,
}: {
  caseId: string;
  editId: string;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const revert = useRevertStatementEdit(caseId);
  const refused = revert.isError ? refusal(revert.error) : null;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md" data-testid="figure-revert-dialog">
        <DialogHeader>
          <DialogTitle>{t("spreadPage.edit.revertTitle")}</DialogTitle>
          <DialogDescription>{t("spreadPage.edit.revertReason")}</DialogDescription>
        </DialogHeader>
        <input
          className={field}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          data-testid="figure-revert-reason"
        />
        {refused && (
          <p className="text-[12.5px] text-destructive" role="alert">
            {refused}
          </p>
        )}
        <DialogFooter className="gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border px-3 py-1.5 text-[13px]"
          >
            {t("spreadPage.edit.cancel")}
          </button>
          <button
            type="button"
            disabled={reason.trim().length < 3 || revert.isPending}
            onClick={() =>
              revert.mutate(
                { edit: editId, reason: reason.trim() },
                {
                  onSuccess: () => {
                    toast.success(t("spreadPage.edit.reverted"));
                    onClose();
                  },
                },
              )
            }
            className="rounded bg-primary px-3 py-1.5 text-[13px] font-medium text-primary-foreground disabled:opacity-50"
            data-testid="figure-revert-save"
          >
            {t("spreadPage.working.revert")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
