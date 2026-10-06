import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import type {
  ChecklistItemDef,
  ChecklistItemState,
  CoverageRule,
  LogicalDocument,
  Readiness,
} from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { ChecklistStatusChip } from "@/components/documents/chips";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useCase, useLabels } from "@/domain/cases";
import { bySection, isOpen, useTaxonomy } from "@/domain/checklist";
import { cn } from "@/lib/utils";
import { pageRange, useCaseDocuments, useDocumentTypes } from "@/domain/documents";

type ItemFilter = "all" | "open" | "blocking" | "satisfied";
const ITEM_FILTERS: ItemFilter[] = ["all", "open", "blocking", "satisfied"];

function passes(item: ChecklistItemState, filter: ItemFilter): boolean {
  if (filter === "open") return isOpen(item);
  if (filter === "blocking") return item.blocking && isOpen(item);
  if (filter === "satisfied") return item.status === "satisfied" || item.status === "waived";
  return true;
}

/** The checklist with each item's status (F-12, F-13), filterable. */
export function ChecklistPanel({ caseId, r }: { caseId: string; r: Readiness }) {
  const { data: c } = useCase(caseId);
  const labels = useLabels();
  const taxonomy = useTaxonomy();
  const documents = useCaseDocuments(caseId);
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState<ItemFilter>("all");
  const items = r.items;
  const shown = items.filter((i) => passes(i, filter));

  return (
    <Panel
      title={t("page.checklist.title")}
      subtitle={
        c
          ? t("checklist.derivedFrom", {
              n: items.length,
              constitution: labels.constitution(c.constitution).toLowerCase(),
              facilities: labels.facilities(c.facilities).toLowerCase(),
            })
          : undefined
      }
      testId="checklist"
    >
      <div
        className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2"
        data-testid="checklist-filters"
      >
        {ITEM_FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
            data-testid={`checklist-filter-${f}`}
            className={cn(
              "rounded border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
              filter === f
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-surface text-muted-foreground hover:bg-muted",
            )}
          >
            {t(`checklist.filter.${f}`, { n: items.filter((i) => passes(i, f)).length })}
          </button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
          {t("checklist.filterEmpty")}
        </p>
      ) : (
        <div className="divide-y divide-border">
          {bySection(shown, taxonomy.data?.sections).map(({ section, items: sectionItems }) => (
            <div key={section} data-testid="checklist-section">
              <p className="flex items-center justify-between gap-2 bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                <span>{section}</span>
                {taxonomy.data?.section_weight[section] !== undefined && (
                  <span className="tabular font-medium normal-case tracking-normal">
                    {t("checklist.weight", { n: taxonomy.data.section_weight[section] ?? 0 })}
                  </span>
                )}
              </p>
              <ul className="divide-y divide-border">
                {sectionItems.map((item) => (
                  <Item
                    key={item.item_id}
                    caseId={caseId}
                    item={item}
                    documents={documents.data ?? []}
                    def={taxonomy.data?.items.find((d) => d.id === item.item_id)}
                    expanded={open === item.item_id}
                    onToggle={() => setOpen(open === item.item_id ? null : item.item_id)}
                  />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/** What complete means for an item, in words (F-13.2), from configuration. */
function coverageText(c: CoverageRule): string {
  return t(`coverage.${c.kind}`, {
    count: c.count ?? 0,
    months: c.months ?? 0,
    statements: (c.statements ?? []).map((s) => s.replace(/_/g, " ")).join(", "),
  });
}

function Item({
  caseId,
  item,
  documents,
  def,
  expanded,
  onToggle,
}: {
  caseId: string;
  item: ChecklistItemState;
  documents: LogicalDocument[];
  def: ChecklistItemDef | undefined;
  expanded: boolean;
  onToggle: () => void;
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const linked = (item.document_ids ?? [])
    .map((id) => documents.find((d) => d.id === id))
    .filter((d): d is LogicalDocument => Boolean(d));

  return (
    <li data-testid="checklist-item" data-item={item.item_id} data-status={item.status}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-start gap-2.5 px-4 py-2.5 text-left hover:bg-surface-muted/60"
      >
        {expanded ? (
          <ChevronDown className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium text-foreground">{item.name}</span>
            {item.blocking && (
              <Chip tone="critical" upper>
                {t("checklist.blocking")}
              </Chip>
            )}
          </span>
          {item.deficiency && (
            <span
              className="mt-0.5 block text-[12px] text-flag-foreground"
              data-testid="deficiency"
            >
              {item.deficiency}
            </span>
          )}
          <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
            {item.basis}
            {linked.length > 0 && ` · ${t("checklist.documentsLinked", { n: linked.length })}`}
          </span>
        </span>
        <ChecklistStatusChip status={item.status} />
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border bg-surface-muted/40 px-4 py-3 sm:pl-11">
          <div>
            <p className="field-label">{t("checklist.why")}</p>
            <p className="mt-0.5 max-w-3xl text-[12.5px] leading-relaxed text-foreground">
              {item.why}
            </p>
          </div>
          {def?.request && item.status !== "satisfied" && item.status !== "waived" && (
            <div>
              <p className="field-label">{t("checklist.request")}</p>
              <p className="mt-0.5 text-[12.5px] text-foreground" data-testid="request">
                {def.request}
              </p>
            </div>
          )}
          {def?.coverage && (
            <Details testId="coverage-details">
              <div>
                <p className="field-label">{t("checklist.coverage")}</p>
                <p className="mt-0.5 text-[12.5px] text-foreground" data-testid="coverage">
                  {coverageText(def.coverage)}
                </p>
              </div>
            </Details>
          )}
          {item.deficiency && (
            <p className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] leading-relaxed text-destructive">
              {t(`docStatus.${item.status}`)} — {item.deficiency}
            </p>
          )}
          {linked.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {linked.map((doc) => (
                <button
                  key={doc.id}
                  type="button"
                  onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
                  className="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-2.5 py-1 text-[12px] font-medium text-primary hover:bg-muted"
                  data-testid="linked-document"
                >
                  <FileText className="h-3.5 w-3.5" />
                  {doc.classification?.types.map(types.name).join(" + ") ||
                    t("document.unclassified")}{" "}
                  · {pageRange(doc)}
                </button>
              ))}
              <Link
                to="/appraisals/$caseId/documents"
                params={{ caseId }}
                className="rounded border border-border px-2.5 py-1 text-[12px] font-medium text-primary hover:bg-muted"
              >
                {t("checklist.seeChecks")}
              </Link>
            </div>
          )}
        </div>
      )}
    </li>
  );
}
