import { useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";
import type { LogicalDocument, ReviewItem } from "@/api/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { t } from "@/config/terminology";
import { useChecklist, useTaxonomy } from "@/domain/checklist";
import { useMakeCaseDocumentType, useMapCaseDocumentType } from "@/domain/documents";
import { refusal } from "@/domain/errors";
import { useDecideReview } from "@/domain/review";

const inputClass =
  "mt-1 h-9 w-full min-w-0 rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring";

type Row = { key: number; name: string; hint: string };

/**
 * A document type made for one appraisal when no published type fits an
 * unclassified document (F-09.8): its name, what it is, and optionally the
 * fields to read. With no field named, the key fields are proposed from the
 * document and each waits in the review queue (F-15.8, F-17.7). It may be
 * set to count toward a checklist item that one document satisfies; a
 * mandatory item waits for a Credit Manager (F-09.9). Every step is the
 * engine's record: the type, its assignment and the mapping.
 *
 * Test ids: new-type-dialog, new-type-name, new-type-about, new-type-field,
 * new-type-hint, new-type-add-field, new-type-counts, new-type-reason,
 * new-type-create.
 */
export function NewCaseTypeDialog({
  doc,
  item,
  onClose,
}: {
  doc: LogicalDocument;
  item: ReviewItem;
  onClose: () => void;
}) {
  const make = useMakeCaseDocumentType(doc.case_id);
  const decide = useDecideReview();
  const map = useMapCaseDocumentType(doc.case_id);
  const checklist = useChecklist(doc.case_id);
  const taxonomy = useTaxonomy();
  const [name, setName] = useState("");
  const [about, setAbout] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [next, setNext] = useState(1);
  const [itemId, setItemId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Only an item one document satisfies can take a type made here: the others are checked by
  // years, periods, accounts or parties, which only a published type's fields give.
  const coverage = new Map((taxonomy.data?.items ?? []).map((i) => [i.id, i.coverage]));
  const items = (checklist.data?.items ?? []).filter(
    (i) => coverage.has(i.item_id) && !coverage.get(i.item_id) && i.status !== "satisfied",
  );
  const chosen = items.find((i) => i.item_id === itemId);
  const named = rows.filter((r) => r.name.trim());
  const busy = make.isPending || decide.isPending || map.isPending;
  const ready = name.trim().length > 0 && (!chosen?.blocking || reason.trim().length > 0) && !busy;

  const submit = async () => {
    setError(null);
    try {
      const made = await make.mutateAsync({
        name: name.trim(),
        description: about.trim() || null,
        fields: named.map((r) => ({ name: r.name.trim(), hint: r.hint.trim() || null })),
      });
      await decide.mutateAsync({
        id: item.id,
        body: { decision: "assign", value: made.id, reason: null },
      });
      toast.success(t("caseType.created", { type: made.name }));
      if (chosen) {
        const mapped = await map.mutateAsync({
          typeId: made.id,
          item_id: chosen.item_id,
          reason: reason.trim() || null,
        });
        // Counts at once for an item that is not mandatory; waits for a checker for one that is.
        const status = mapped.mappings?.find((m) => m.item_id === chosen.item_id)?.status;
        if (status) toast.success(t(`caseType.mapping.${status}`, { item: chosen.name }));
      }
      onClose();
    } catch (e) {
      setError(refusal(e) ?? t("caseType.failed"));
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        className="max-h-[90vh] max-w-lg overflow-y-auto"
        data-testid="new-type-dialog"
      >
        <DialogHeader>
          <DialogTitle>{t("caseType.title")}</DialogTitle>
          <DialogDescription>{t("caseType.description")}</DialogDescription>
        </DialogHeader>

        <label className="block">
          <span className="field-label">{t("caseType.name")}</span>
          <input
            className={inputClass}
            value={name}
            maxLength={80}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("caseType.namePlaceholder")}
            data-testid="new-type-name"
          />
        </label>
        <label className="block">
          <span className="field-label">{t("caseType.about")}</span>
          <input
            className={inputClass}
            value={about}
            onChange={(e) => setAbout(e.target.value)}
            placeholder={t("caseType.aboutPlaceholder")}
            data-testid="new-type-about"
          />
        </label>

        <fieldset className="space-y-2">
          <legend className="field-label">{t("caseType.fields")}</legend>
          {rows.length === 0 && (
            <p className="text-[12px] text-muted-foreground" data-testid="new-type-fields-none">
              {t("caseType.fieldsNone")}
            </p>
          )}
          {rows.map((r) => (
            <div key={r.key} className="flex items-start gap-2">
              <input
                className={inputClass}
                value={r.name}
                aria-label={t("caseType.fieldName")}
                placeholder={t("caseType.fieldName")}
                onChange={(e) =>
                  setRows((all) =>
                    all.map((x) => (x.key === r.key ? { ...x, name: e.target.value } : x)),
                  )
                }
                data-testid="new-type-field"
              />
              <input
                className={inputClass}
                value={r.hint}
                aria-label={t("caseType.fieldHint")}
                placeholder={t("caseType.fieldHintPlaceholder")}
                onChange={(e) =>
                  setRows((all) =>
                    all.map((x) => (x.key === r.key ? { ...x, hint: e.target.value } : x)),
                  )
                }
                data-testid="new-type-hint"
              />
              <button
                type="button"
                onClick={() => setRows((all) => all.filter((x) => x.key !== r.key))}
                aria-label={t("caseType.removeField", { name: r.name || t("caseType.fieldName") })}
                className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded border border-border text-muted-foreground hover:bg-muted"
              >
                <X className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => {
              setRows((all) => [...all, { key: next, name: "", hint: "" }]);
              setNext((n) => n + 1);
            }}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] font-medium text-primary hover:bg-muted"
            data-testid="new-type-add-field"
          >
            <Plus className="h-3 w-3" aria-hidden /> {t("caseType.addField")}
          </button>
        </fieldset>

        {items.length > 0 && (
          <label className="block">
            <span className="field-label">{t("caseType.countsToward")}</span>
            <select
              className={inputClass}
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              data-testid="new-type-counts"
            >
              <option value="">{t("caseType.countsNone")}</option>
              {items.map((i) => (
                <option key={i.item_id} value={i.item_id}>
                  {i.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {chosen?.blocking && (
          <>
            <p className="text-[12px] text-muted-foreground">
              {t("caseType.countsMandatory", { name: chosen.name })}
            </p>
            <label className="block">
              <span className="field-label">{t("caseType.reason")}</span>
              <textarea
                className={`${inputClass} h-16 py-1.5`}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                data-testid="new-type-reason"
              />
            </label>
          </>
        )}

        {error && (
          <p role="alert" className="text-[12px] text-critical-text" data-testid="new-type-error">
            {error}
          </p>
        )}

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
            onClick={() => void submit()}
            data-testid="new-type-create"
            className="h-9 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
          >
            {busy ? t("caseType.creating") : t("caseType.create")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
