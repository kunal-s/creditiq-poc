import { useRef, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import type { FileRecord } from "@/api/types";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { t } from "@/config/terminology";
import { ACCEPT, useRemoveFile, useReplaceFile } from "@/domain/documents";
import { useCan } from "@/domain/session";

/** A file's own actions on the register, after its size: "Replace" (a new upload in its place) and
 * "Remove" (off the case, after a confirmation). Whatever the file's outcome, registered, refused or
 * in exception; the engine forgets its content, so the same file may be uploaded again. Not offered
 * while the file is still being read. Test ids: file-replace, file-replace-input, file-remove,
 * file-remove-confirm. */
export function FileActions({
  caseId,
  file,
  reading,
}: {
  caseId: string;
  file: FileRecord;
  /** The file is still being read: its actions wait. */
  reading: boolean;
}) {
  const canUpload = useCan("document.upload");
  const remove = useRemoveFile(caseId);
  const replace = useReplaceFile(caseId);
  const input = useRef<HTMLInputElement>(null);
  const [confirming, setConfirming] = useState(false);
  if (!canUpload) return null;

  const busy = reading || remove.isPending || replace.isPending;
  const name = file.archive_path ?? file.original_name;
  const action =
    "inline-flex items-center gap-1 rounded px-1 py-0.5 text-[11px] font-medium text-muted-foreground hover:bg-surface-muted hover:text-primary disabled:pointer-events-none disabled:opacity-50";

  function onPick(files: FileList | null) {
    const picked = Array.from(files ?? []);
    if (input.current) input.current.value = "";
    if (picked.length === 0) return;
    replace.mutate(
      { fileId: file.id, files: picked },
      { onError: () => toast.error(t("documents.fileActions.replaceFailed")) },
    );
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-testid="file-actions">
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => onPick(e.target.files)}
        data-testid="file-replace-input"
      />
      <button
        type="button"
        className={action}
        disabled={busy}
        onClick={() => input.current?.click()}
        title={t(
          reading ? "documents.fileActions.readingFirst" : "documents.fileActions.replaceHelp",
        )}
        data-testid="file-replace"
      >
        <RefreshCw className={replace.isPending ? "h-3 w-3 animate-spin" : "h-3 w-3"} aria-hidden />
        {t(replace.isPending ? "documents.fileActions.replacing" : "documents.fileActions.replace")}
      </button>
      <button
        type="button"
        className={`${action} hover:text-critical-text`}
        disabled={busy}
        onClick={() => setConfirming(true)}
        title={t(
          reading ? "documents.fileActions.readingFirst" : "documents.fileActions.removeHelp",
        )}
        data-testid="file-remove"
      >
        <Trash2 className="h-3 w-3" aria-hidden />
        {t(remove.isPending ? "documents.fileActions.removing" : "documents.fileActions.remove")}
      </button>
      <AlertDialog
        open={confirming}
        onOpenChange={(next) => {
          setConfirming(next);
          if (!next) remove.reset();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="[overflow-wrap:anywhere]">
              {t("documents.fileActions.removeTitle", { name })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("documents.fileActions.removeDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {remove.isError && (
            <p className="text-[12px] text-critical-text">{t("documents.fileActions.failed")}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel>{t("documents.fileActions.cancel")}</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate(file.id, { onSuccess: () => setConfirming(false) })}
              data-testid="file-remove-confirm"
            >
              {t(
                remove.isPending
                  ? "documents.fileActions.removing"
                  : "documents.fileActions.removeConfirm",
              )}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </span>
  );
}
