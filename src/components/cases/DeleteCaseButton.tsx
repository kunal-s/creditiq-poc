import { useNavigate } from "@tanstack/react-router";
import { MoreHorizontal, Trash2 } from "lucide-react";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { t } from "@/config/terminology";
import { useDeleteCase } from "@/domain/cases";
import { useCan } from "@/domain/session";

/** The case header's "More" menu: the actions a person rarely needs, kept off the header itself.
 * Today it holds the case's deletion, for a role that may delete. */
export function CaseMoreMenu({ caseId, borrower }: { caseId: string; borrower: string }) {
  const allowed = useCan("case.delete");
  const [open, setOpen] = useState(false);
  if (!allowed) return null;
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={t("caseHeader.more")}
            title={t("caseHeader.more")}
            className="grid size-8 place-items-center rounded text-muted-foreground hover:bg-surface-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            data-testid="case-more"
          >
            <MoreHorizontal className="size-4" aria-hidden />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => setOpen(true)}
            className="text-critical-text focus:text-critical-text"
            data-testid="delete-case"
          >
            <Trash2 className="size-3.5" aria-hidden />
            {t("caseDelete.action")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <DeleteCaseButton caseId={caseId} borrower={borrower} open={open} onOpenChange={setOpen} />
    </>
  );
}

/** F-01.5: delete a case and everything it owns. The person types the case
 * ID and gives a reason; the engine keeps a record of the deletion. Opened by its own button, or,
 * given `open`, by whoever holds that state (the header's "More" menu). */
export function DeleteCaseButton({
  caseId,
  borrower,
  open: controlled,
  onOpenChange,
}: {
  caseId: string;
  borrower: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const allowed = useCan("case.delete");
  const navigate = useNavigate();
  const del = useDeleteCase();
  const [own, setOwn] = useState(false);
  const open = controlled ?? own;
  const setOpen = (next: boolean) => (onOpenChange ? onOpenChange(next) : setOwn(next));
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
      {controlled === undefined && (
        <AlertDialogTrigger asChild>
          <button
            type="button"
            aria-label={t("caseDelete.action")}
            className="inline-flex items-center gap-1 rounded px-2 py-1.5 text-[11.5px] font-medium text-muted-foreground hover:bg-destructive/5 hover:text-critical-text"
            data-testid="delete-case"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">{t("caseDelete.action")}</span>
          </button>
        </AlertDialogTrigger>
      )}
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
          {error && <p className="text-[12px] text-critical-text">{error}</p>}
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
