import type { UseMutationResult } from "@tanstack/react-query";
import { useState } from "react";
import type {
  SettingsChanges,
  SettingsPreview,
  SettingsPublished,
  SettingsPublishRequest,
} from "@/api/types";
import { ErrorState } from "@/components/common/States";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { publishProblems } from "@/domain/admin";
import { changeFieldLabel, formatChangeValue, NOTE_MIN } from "@/domain/settings";

/** Review the draft as the engine reads it (each change, and why it cannot be published if it
 * cannot), give the reason for it, and publish it as a new version (F-00.6). */
export function ReviewDialog({
  preview,
  publish,
  changes,
  onPublish,
  onClose,
}: {
  preview: UseMutationResult<SettingsPreview, Error, SettingsChanges>;
  publish: UseMutationResult<SettingsPublished, Error, SettingsPublishRequest>;
  /** What the draft changes, as previewed. */
  changes: SettingsChanges;
  onPublish: (note: string) => void;
  onClose: () => void;
}) {
  const [note, setNote] = useState("");
  const result = preview.data;
  const refused = publishProblems(publish.error);
  const problems = refused ?? result?.problems ?? [];
  const ready =
    result !== undefined &&
    !preview.isPending &&
    problems.length === 0 &&
    note.trim().length >= NOTE_MIN &&
    !publish.isPending;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-2xl overflow-y-auto"
        data-testid="settings-review-dialog"
      >
        <DialogHeader>
          <DialogTitle>{t("admin.settings.review.title")}</DialogTitle>
          <DialogDescription>{t("admin.settings.review.description")}</DialogDescription>
        </DialogHeader>

        {preview.isPending && (
          <p role="status" className="text-[12.5px] text-muted-foreground">
            {t("admin.settings.review.checking")}
          </p>
        )}
        {preview.isError && (
          <ErrorState error={preview.error} compact onRetry={() => preview.mutate(changes)} />
        )}
        {result && !preview.isPending && result.changes.length > 0 && (
          <ul
            className="divide-y divide-border rounded border border-border"
            data-testid="settings-changes"
          >
            {result.changes.map((c) => (
              <li
                key={`${c.section}-${c.item}-${c.label}-${c.field}`}
                className="px-3 py-2 text-[12.5px]"
                data-testid="settings-change"
              >
                <span className="font-medium text-foreground">{c.label}</span>
                <span className="text-muted-foreground"> · {changeFieldLabel(c.field)}: </span>
                <span className="tabular text-muted-foreground">
                  {formatChangeValue(c, c.before)}
                </span>
                <span className="text-muted-foreground"> → </span>
                <span className="tabular font-medium text-foreground">
                  {formatChangeValue(c, c.after)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {problems.length > 0 && !preview.isPending && (
          <div
            role="alert"
            className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2"
            data-testid="settings-problems"
          >
            <p className="text-[12px] font-semibold text-destructive">
              {t("admin.settings.review.problems")}
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12.5px] text-destructive">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        )}

        <label className="block">
          <span className="field-label">{t("admin.settings.review.note")}</span>
          <textarea
            rows={2}
            className="mt-1 w-full resize-none rounded border border-border bg-surface p-2.5 text-[13px] outline-none focus:ring-1 focus:ring-ring"
            value={note}
            required
            placeholder={t("admin.settings.review.notePlaceholder")}
            aria-describedby="settings-note-hint"
            onChange={(e) => {
              setNote(e.target.value);
              if (publish.isError) publish.reset();
            }}
            data-testid="settings-note"
          />
        </label>
        <p id="settings-note-hint" className="text-[11.5px] text-muted-foreground">
          {t("admin.settings.review.noteHelp", { n: NOTE_MIN })}
        </p>
        {publish.isError && !refused && <ErrorState error={publish.error} compact />}

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
            disabled={!ready}
            onClick={() => onPublish(note.trim())}
            data-testid="settings-publish"
            className="h-9 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          >
            {publish.isPending
              ? t("admin.settings.review.publishing")
              : t("admin.settings.review.publish")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
