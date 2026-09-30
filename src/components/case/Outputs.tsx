import { Link } from "@tanstack/react-router";
import { FileText } from "lucide-react";
import type { CamText, Evidence, PdQuestion, Spread, SpreadCell, SpreadRow } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { useCam, usePdNote, useSpread } from "@/domain/findings";
import { cn } from "@/lib/utils";

// The Outputs tab's three views (FRD §6): the spread (F-22, interim layout),
// the draft CAM (F-23) and the PD question note (F-24). Every figure and
// statement opens the page it rests on.

function Citations({ caseId, evidence }: { caseId: string; evidence: Evidence[] }) {
  const viewer = useDocViewer();
  const unique = evidence.filter(
    (e, i) => evidence.findIndex((x) => x.document_id === e.document_id && x.page === e.page) === i,
  );
  if (unique.length === 0) return null;
  return (
    <span className="ml-1 inline-flex flex-wrap gap-0.5 align-baseline">
      {unique.slice(0, 4).map((e, i) => (
        <button
          key={`${e.document_id}-${e.page}-${i}`}
          type="button"
          onClick={() =>
            viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
          }
          className="inline-flex items-center gap-0.5 rounded border border-border px-1 text-[10.5px] font-medium text-primary hover:bg-muted"
          data-testid="citation"
        >
          <FileText className="h-2.5 w-2.5" />p{e.page}
        </button>
      ))}
    </span>
  );
}

// --- Spread ---

function spreadValue(value: number | null | undefined, unit: SpreadRow["unit"]): string {
  if (value === null || value === undefined) return "—";
  if (unit === "inr") return formatInr(value);
  if (unit === "x") return `${value.toFixed(2)}x`;
  if (unit === "%") return `${value.toFixed(1)}%`;
  return `${Math.round(value)} days`;
}

function SpreadValue({
  caseId,
  cell,
  unit,
}: {
  caseId: string;
  cell: SpreadCell;
  unit: SpreadRow["unit"];
}) {
  const viewer = useDocViewer();
  const e = cell.evidence?.[0];
  const text = spreadValue(cell.value, unit);
  if (!e || cell.value === null || cell.value === undefined) return <span>{text}</span>;
  return (
    <button
      type="button"
      onClick={() =>
        viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
      }
      className="tabular underline decoration-border decoration-dotted underline-offset-2 hover:text-primary"
      data-testid="spread-value"
    >
      {text}
    </button>
  );
}

const SECTIONS = ["profit_and_loss", "balance_sheet", "ratios"] as const;

function SpreadTable({ caseId, spread }: { caseId: string; spread: Spread }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-[12.5px]" data-testid="spread-table">
        <thead>
          <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
            <th className="px-4 py-2 font-medium">{t("outputs.spread.line")}</th>
            {spread.columns.map((c) => (
              <th key={c.key} className="px-3 py-2 text-right font-medium">
                {c.fy}
                <span className="block normal-case tracking-normal">
                  {t(`outputs.spread.basis.${c.basis}`)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        {SECTIONS.map((section) => {
          const rows = spread.rows.filter((r) => r.section === section);
          if (rows.length === 0) return null;
          return (
            <tbody key={section} className="divide-y divide-border border-b border-border">
              <tr>
                <td
                  colSpan={spread.columns.length + 1}
                  className="bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
                >
                  {t(`outputs.spread.section.${section}`)}
                </td>
              </tr>
              {rows.map((row) => (
                <tr key={row.key} data-testid="spread-row" data-row={row.key}>
                  <td className="px-4 py-1.5">
                    <span className={cn(row.kind !== "line" && "italic")}>{row.label}</span>
                    {row.formula && (
                      <span className="block text-[10.5px] text-muted-foreground">
                        {row.formula}
                      </span>
                    )}
                  </td>
                  {row.cells.map((cell, i) => (
                    <td key={i} className="tabular px-3 py-1.5 text-right">
                      <SpreadValue caseId={caseId} cell={cell} unit={row.unit} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          );
        })}
      </table>
    </div>
  );
}

export function SpreadView({ caseId }: { caseId: string }) {
  const spread = useSpread(caseId);
  return (
    <QueryView
      query={spread}
      isEmpty={(s) => s.columns.length === 0}
      empty={{
        title: t("outputs.spread.emptyTitle"),
        description: t("outputs.spread.emptyDescription"),
      }}
    >
      {(s) => {
        const wc = s.working_capital;
        return (
          <div className="space-y-4">
            {s.interim && (
              <p
                className="rounded border border-info/40 bg-info-soft px-3 py-2 text-[12px] text-info"
                data-testid="spread-interim"
              >
                {t("outputs.spread.interim")}
              </p>
            )}
            <Panel title={t("outputs.spread.title")} testId="spread">
              <SpreadTable caseId={caseId} spread={s} />
            </Panel>
            <Panel
              title={t("outputs.spread.wcTitle")}
              subtitle={wc.reason}
              testId="working-capital"
            >
              {wc.method === "not_applicable" ? null : wc.missing && wc.missing.length > 0 ? (
                <p className="px-4 py-3 text-[12.5px] text-flag-foreground">
                  {t("outputs.spread.wcMissing", { inputs: wc.missing.join(", ") })}
                </p>
              ) : (
                <div className="px-4 py-3 text-[12.5px]">
                  <table className="w-full">
                    <tbody className="divide-y divide-border">
                      {(wc.steps ?? []).map((step) => (
                        <tr key={step.label}>
                          <td className="py-1.5">{step.label}</td>
                          <td className="tabular py-1.5 text-right font-medium">
                            {step.value === null || step.value === undefined
                              ? "—"
                              : formatInr(step.value)}
                            <Citations caseId={caseId} evidence={step.evidence ?? []} />
                          </td>
                          <td className="py-1.5 pl-4 text-muted-foreground">{step.basis}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 font-medium" data-testid="wc-verdict">
                    {t("outputs.spread.wcVerdict", {
                      eligible:
                        wc.eligible === null || wc.eligible === undefined
                          ? "—"
                          : formatInr(wc.eligible),
                      requested: formatInr(wc.requested),
                    })}
                  </p>
                </div>
              )}
            </Panel>
          </div>
        );
      }}
    </QueryView>
  );
}

// --- CAM ---

function Statement({ caseId, text }: { caseId: string; text: CamText }) {
  return (
    <>
      {text.text}
      <Citations caseId={caseId} evidence={text.citations ?? []} />
    </>
  );
}

export function CamView({ caseId }: { caseId: string }) {
  const cam = useCam(caseId);
  return (
    <QueryView query={cam}>
      {(m) => (
        <article
          className="mx-auto max-w-4xl space-y-5 rounded border border-border bg-surface px-6 py-5"
          data-testid="cam"
        >
          <header className="border-b border-border pb-3">
            <p className="field-label">{t("outputs.cam.eyebrow")}</p>
            <h2 className="text-[18px] font-semibold">{t("outputs.cam.title")}</h2>
            {m.interim_template && (
              <p className="mt-1 text-[12px] text-muted-foreground">{t("outputs.cam.interim")}</p>
            )}
          </header>
          {m.sections.map((s, i) => (
            <section key={s.id} data-testid="cam-section" data-section={s.id}>
              <h3 className="text-[14px] font-semibold">
                {i + 1}. {s.title}
              </h3>
              {s.empty && <p className="mt-1 text-[12.5px] text-muted-foreground">{s.empty}</p>}
              <div className="mt-1 space-y-1.5 text-[13px] leading-relaxed">
                {(s.paragraphs ?? []).map((p, j) => (
                  <p key={j}>
                    <Statement caseId={caseId} text={p} />
                  </p>
                ))}
              </div>
              {s.table && (
                <table className="mt-2 w-full text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
                      {s.table.columns.map((c, j) => (
                        <th key={j} className={cn("py-1 font-medium", j > 0 && "text-right")}>
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {s.table.rows.map((row, j) => (
                      <tr key={j}>
                        {row.map((cell, k) => (
                          <td key={k} className={cn("tabular py-1", k > 0 && "text-right")}>
                            <Statement caseId={caseId} text={cell} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          ))}
          <section data-testid="cam-summary">
            <h3 className="text-[14px] font-semibold">
              {m.sections.length + 1}. {m.summary_title}
            </h3>
            {(["finding", "deviation", "query"] as const).map((kind) => {
              const items = m.summary.filter((i) => i.kind === kind);
              if (items.length === 0) return null;
              return (
                <div key={kind} className="mt-2">
                  <p className="text-[12px] font-semibold text-muted-foreground">
                    {t(`outputs.cam.summary.${kind}`, { n: items.length })}
                  </p>
                  <ol className="mt-1 list-decimal space-y-1 pl-5 text-[12.5px]">
                    {items.map((item) => (
                      <li key={item.ref}>
                        {item.severity && (
                          <Chip tone={item.severity === "serious" ? "critical" : "flag"}>
                            {t(`severity.${item.severity}`)}
                          </Chip>
                        )}{" "}
                        {item.text}
                        <Citations caseId={caseId} evidence={item.citations ?? []} />
                      </li>
                    ))}
                  </ol>
                </div>
              );
            })}
          </section>
          <section data-testid="cam-recommendation">
            <h3 className="text-[14px] font-semibold">
              {m.sections.length + 2}. {m.recommendation_title}
            </h3>
            <div className="mt-1 min-h-[4rem] rounded border border-dashed border-border px-3 py-2 text-[12.5px] text-muted-foreground">
              {m.recommendation || t("outputs.cam.recommendationEmpty")}
            </div>
          </section>
        </article>
      )}
    </QueryView>
  );
}

// --- PD note ---

/** Where a question's source is decided: a cross-check, else a policy norm. */
function sourceLink(caseId: string, q: PdQuestion): string {
  const base = `/appraisals/${encodeURIComponent(caseId)}`;
  return /^(ID|TO|BA|OB)-\d/.test(q.rule) ? `${base}/cross-verification` : `${base}/policy`;
}

export function PdNoteView({ caseId }: { caseId: string }) {
  const note = usePdNote(caseId);
  return (
    <QueryView
      query={note}
      isEmpty={(n) => n.questions.length === 0}
      empty={{ title: t("outputs.pd.emptyTitle"), description: t("outputs.pd.emptyDescription") }}
    >
      {(n) => (
        <Panel
          title={t("outputs.pd.title")}
          subtitle={t("outputs.pd.subtitle", { n: n.questions.length })}
          testId="pd-note"
        >
          <ol className="divide-y divide-border">
            {n.questions.map((q, i) => (
              <li
                key={q.id}
                className="flex gap-3 px-4 py-3"
                data-testid="pd-question"
                data-rule={q.rule}
              >
                <span className="tabular w-6 shrink-0 text-[12.5px] font-medium">{i + 1}.</span>
                <div className="min-w-0 flex-1 space-y-1">
                  <p className="text-[13px] leading-relaxed">{q.text}</p>
                  <p className="flex flex-wrap items-center gap-2 text-[11.5px] text-muted-foreground">
                    <Chip
                      tone={
                        q.severity === "serious"
                          ? "critical"
                          : q.severity === "moderate"
                            ? "flag"
                            : "muted"
                      }
                    >
                      {t(`severity.${q.severity}`)}
                    </Chip>
                    <span>{t(`outputs.pd.source.${q.source}`)}</span>
                    <Link
                      to={sourceLink(caseId, q)}
                      className="font-medium text-primary hover:underline"
                    >
                      {q.rule} · {q.title}
                    </Link>
                    <Citations caseId={caseId} evidence={q.evidence ?? []} />
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </QueryView>
  );
}
