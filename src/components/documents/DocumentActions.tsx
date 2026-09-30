import { useState } from "react";
import { toast } from "sonner";
import type { LogicalDocument, ReviewItem } from "@/api/types";
import { DecisionDialog } from "@/components/review/DecisionDialog";
import { t } from "@/config/terminology";
import { useDocumentTypes } from "@/domain/documents";
import { useCan } from "@/domain/session";
import { useDecideReview } from "@/domain/review";

const MAX_CANDIDATES = 3;

/**
 * What a person can do about a document, on its register row (FRD §6): an
 * unclassified document offers its top candidate types to assign in one
 * click (F-09.5); a quality, split or party item opens the review decision.
 * Without the permission to decide, the row says it is waiting for review.
 */
export function DocumentActions({
  doc,
  items,
  borrower,
}: {
  doc: LogicalDocument;
  items: ReviewItem[];
  borrower: string;
}) {
  const canDecide = useCan("review.decide");
  const types = useDocumentTypes();
  const decide = useDecideReview();
  const [open, setOpen] = useState<ReviewItem | null>(null);
  if (items.length === 0) return null;
  if (!canDecide) {
    return (
      <span className="text-[11px] text-muted-foreground" data-testid="waiting-review">
        {t("documents.waitingReview")}
      </span>
    );
  }

  const typeItem = items.find((i) => i.kind === "type");
  const others = items.filter((i) => i.kind !== "type");
  const candidates = (doc.classification?.candidates ?? []).slice(0, MAX_CANDIDATES);
  const assign = (item: ReviewItem, typeId: string) =>
    decide.mutate(
      { id: item.id, body: { decision: "assign", value: typeId, reason: null } },
      {
        onSuccess: () => toast.success(t("documents.assigned", { type: types.name(typeId) })),
        onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
      },
    );
  const button =
    "rounded border px-2 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-50";

  return (
    <span className="flex flex-wrap items-center gap-1" data-testid="document-actions">
      {typeItem && (
        <>
          <span className="text-[11px] text-muted-foreground">{t("documents.assignAs")}</span>
          {candidates.map((c) => (
            <button
              key={c.type_id}
              type="button"
              disabled={decide.isPending}
              onClick={() => assign(typeItem, c.type_id)}
              className={`${button} border-primary/40 bg-surface text-primary hover:bg-primary/10`}
              data-testid="assign-candidate"
            >
              {types.name(c.type_id)} {Math.round(c.confidence * 100)}%
            </button>
          ))}
          <button
            type="button"
            onClick={() => setOpen(typeItem)}
            className={`${button} border-border bg-surface text-muted-foreground hover:bg-muted`}
            data-testid="assign-other"
          >
            {t("documents.otherType")}
          </button>
        </>
      )}
      {others.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => setOpen(item)}
          className={`${button} border-flag/40 bg-flag-soft text-flag-foreground hover:bg-flag-soft/70`}
          data-testid={`resolve-${item.kind}`}
        >
          {t("documents.resolve", { kind: t(`reviewKind.${item.kind}`) })}
        </button>
      ))}
      {open && (
        <DecisionDialog
          item={open}
          borrower={borrower}
          field={undefined}
          onClose={() => setOpen(null)}
        />
      )}
    </span>
  );
}
