import { useState, type ComponentType } from "react";
import { ChevronRight, Eye } from "lucide-react";
import type { CaseFacts, Evidence, FactValue, FindingArea, FindingSide } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { useDocumentTypes } from "@/domain/documents";
import { useFacts } from "@/domain/findings";
import { cn } from "@/lib/utils";
import { subsectionTitle } from "./xv/styles";

// The aligned facts behind the cross-checks (F-18), each with the pages it came from. Each area
// of the cross-verification board (src/components/case/xv/Board.tsx) shows its own, closed until
// asked for: identity the identifiers and the people, turnover the turnover by year, bank
// accounts the accounts and the business credits, existing obligations the instalments and
// facilities.

type FactsPanel = ComponentType<{ facts: CaseFacts; caseId: string }>;

const AREA_PANELS: Partial<Record<FindingArea, FactsPanel[]>> = {
  identity: [IdentityPanel, PeoplePanel],
  turnover: [TurnoverPanel],
  accounts: [AccountsPanel, CreditsPanel],
  obligations: [ObligationsPanel],
};

/** The facts an area's checks compared, closed until asked for; they load on opening. An area
 * with no facts on this screen shows nothing. */
export function AreaFactsSection({ caseId, area }: { caseId: string; area: FindingArea }) {
  const [open, setOpen] = useState(false);
  if ((AREA_PANELS[area]?.length ?? 0) === 0) return null;
  return (
    <details
      className="group min-w-0 rounded border border-border bg-surface"
      onToggle={(e) => setOpen(e.currentTarget.open)}
      data-testid="xv-facts"
    >
      <summary className="flex cursor-pointer select-none list-none flex-wrap items-baseline gap-x-3 gap-y-0.5 px-4 py-2.5 [&::-webkit-details-marker]:hidden">
        <span className={`flex items-center gap-1.5 ${subsectionTitle}`}>
          <ChevronRight
            className="h-4 w-4 shrink-0 self-center text-muted-foreground transition-transform group-open:rotate-90"
            aria-hidden
          />
          {t("crossVerification.facts.title")}
        </span>
        <span className="text-[11.5px] text-muted-foreground">{t("facts.purpose")}</span>
      </summary>
      {open && (
        <div className="border-t border-border p-4">
          <AreaFacts caseId={caseId} area={area} />
        </div>
      )}
    </details>
  );
}

function value(v: FindingSide["value"] | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "number" ? formatInr(v) : String(v);
}

function EvidenceLinks({ caseId, evidence }: { caseId: string; evidence: Evidence[] }) {
  const viewer = useDocViewer();
  if (evidence.length === 0) return null;
  const shown = evidence.slice(0, 3);
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((e, i) => (
        <button
          key={`${e.document_id}-${e.page}-${i}`}
          type="button"
          onClick={() =>
            viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
          }
          className="inline-flex items-center gap-0.5 rounded border border-border px-1.5 py-0.5 text-[11px] font-medium text-primary hover:bg-muted"
          data-testid="finding-evidence"
        >
          <Eye className="h-3 w-3" /> p{e.page}
        </button>
      ))}
      {evidence.length > shown.length && (
        <span className="text-[11px] text-muted-foreground">
          {t("crossCheck.morePages", { n: evidence.length - shown.length })}
        </span>
      )}
    </span>
  );
}

/** The facts one area's checks compared; they load when first shown. */
function AreaFacts({ caseId, area }: { caseId: string; area: FindingArea }) {
  const facts = useFacts(caseId);
  const panels = AREA_PANELS[area] ?? [];
  return (
    <QueryView query={facts} compact>
      {(f) => (
        // Side by side only where the board is wide: the people table has a column per source.
        <div className={cn("grid gap-4", panels.length > 1 && "2xl:grid-cols-2")}>
          {panels.map((Facts, i) => (
            <Facts key={i} facts={f} caseId={caseId} />
          ))}
        </div>
      )}
    </QueryView>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="px-4 py-4 text-[12.5px] text-muted-foreground">{text}</p>;
}

const IDENTIFIERS = ["entity_pan", "gstin", "cin", "legal_name"] as const;

/** Each identifier with its distinct values and the documents stating each. */
function IdentityPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const rows = IDENTIFIERS.map((key) => {
    const values = (facts.identities[key] ?? []) as FactValue[];
    const groups = new Map<string, FactValue[]>();
    for (const v of values) {
      const k = key === "legal_name" ? String(v.value).toLowerCase() : String(v.value);
      groups.set(k, [...(groups.get(k) ?? []), v]);
    }
    return { key, groups: [...groups.values()] };
  }).filter((r) => r.groups.length > 0);
  return (
    <Panel title={t("facts.identity")} subtitle={t("facts.identityHelp")} testId="facts-identity">
      {rows.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <ul className="divide-y divide-border text-[12px]">
          {rows.map(({ key, groups }) => (
            <li key={key} className="flex gap-3 px-4 py-2">
              <span className="w-20 shrink-0 font-medium text-muted-foreground">
                {t(`facts.identifier.${key}`)}
              </span>
              <ul className="min-w-0 flex-1 space-y-1">
                {groups.map((g, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span
                      className={cn(
                        "tabular font-medium",
                        groups.length > 1 && key !== "legal_name"
                          ? "text-destructive"
                          : "text-foreground",
                      )}
                    >
                      {String(g[0]!.value)}
                    </span>
                    <span className="text-muted-foreground">
                      {[...new Set(g.map((v) => v.label))].join(" · ")}
                    </span>
                    <EvidenceLinks
                      caseId={caseId}
                      evidence={g.flatMap((v) => (v.evidence ?? []).slice(0, 1))}
                    />
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Each person against each source that names them. */
function PeoplePanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const sets = facts.persons;
  const people: {
    name: string;
    din: string | null | undefined;
    pan: string | null | undefined;
    evidence: Evidence[];
  }[] = [];
  const key = (n: string) => n.toLowerCase().replace(/[^a-z]/g, "");
  for (const s of sets)
    for (const e of s.entries ?? [])
      if (!people.some((p) => key(p.name) === key(e.name)))
        people.push({ name: e.name, din: e.din, pan: e.pan, evidence: e.evidence ?? [] });
      else {
        const p = people.find((q) => key(q.name) === key(e.name))!;
        p.din = p.din ?? e.din;
        p.pan = p.pan ?? e.pan;
      }
  return (
    <Panel title={t("facts.people")} subtitle={t("facts.peopleHelp")} testId="facts-people">
      {people.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] text-muted-foreground">
                <th className="px-4 py-1.5 font-medium">{t("facts.person")}</th>
                <th className="px-2 py-1.5 font-medium">{t("facts.din")}</th>
                <th className="px-2 py-1.5 font-medium">{t("facts.pan")}</th>
                {sets.map((s) => (
                  <th key={s.label} className="px-2 py-1.5 text-center font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.name} className="border-t border-border">
                  <td className="px-4 py-1.5 font-medium">
                    {p.name} <EvidenceLinks caseId={caseId} evidence={p.evidence.slice(0, 1)} />
                  </td>
                  <td className="tabular px-2 py-1.5">{p.din ?? "—"}</td>
                  <td className="tabular px-2 py-1.5">{p.pan ?? "—"}</td>
                  {sets.map((s) => {
                    const named = (s.entries ?? []).some((e) => key(e.name) === key(p.name));
                    return (
                      <td
                        key={s.label}
                        className={cn(
                          "px-2 py-1.5 text-center",
                          named ? "text-positive" : "text-destructive",
                        )}
                      >
                        {named ? "✓" : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function TurnoverPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel title={t("facts.turnover")} subtitle={t("facts.turnoverHelp")} testId="facts-turnover">
      {facts.turnover.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="divide-y divide-border">
          {facts.turnover.map((y) => (
            <div key={y.fy} className="px-4 py-2.5">
              <p className="text-[12.5px] font-semibold">{y.fy}</p>
              <ul className="mt-1 space-y-1 text-[12px]">
                {y.figures.map((fig) => (
                  <li key={fig.source} className="flex flex-wrap items-center gap-x-3">
                    <span className="min-w-[14rem] text-muted-foreground">{fig.label}</span>
                    <span className="tabular font-medium">{value(fig.value)}</span>
                    {fig.months_covered !== null && fig.months_covered !== undefined && (
                      <span
                        className={cn(
                          "text-[11px]",
                          fig.months_covered < 12
                            ? "text-flag-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        {t("facts.months", { n: fig.months_covered })}
                      </span>
                    )}
                    <EvidenceLinks caseId={caseId} evidence={fig.evidence ?? []} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function CreditsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel title={t("facts.credits")} subtitle={t("facts.creditsHelp")} testId="facts-credits">
      {facts.credits.length === 0 ? (
        <Empty text={t("facts.noTransactions")} />
      ) : (
        <div className="divide-y divide-border">
          {facts.credits.map((c) => (
            <div key={c.account} className="px-4 py-2.5 text-[12px]">
              <p className="text-[12.5px] font-semibold">{c.account}</p>
              <p className="tabular mt-0.5 text-muted-foreground">
                {t("facts.creditsLine", {
                  gross: formatInr(c.gross),
                  excluded: formatInr(c.excluded),
                  net: formatInr(c.net),
                })}
              </p>
              {c.exclusions.length > 0 && (
                <ul className="mt-1.5 space-y-0.5">
                  {c.exclusions.slice(0, 8).map((e, i) => (
                    <li
                      key={i}
                      className="flex flex-wrap items-center gap-x-2"
                      data-testid="exclusion"
                    >
                      <Chip tone="muted">{e.label}</Chip>
                      <span className="tabular">{formatInr(e.amount)}</span>
                      <span className="min-w-0 flex-1 truncate text-muted-foreground">
                        {e.date} · {e.narration}
                      </span>
                      <EvidenceLinks caseId={caseId} evidence={e.evidence ?? []} />
                    </li>
                  ))}
                  {c.exclusions.length > 8 && (
                    <li className="text-muted-foreground">
                      {t("crossCheck.morePages", { n: c.exclusions.length - 8 })}
                    </li>
                  )}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function ObligationsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel
      title={t("facts.obligations")}
      subtitle={t("facts.obligationsHelp")}
      testId="facts-obligations"
    >
      {facts.obligations.length === 0 && facts.facilities.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="divide-y divide-border text-[12px]">
          {facts.obligations.map((o) => (
            <div
              key={`${o.lender}-${o.account}`}
              className="flex flex-wrap items-center gap-x-3 px-4 py-2"
            >
              <span className="font-medium">{o.lender}</span>
              <span className="tabular">
                {t("facts.emiLine", { amount: formatInr(o.typical_amount), n: o.months.length })}
              </span>
              <span className="text-muted-foreground">{o.account}</span>
              <EvidenceLinks caseId={caseId} evidence={o.evidence ?? []} />
            </div>
          ))}
          {facts.facilities.map((f, i) => (
            <div key={`${f.label}-${i}`} className="flex flex-wrap items-center gap-x-3 px-4 py-2">
              <span className="font-medium">{f.lender}</span>
              <span className="text-muted-foreground">
                {[f.facility, f.amount ? formatInr(f.amount) : null].filter(Boolean).join(" · ")}
              </span>
              <Chip tone="muted">{f.label}</Chip>
              <EvidenceLinks caseId={caseId} evidence={f.evidence ?? []} />
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function AccountsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const types = useDocumentTypes();
  return (
    <Panel title={t("facts.accounts")} subtitle={t("facts.accountsHelp")} testId="facts-accounts">
      {facts.accounts.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <ul className="divide-y divide-border text-[12px]">
          {facts.accounts.map((a) => (
            <li key={a.label} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
              <span className="min-w-[10rem] font-medium">{a.label}</span>
              <Chip tone={a.declared ? "positive" : "flag"}>
                {a.declared ? t("facts.declared") : t("facts.notDeclared")}
              </Chip>
              <Chip tone={a.has_statement ? "positive" : "flag"}>
                {a.has_statement ? t("facts.statement") : t("facts.noStatement")}
              </Chip>
              <span className="min-w-0 flex-1 text-muted-foreground">
                {a.sources.map(types.name).join(", ")}
              </span>
              <EvidenceLinks caseId={caseId} evidence={a.evidence ?? []} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
