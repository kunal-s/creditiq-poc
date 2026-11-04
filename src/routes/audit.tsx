import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Download, Lock } from "lucide-react";
import type { AuditEntry } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { Details } from "@/components/common/Details";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { actionLabel, formatWhen, useAudit } from "@/domain/admin";
import { stageLabel, useCases } from "@/domain/cases";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [{ title: `${t("page.audit.title")} — ${t("tenant.product.name")}` }],
  }),
  component: Audit,
});

const select =
  "h-8 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground outline-none focus:border-primary/60";

/** The entries shown, as a file the examiner can keep: one line each, oldest last as listed. */
function exportLedger(entries: AuditEntry[]) {
  const cell = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const lines = [
    ["seq", "at", "action", "actor", "appraisal", "detail"].join(","),
    ...entries.map((e) =>
      [
        String(e.seq),
        e.at,
        cell(actionLabel(e.action)),
        cell(e.actor_name),
        e.case_id ?? "",
        cell(JSON.stringify(e.detail)),
      ].join(","),
    ),
  ];
  const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "audit-ledger.csv";
  a.click();
  URL.revokeObjectURL(url);
}

/** The entries that record a person's decision on the appraisal. */
const DECISIONS = new Set([
  "review_decided",
  "comparison_adjudicated",
  "finding_escalated",
  "reference_confirmed",
]);

/** A card for each appraisal in the entries: its borrower, how many entries, how many by a
 * person, and the latest; a click shows only its entries. */
function AppraisalCards({
  entries,
  selected,
  onSelect,
}: {
  entries: AuditEntry[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const cases = useCases();
  const ids = [...new Set(entries.flatMap((e) => (e.case_id ? [e.case_id] : [])))].slice(0, 4);
  if (ids.length === 0) return null;
  return (
    <section className="grid gap-3 @min-[42rem]/main:grid-cols-2" data-testid="audit-cards">
      {ids.map((id) => {
        const mine = entries.filter((e) => e.case_id === id);
        const decisions = mine.filter((e) => DECISIONS.has(e.action)).length;
        const c = cases.data?.find((x) => x.id === id);
        const active = selected === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(active ? "" : id)}
            aria-pressed={active}
            className={cn(
              "rounded border bg-surface px-4 py-3 text-left transition-colors hover:border-primary/40",
              active ? "border-primary ring-1 ring-primary/30" : "border-border",
            )}
            data-testid="audit-card"
          >
            <span className="flex items-start justify-between gap-2">
              <span className="min-w-0 text-[13.5px] font-semibold text-foreground">
                {c?.borrower ?? id}
              </span>
              {c && (
                <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  {stageLabel(c.stage)}
                </span>
              )}
            </span>
            <span className="tabular mt-0.5 block text-[11px] text-muted-foreground">
              {id} · {formatWhen(mine[0]!.at)}
            </span>
            <span className="mt-2 block text-[12px] text-muted-foreground">
              {t("audit.cardCounts", { n: mine.length, decisions })}
            </span>
          </button>
        );
      })}
    </section>
  );
}

function Audit() {
  const session = useSession();
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [caseId, setCaseId] = useState("");
  const audit = useAudit({
    ...(actor ? { actor } : {}),
    ...(action ? { action } : {}),
    ...(caseId.trim() ? { caseId: caseId.trim() } : {}),
  });
  return (
    <div>
      <PageHeader
        eyebrow={t("page.audit.eyebrow")}
        title={t("page.audit.title")}
        purpose={t("page.audit.purpose")}
        actions={
          <>
            <span className="inline-flex items-center gap-1.5 rounded border border-border bg-muted/60 px-2.5 py-1.5 text-[12px] text-muted-foreground">
              <Lock className="h-3.5 w-3.5" aria-hidden />
              {t("audit.readOnly", {
                name: session?.user.name ?? "",
                role: session?.user.roleLabel ?? "",
              })}
            </span>
            <button
              type="button"
              disabled={!audit.data || audit.data.entries.length === 0}
              onClick={() => audit.data && exportLedger(audit.data.entries)}
              className="inline-flex items-center gap-1.5 rounded bg-primary px-3 py-1.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
              data-testid="audit-export"
            >
              <Download className="h-3.5 w-3.5" aria-hidden /> {t("audit.export")}
            </button>
          </>
        }
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        <QueryView query={audit}>
          {(page) => (
            <>
              {/* The appraisals the ledger speaks of, as the original's cards: one picks its entries. */}
              <AppraisalCards
                entries={page.entries}
                selected={caseId.trim()}
                onSelect={setCaseId}
              />
              <Panel
                title={t("audit.entries")}
                testId="audit"
                action={
                  // On a phone the three filters share the width: two to a row, the activity first.
                  <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
                    <select
                      className={`${select} max-sm:col-span-2`}
                      value={action}
                      onChange={(e) => setAction(e.target.value)}
                      aria-label={t("audit.filterAction")}
                    >
                      <option value="">{t("audit.allActions")}</option>
                      {page.actions.map((a) => (
                        <option key={a} value={a}>
                          {actionLabel(a)}
                        </option>
                      ))}
                    </select>
                    <select
                      className={select}
                      value={actor}
                      onChange={(e) => setActor(e.target.value)}
                      aria-label={t("audit.filterPerson")}
                    >
                      <option value="">{t("audit.allPeople")}</option>
                      {page.actors.map((a) => (
                        <option key={a} value={a}>
                          {page.entries.find((e) => e.actor === a)?.actor_name ?? a}
                        </option>
                      ))}
                    </select>
                    <input
                      className={`${select} min-w-0 sm:w-40`}
                      value={caseId}
                      onChange={(e) => setCaseId(e.target.value)}
                      placeholder={t("audit.caseId")}
                      aria-label={t("audit.caseId")}
                    />
                  </div>
                }
              >
                {page.entries.length === 0 ? (
                  <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
                    {t("audit.none")}
                  </p>
                ) : (
                  // A timeline, as the original design: when on the left, a mark on the line, then
                  // what was done, by whom and on which appraisal.
                  <ol className="px-4 py-3">
                    {page.entries.map((e, i) => (
                      <li
                        key={e.seq}
                        className="grid grid-cols-[5.5rem_1rem_minmax(0,1fr)] gap-x-2 sm:grid-cols-[7.5rem_1rem_minmax(0,1fr)]"
                        data-testid="audit-entry"
                      >
                        <span className="tabular pt-0.5 text-[11.5px] leading-snug text-muted-foreground">
                          {formatWhen(e.at)}
                        </span>
                        <span className="relative flex justify-center" aria-hidden>
                          <span className="mt-1.5 h-2 w-2 rounded-full bg-primary/70 ring-2 ring-surface" />
                          {i < page.entries.length - 1 && (
                            <span className="absolute bottom-0 top-3.5 w-px bg-border" />
                          )}
                        </span>
                        <div className="min-w-0 space-y-1 pb-4">
                          <p className="text-[13px] font-medium text-foreground">
                            {actionLabel(e.action)}
                          </p>
                          <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11.5px] text-muted-foreground">
                            <span>{e.actor_name}</span>
                            {e.case_id && (
                              <Link
                                to="/appraisals/$caseId"
                                params={{ caseId: e.case_id }}
                                className="rounded border border-border bg-muted/50 px-1.5 py-px text-[11px] text-primary hover:underline"
                              >
                                {e.case_id}
                              </Link>
                            )}
                          </p>
                          {Object.keys(e.detail).length > 0 && (
                            <Details>
                              <dl className="space-y-0.5 text-[12px]">
                                {Object.entries(e.detail).map(([k, v]) => (
                                  <div key={k} className="flex gap-2">
                                    <dt className="w-32 shrink-0 text-muted-foreground">
                                      {k.replace(/_/g, " ")}
                                    </dt>
                                    <dd className="min-w-0 break-words">
                                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                    </dd>
                                  </div>
                                ))}
                              </dl>
                            </Details>
                          )}
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </Panel>
            </>
          )}
        </QueryView>
      </div>
    </div>
  );
}
