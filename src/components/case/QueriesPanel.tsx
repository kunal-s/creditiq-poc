import { Check, Copy, FileText, Mail } from "lucide-react";
import { toast } from "sonner";
import type { QueryItem } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useCase } from "@/domain/cases";
import { useQueryList } from "@/domain/checklist";
import { numbered, queryListEmail, queryListText } from "@/domain/queries";
import { cn } from "@/lib/utils";

async function copy(text: string, done: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(done);
  } catch {
    toast.error(t("queries.copyFailed"));
  }
}

/** The pre-login query list (F-14): everything to ask the customer, ready
 * to copy as an email or as text. */
export function QueriesPanel({ caseId }: { caseId: string }) {
  const { data: c } = useCase(caseId);
  const queries = useQueryList(caseId);
  const items = queries.data ?? [];
  const open = items.filter((i) => !i.resolved);
  const resolved = items.filter((i) => i.resolved);

  return (
    <Panel
      title={t("term.queryList")}
      subtitle={
        queries.data
          ? t("queries.subtitle", { open: open.length, resolved: items.length - open.length })
          : undefined
      }
      testId="query-list"
      action={
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            disabled={open.length === 0 || !c}
            onClick={() => c && void copy(queryListEmail(c, items), t("queries.copiedEmail"))}
            className="inline-flex items-center gap-1.5 rounded bg-primary px-2.5 py-1 text-[12px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          >
            <Mail className="h-3.5 w-3.5" /> {t("queries.copyEmail")}
          </button>
          <button
            type="button"
            disabled={open.length === 0}
            onClick={() => void copy(queryListText(items), t("queries.copiedText"))}
            className="inline-flex items-center gap-1.5 rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted disabled:opacity-40"
          >
            <Copy className="h-3.5 w-3.5" /> {t("queries.copyText")}
          </button>
        </div>
      }
    >
      <QueryView
        query={queries}
        compact
        isEmpty={(list) => list.length === 0}
        empty={{ title: t("queries.emptyTitle"), description: t("queries.emptyDescription") }}
      >
        {() => (
          <>
            <div className="divide-y divide-border">
              {numbered(open).map((g) => (
                <div key={g.group} data-testid={`query-group-${g.group}`}>
                  <p className="bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t(`queryGroup.${g.group}`)} · {g.items.length}
                  </p>
                  <ol className="divide-y divide-border">
                    {g.items.map(({ n, item }) => (
                      <QueryRow key={item.id} caseId={caseId} n={n} item={item} />
                    ))}
                  </ol>
                </div>
              ))}
              {resolved.length > 0 && (
                <div data-testid="query-group-resolved">
                  <p className="bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t("queries.resolvedGroup")} · {resolved.length}
                  </p>
                  <ol className="divide-y divide-border">
                    {resolved.map((item) => (
                      <QueryRow key={item.id} caseId={caseId} n={0} item={item} />
                    ))}
                  </ol>
                </div>
              )}
            </div>
            <p className="border-t border-border px-4 py-2 text-[11.5px] text-muted-foreground">
              {t("queries.nothingSent")}
            </p>
          </>
        )}
      </QueryView>
    </Panel>
  );
}

function QueryRow({ caseId, n, item }: { caseId: string; n: number; item: QueryItem }) {
  const viewer = useDocViewer();
  const evidence = item.evidence?.[0];
  return (
    <li
      className={cn(
        "flex flex-wrap items-start gap-2 px-4",
        item.resolved ? "bg-surface-muted/40 py-1.5 text-[12px]" : "py-2.5",
      )}
      data-testid="query-item"
      data-resolved={item.resolved}
    >
      <span className="tabular w-6 shrink-0 text-[12.5px] font-medium text-foreground">
        {item.resolved ? <Check className="mt-0.5 h-3.5 w-3.5 text-positive" /> : `${n}.`}
      </span>
      <span
        className={cn(
          "min-w-0 flex-1 text-[12.5px] leading-relaxed",
          item.resolved ? "text-muted-foreground line-through" : "text-foreground",
        )}
      >
        {item.text}
      </span>
      {item.resolved && <Chip tone="positive">{t("queries.resolved")}</Chip>}
      {evidence && (
        <button
          type="button"
          onClick={() =>
            viewer.open({
              caseId,
              documentId: evidence.document_id,
              page: evidence.page,
              bbox: evidence.bbox ?? null,
            })
          }
          className="inline-flex items-center gap-1 text-[11.5px] font-medium text-primary hover:underline"
        >
          <FileText className="h-3 w-3" /> {t("queries.evidence")}
        </button>
      )}
    </li>
  );
}
