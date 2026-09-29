import { useNavigate } from "@tanstack/react-router";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/config/terminology";
import { useDeleteCase } from "@/domain/cases";
import { useCan } from "@/domain/session";

/** F-01.5: delete a case and everything it owns. The person types the case
 * ID and gives a reason; the engine keeps a record of the deletion. */
export function DeleteCaseButton({ caseId, borrower }: { caseId: string; borrower: string }) {
  const allowed = useCan("case.delete");
  const navigate = useNavigate();
  const del = useDeleteCase();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");
  if (!allowed) return null;

  const ready = typed.trim() === caseId && reason.trim().length >= 3 && !del.isPending;

  function submit() {
    del.mutate(
      { id: caseId, reason: reason.trim() },
      {
        onSuccess: () => {
          setOpen(false);
          toast.success(t("caseDelete.done", { id: caseId }));
          void navigate({ to: "/" });
        },
      },
    );
  }

  const error =
    del.error instanceof ApiError && del.error.status === 409
      ? t("caseDelete.busy")
      : del.error
        ? t("caseDelete.failed")
        : null;

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setTyped("");
          setReason("");
          del.reset();
        }
      }}
    >
      <AlertDialogTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-border px-2.5 py-1.5 text-[11.5px] font-medium text-muted-foreground hover:border-destructive/40 hover:text-destructive"
          data-testid="delete-case"
        >
          <Trash2 className="h-3 w-3" /> {t("caseDelete.action")}
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("caseDelete.title", { id: caseId })}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("caseDelete.description", { borrower })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="delete-reason">{t("caseDelete.reason")}</Label>
            <Input
              id="delete-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder={t("caseDelete.reasonPlaceholder")}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="delete-confirm">{t("caseDelete.confirm", { id: caseId })}</Label>
            <Input
              id="delete-confirm"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              className="tabular"
            />
          </div>
          {error && <p className="text-[12px] text-destructive">{error}</p>}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("caseDelete.cancel")}</AlertDialogCancel>
          <Button
            variant="destructive"
            disabled={!ready}
            onClick={submit}
            data-testid="delete-case-confirm"
          >
            {del.isPending ? t("caseDelete.deleting") : t("caseDelete.submit")}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
