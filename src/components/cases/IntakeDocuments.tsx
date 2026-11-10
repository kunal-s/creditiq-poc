import { Paperclip, X } from "lucide-react";
import type { ChecklistPreviewItem, ChecklistPreviewRequest } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { ErrorState } from "@/components/common/States";
import { UploadZone } from "@/components/documents/UploadZone";
import { t } from "@/config/terminology";
import { useChecklistPreview } from "@/domain/cases";
import { formatBytes } from "@/domain/documents";
import { cn } from "@/lib/utils";

/** The documents step of a new appraisal: files attached so far beside what the
 * application will need (F-12), worked out from the values on screen. Nothing is
 * matched to the list here: a file is read only once the application exists. */
export function IntakeDocuments({
  request,
  attachments,
  onAttach,
  onRemove,
}: {
  request: ChecklistPreviewRequest;
  attachments: File[];
  onAttach: (files: File[]) => void;
  onRemove: (index: number) => void;
}) {
  const preview = useChecklistPreview(request);
  const data = preview.data;
  const sections = data
    ? data.sections
        .map((name) => ({ name, items: data.items.filter((i) => i.category === name) }))
        .filter((s) => s.items.length > 0)
    : [];

  return (
    <Panel
      title={t("newApplication.documents.title")}
      subtitle={t("newApplication.documents.help")}
      testId="intake-documents"
    >
      <div className="@container/docs">
        <div className="grid divide-y divide-border @min-[44rem]/docs:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @min-[44rem]/docs:divide-x @min-[44rem]/docs:divide-y-0">
          <div className="min-w-0 space-y-2 p-4">
            <UploadZone compact onFiles={onAttach} />
            {attachments.length > 0 ? (
              <>
                <p className="field-label pt-1">
                  {t("newApplication.documents.attached", { n: attachments.length })}
                </p>
                <ul
                  className="max-h-64 space-y-1 overflow-auto text-[12px]"
                  data-testid="attachments"
                >
                  {attachments.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="flex items-center gap-2">
                      <Paperclip className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate" title={f.name}>
                        {f.name}
                      </span>
                      <span className="tabular text-muted-foreground">{formatBytes(f.size)}</span>
                      <button
                        type="button"
                        aria-label={t("action.remove")}
                        onClick={() => onRemove(i)}
                        className="rounded p-0.5 text-muted-foreground hover:bg-muted"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-[11.5px] text-muted-foreground">
                {t("newApplication.documents.noneAttached")}
              </p>
            )}
          </div>

          <div className="min-w-0 p-4" data-testid="documents-needed">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-[13px] font-semibold text-foreground">
                {data ? neededTitle(data.items) : t("newApplication.documents.neededLoading")}
              </p>
              {data?.provisional && (
                <Chip tone="flag">
                  <span data-testid="needed-provisional">{t("checklist.provisional")}</span>
                </Chip>
              )}
            </div>
            {data?.provisional && (
              <p className="mt-1 text-[11.5px] text-muted-foreground">
                {t("newApplication.documents.provisionalHelp")}
              </p>
            )}
            {preview.isError && !data ? (
              <div className="mt-2">
                <ErrorState error={preview.error} compact />
              </div>
            ) : (
              <dl className="mt-2 space-y-2">
                {sections.map((section) => (
                  <div key={section.name}>
                    <dt className="field-label">{section.name}</dt>
                    <dd className="mt-1 flex flex-wrap gap-1">
                      {section.items.map((item) => (
                        <span
                          key={item.id}
                          data-testid="needed-item"
                          data-blocking={item.blocking}
                          title={hint(item)}
                          className={cn(
                            "rounded border px-1.5 py-0.5 text-[11.5px] leading-snug",
                            item.blocking
                              ? "border-border bg-surface-muted text-foreground"
                              : "border-dashed border-border text-muted-foreground",
                          )}
                        >
                          {item.name}
                        </span>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            <p className="mt-2 text-[11px] text-muted-foreground">
              {t("newApplication.documents.after")}
            </p>
          </div>
        </div>
      </div>
    </Panel>
  );
}

/** "Will need 10 documents", naming the blocking ones only when some are not. */
function neededTitle(items: ChecklistPreviewItem[]): string {
  const blocking = items.filter((i) => i.blocking).length;
  return blocking === items.length
    ? t("newApplication.documents.needed", { n: items.length })
    : t("newApplication.documents.neededSome", { n: items.length, blocking });
}

/** Hover text: why the item is needed, what satisfies it, and whether it blocks. */
function hint(item: ChecklistPreviewItem): string {
  const name = item.name.trim().toLowerCase();
  const types = (item.document_types ?? []).filter((d) => d.trim().toLowerCase() !== name);
  return [
    item.why,
    types.length ? t("newApplication.documents.acceptedAs", { types: types.join(", ") }) : null,
    item.blocking ? null : t("newApplication.documents.notBlocking"),
  ]
    .filter(Boolean)
    .join("\n");
}
