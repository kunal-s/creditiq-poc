import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import type { LogicalDocument, ReviewItem } from "@/api/types";
import { DecisionDialog } from "@/components/review/DecisionDialog";
import { NewCaseTypeDialog } from "./NewCaseTypeDialog";
import { t } from "@/config/terminology";
import { useDocumentTypes } from "@/domain/documents";
import { useCan } from "@/domain/session";
import { useDecideReview } from "@/domain/review";

const MAX_CANDIDATES = 3;

/**
 * What a person can do about a document, on its register row (FRD §6): an
 * unclassified document offers its top candidate types to assign in one
 * click (F-09.5), any published type or one made for this appraisal from a
 * list (F-09.7), a new type when none fits (F-09.8), and the review decision
 * to waive it; a quality, split or party item opens the review decision.
 * Without the permission to decide, the row says it is waiting for review.
 *
 * Test ids: document-actions, assign-candidate, assign-choose, assign-chosen,
 * assign-new, assign-other, resolve-<kind>, none-close, waiting-review.
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
  const [creating, setCreating] = useState(false);
  const [chosen, setChosen] = useState("");
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
  // A type that matched nothing of the document (0%) is no suggestion: only the others are offered.
  const candidates = (doc.classification?.candidates ?? [])
    .filter((c) => Math.round(c.confidence * 100) > 0)
    .slice(0, MAX_CANDIDATES);
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
          {candidates.length > 0 ? (
            <span className="text-[11px] text-muted-foreground">{t("documents.assignAs")}</span>
          ) : (
            <span className="text-[11px] text-muted-foreground" data-testid="none-close">
              {t("documents.noneClose")}
            </span>
          )}
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
          {/* Any published type, or one already made for this appraisal: chosen, then assigned. */}
          <span className="inline-flex items-center gap-1">
            <select
              value={chosen}
              onChange={(e) => setChosen(e.target.value)}
              aria-label={t("documents.chooseType")}
              className="h-[22px] max-w-[11rem] rounded border border-border bg-surface px-1 text-[11px] text-foreground"
              data-testid="assign-choose"
            >
              <option value="">{t("documents.chooseType")}</option>
              {types.caseTypes.length > 0 && (
                <optgroup label={t("documents.thisAppraisal")}>
                  {types.caseTypes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </optgroup>
              )}
              <optgroup label={t("documents.publishedList")}>
                {(types.data?.types ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </optgroup>
            </select>
            {chosen && (
              <button
                type="button"
                disabled={decide.isPending}
                onClick={() => assign(typeItem, chosen)}
                className={`${button} border-primary/40 bg-surface text-primary hover:bg-primary/10`}
                data-testid="assign-chosen"
              >
                {t("documents.assign")}
              </button>
            )}
          </span>
          <button
            type="button"
            onClick={() => setCreating(true)}
            title={t("documents.newTypeHelp")}
            className={`${button} inline-flex items-center gap-0.5 border-border bg-surface text-primary hover:bg-muted`}
            data-testid="assign-new"
          >
            <Plus className="h-3 w-3" aria-hidden />
            {t("documents.newType")}
          </button>
          <button
            type="button"
            onClick={() => setOpen(typeItem)}
            title={t("documents.otherTypeHelp")}
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
      {creating && typeItem && (
        <NewCaseTypeDialog doc={doc} item={typeItem} onClose={() => setCreating(false)} />
      )}
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
