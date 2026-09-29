import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, Info } from "lucide-react";
import type { ChecklistItemState, LogicalDocument } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { ChecklistStatusChip } from "@/components/documents/chips";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useCase, useLabels } from "@/domain/cases";
import { bySection, countItems, useChecklist, useQueryList, useTaxonomy } from "@/domain/checklist";
import { pageRange, useCaseDocuments, useDocumentTypes } from "@/domain/documents";

export const Route = createFileRoute("/docready/$caseId/checklist")({
  head: () => ({
    meta: [{ title: `${t("page.checklist.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ChecklistTab,
});

function ChecklistTab() {
  const { caseId } = Route.useParams();
  const checklist = useChecklist(caseId);
  return (
    <div className="px-4 py-5 sm:px-6">
      <QueryView
        query={checklist}
        isEmpty={(r) => r.items.length === 0}
        empty={{
          title: t("checklist.emptyTitle"),
          description: t("checklist.emptyDescription"),
        }}
      >
        {(r) => (
          <Checklist
            caseId={caseId}
            items={r.items}
            provisional={r.provisional}
            score={r.score_pct}
            gate={r.gate_pct}
            blocking={r.blocking_open}
          />
        )}
      </QueryView>
    </div>
  );
}

function Checklist({
  caseId,
  items,
  provisional,
  score,
  gate,
  blocking,
}: {
  caseId: string;
  items: ChecklistItemState[];
  provisional: boolean;
  score: number;
  gate: number;
  blocking: number;
}) {
  const { data: c } = useCase(caseId);
  const labels = useLabels();
  const taxonomy = useTaxonomy();
  const queries = useQueryList(caseId);
  const documents = useCaseDocuments(caseId);
  const [open, setOpen] = useState<string | null>(null);
  const counts = countItems(items);
  const openQueries = queries.data?.filter((q) => !q.resolved).length;

  return (
    <div className="grid gap-4 [@media(min-width:1280px)]:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        {provisional && (
          <div
            className="flex items-start gap-2 rounded border border-flag/35 bg-flag-soft px-3 py-2.5 text-[12.5px] text-flag-foreground"
            data-testid="provisional"
          >
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {t("checklist.provisionalHelp")}
          </div>
        )}
        <Panel
          title={t("page.checklist.title")}
          subtitle={
            c
              ? t("checklist.derivedFrom", {
                  n: counts.total,
                  constitution: labels.constitution(c.constitution).toLowerCase(),
                  facilities: labels.facilities(c.facilities).toLowerCase(),
                })
              : undefined
          }
          action={
            <Link
              to="/docready/$caseId/collection"
              params={{ caseId }}
              className="rounded border border-border px-2.5 py-1 text-[12px] font-medium hover:bg-muted"
            >
              {t("checklist.queryListLink", { n: openQueries ?? "…" })}
            </Link>
          }
          testId="checklist"
        >
          <div className="divide-y divide-border">
            {bySection(items, taxonomy.data?.sections).map(({ section, items: sectionItems }) => (
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
                      expanded={open === item.item_id}
                      onToggle={() => setOpen(open === item.item_id ? null : item.item_id)}
                    />
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="min-w-0 space-y-3">
        <div
          className="rounded border border-border bg-surface p-4"
          data-testid="checklist-summary"
        >
          <p className="field-label">{t("docready.readiness")}</p>
          <p className="tabular mt-1 text-[26px] font-semibold leading-none text-foreground">
            {Math.round(score)}%
          </p>
          <p className="mt-1 text-[11.5px] text-muted-foreground">
            {t("checklist.gate", { gate: Math.round(gate) })}
          </p>
          <div className="mt-3 space-y-1.5 text-[12px]">
            {[
              {
                k: t("docStatus.satisfied"),
                v: t("checklist.xOfY", { x: counts.satisfied, y: counts.total }),
              },
              { k: t("docStatus.insufficient"), v: counts.insufficient },
              { k: t("docStatus.missing"), v: counts.missing },
              { k: t("docStatus.in_review"), v: counts.in_review },
              { k: t("docStatus.waived"), v: counts.waived },
              { k: t("checklist.blockingOpen"), v: blocking },
            ].map((row) => (
              <div key={row.k} className="flex justify-between">
                <span className="text-muted-foreground">{row.k}</span>
                <span className="tabular text-foreground">{row.v}</span>
              </div>
            ))}
          </div>
          <Link
            to="/docready/$caseId/readiness"
            params={{ caseId }}
            className="mt-3 block rounded border border-border px-3 py-1.5 text-center text-[12.5px] font-medium hover:bg-muted"
          >
            {t("checklist.openReadiness")}
          </Link>
        </div>
      </div>
    </div>
  );
}

function Item({
  caseId,
  item,
  documents,
  expanded,
  onToggle,
}: {
  caseId: string;
  item: ChecklistItemState;
  documents: LogicalDocument[];
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
          <div>
            <p className="field-label">{t("checklist.basis")}</p>
            <p className="mt-0.5 text-[12.5px] text-foreground">{item.basis}</p>
          </div>
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
                to="/docready/$caseId/validation"
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
