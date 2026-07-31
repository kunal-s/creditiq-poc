import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CircleAlert,
  Download,
  FileText,
  PenLine,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { ConfidenceChip, Panel, SourceChip } from "@/components/identity/chips";
import { getAppraisal, CURRENT_USER } from "@/data/seed";
import {
  BS_ITEMS,
  DISCREPANCY_BANNER,
  PERIODS,
  PERIOD_META,
  PL_ITEMS,
  RATIOS,
  RATIO_LABEL,
  RATIO_TONE,
  SOURCE_DOCS,
  TREND_NOTES,
  fmt,
  type Cell,
  type FY,
  type LineItem,
  type Ratio,
} from "@/data/spread";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/spread")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Financial spread — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "A three-year normalised spread and the CCB policy ratios, with every figure traceable to the audited statement, GST return, bureau report or bank statement it came from.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: SpreadWorkspace,
});

type Inspect =
  | { kind: "cell"; itemKey: string; fy: FY }
  | { kind: "ratio"; key: string }
  | { kind: "source"; sourceId: string }
  | null;

type Amendment = { key: string; item: string; fy: FY; from: number; to: number; reason: string; at: string };

const ALL_ITEMS = [...PL_ITEMS, ...BS_ITEMS];

function SpreadWorkspace() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const [focus, setFocus] = useState<FY>("FY2025");
  const [inspect, setInspect] = useState<Inspect>({ kind: "cell", itemKey: "turnover", fy: "FY2025" });
  const [amendments, setAmendments] = useState<Amendment[]>([]);
  const [editing, setEditing] = useState<{ itemKey: string; fy: FY } | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  const amendedValue = (itemKey: string, fy: FY, base: number) => {
    const hit = [...amendments].reverse().find((x) => x.key === `${itemKey}:${fy}`);
    return hit ? hit.to : base;
  };
  const isAmended = (itemKey: string, fy: FY) => amendments.some((x) => x.key === `${itemKey}:${fy}`);
  const clConfirmed = amendments.some((x) => x.key === "cl:FY2025");

  const lowConfidenceOpen = useMemo(
    () => ALL_ITEMS.filter((i) => PERIODS.some((p) => i.cells[p].confidence === "low")).length - (clConfirmed ? 1 : 0),
    [clConfirmed],
  );

  const exportSpread = () => {
    const header = ["Block", "Line item", ...PERIODS, "Source (FY2025)"].join(",");
    const lines = [
      ...PL_ITEMS.map((i) => ["Profit and loss", i.label, ...PERIODS.map((p) => amendedValue(i.key, p, i.cells[p].value).toFixed(2)), SOURCE_DOCS[i.cells.FY2025.sourceId]!.doc]),
      ...BS_ITEMS.map((i) => ["Balance sheet", i.label, ...PERIODS.map((p) => amendedValue(i.key, p, i.cells[p].value).toFixed(2)), SOURCE_DOCS[i.cells.FY2025.sourceId]!.doc]),
      ...RATIOS.map((r) => ["Ratios", r.label, ...PERIODS.map((p) => fmt(r.values[p], r.unit)), r.formula]),
    ].map((cells) => cells.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","));
    const csv = [`"CreditIQ spread — ${a.borrower} — appraisal ${a.id}"`, header, ...lines].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `CreditIQ_Spread_${a.id}_${a.borrower.replace(/\s+/g, "_")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    toast("Spread exported", { description: `${ALL_ITEMS.length} line items and ${RATIOS.length} ratios, FY2023 to FY2025, with source attribution.` });
  };

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Spread`}
        title="Financial spread"
        purpose="Three audited years normalised into the bank's own format, with the CCB policy ratios computed on top. Every figure carries the document, page and line it was lifted from."
        actions={
          <>
            <Link
              to="/appraisals/$id/data"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Data console
            </Link>
            <button
              type="button"
              onClick={exportSpread}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <Download className="h-3.5 w-3.5" /> Export spread
            </button>
            <Link
              to="/appraisals/$id/cross-verification"
              params={{ id: a.id }}
              onClick={() => {
                setConfirmed(true);
                toast("Spread confirmed", {
                  description: `FY2023–FY2025 spread locked by ${CURRENT_USER.name}. ${amendments.length} analyst amendment${amendments.length === 1 ? "" : "s"} recorded to the audit trail.`,
                });
              }}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              Confirm spread and continue <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-4">
          {/* Period selector */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-border bg-surface px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="field-label">Period</span>
              <div className="flex rounded border border-border">
                {PERIODS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setFocus(p)}
                    className={cn(
                      "h-7 border-r border-border px-3 text-[12.5px] font-medium last:border-r-0",
                      focus === p ? "bg-primary text-primary-foreground" : "bg-surface text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-[11.5px] text-muted-foreground">
              {PERIOD_META[focus].ended} · {PERIOD_META[focus].status} · {PERIOD_META[focus].auditor}
            </p>
          </div>

          {/* Discrepancy banner */}
          <div className="rounded border border-flag/35 bg-flag-soft px-4 py-3">
            <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-flag-foreground">
              <CircleAlert className="h-3.5 w-3.5" /> {DISCREPANCY_BANNER.title}
            </p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-flag-foreground/90">{DISCREPANCY_BANNER.detail}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {DISCREPANCY_BANNER.refs.map((r) => (
                <button
                  key={r.sourceId}
                  type="button"
                  onClick={() => setInspect({ kind: "source", sourceId: r.sourceId })}
                  className="rounded border border-flag/35 bg-surface px-2 py-0.5 text-[11.5px] font-medium text-flag-foreground hover:bg-muted"
                >
                  {r.label}
                </button>
              ))}
              <Link
                to="/appraisals/$id/cross-verification"
                params={{ id: a.id }}
                className="text-[11.5px] font-medium text-primary hover:underline"
              >
                Take this to cross-verification →
              </Link>
            </div>
          </div>

          <SpreadBlock
            id="spread-base"
            title="Profit and loss"
            subtitle="INR crore · as reported, normalised to the CCB spread format"
            items={PL_ITEMS}
            focus={focus}
            inspect={inspect}
            onInspect={setInspect}
            amendedValue={amendedValue}
            isAmended={isAmended}
            clConfirmed={clConfirmed}
          />

          <SpreadBlock
            id="bank-credits"
            title="Balance sheet"
            subtitle="INR crore · as at 31 March of each year"
            items={BS_ITEMS}
            focus={focus}
            inspect={inspect}
            onInspect={setInspect}
            amendedValue={amendedValue}
            isAmended={isAmended}
            clConfirmed={clConfirmed}
          />

          {/* Ratios */}
          <Panel
            title="Ratios against CCB policy"
            subtitle={`Computed on ${focus} figures · thresholds from the credit policy manual, effective 01 April 2026`}
          >
            <div className="grid grid-cols-1 divide-y divide-border sm:grid-cols-2 sm:divide-y-0 md:grid-cols-4">
              {RATIOS.map((r) => {
                const active = inspect?.kind === "ratio" && inspect.key === r.key;
                const status = r.status[focus];
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => setInspect({ kind: "ratio", key: r.key })}
                    className={cn(
                      "border-b border-r border-border px-4 py-3 text-left transition-colors hover:bg-accent",
                      active && "bg-accent ring-1 ring-inset ring-primary/40",
                    )}
                  >
                    <p className="text-[11.5px] text-muted-foreground">{r.label}</p>
                    <p
                      className={cn(
                        "mt-0.5 text-[20px] font-semibold tabular-nums",
                        status === "pass" && "text-positive",
                        status === "marginal" && "text-flag-foreground",
                        status === "breach" && "text-destructive",
                      )}
                    >
                      {fmt(r.values[focus], r.unit)}
                      <span className="ml-0.5 text-[12px] font-medium">
                        {r.unit === "x" ? "x" : r.unit === "%" ? "%" : " days"}
                      </span>
                    </p>
                    <span
                      className={cn(
                        "mt-1 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
                        RATIO_TONE[status],
                      )}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      {RATIO_LABEL[status]}
                    </span>
                    <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
                      {r.policy?.text ?? "No hard policy threshold"}
                    </p>
                  </button>
                );
              })}
            </div>
          </Panel>

          {/* Trend strip */}
          <div className="grid gap-3 md:grid-cols-2">
            {TREND_NOTES.map((t) => (
              <div
                key={t.title}
                className={cn(
                  "rounded border px-4 py-3",
                  t.tone === "positive" ? "border-positive/30 bg-positive-soft" : "border-flag/35 bg-flag-soft",
                )}
              >
                <p
                  className={cn(
                    "flex items-center gap-1.5 text-[12.5px] font-semibold",
                    t.tone === "positive" ? "text-positive" : "text-flag-foreground",
                  )}
                >
                  <TrendingUp className="h-3.5 w-3.5" /> {t.title}
                </p>
                <p
                  className={cn(
                    "mt-1 text-[12.5px] leading-relaxed",
                    t.tone === "positive" ? "text-positive/90" : "text-flag-foreground/90",
                  )}
                >
                  {t.detail}
                </p>
              </div>
            ))}
          </div>

          {amendments.length > 0 && (
            <Panel title="Analyst amendments" subtitle="Recorded to the audit trail with the original extracted value retained">
              <ul className="divide-y divide-border">
                {amendments.map((am) => (
                  <li key={`${am.key}-${am.at}`} className="px-4 py-2.5 text-[12.5px]">
                    <p className="font-medium">
                      {am.item} · {am.fy} — {am.from.toFixed(2)} corrected to {am.to.toFixed(2)} cr
                    </p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {am.reason} · {CURRENT_USER.name} · {am.at} ·{" "}
                      <Link to="/audit" className="text-primary hover:underline">
                        View in audit trail
                      </Link>
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        {/* Right column */}
        <div className="space-y-3">
          <Panel title="Spread status" subtitle={`${a.borrower} · PAN ${a.pan}`}>
            <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
              <div className="px-4 py-3">
                <p className="text-[22px] font-semibold tabular-nums text-foreground">{ALL_ITEMS.length}</p>
                <p className="text-[11.5px] text-muted-foreground">Line items traced</p>
              </div>
              <div className="px-4 py-3">
                <p
                  className={cn(
                    "text-[22px] font-semibold tabular-nums",
                    lowConfidenceOpen > 0 ? "text-flag-foreground" : "text-positive",
                  )}
                >
                  {lowConfidenceOpen}
                </p>
                <p className="text-[11.5px] text-muted-foreground">Awaiting human check</p>
              </div>
            </div>
            <dl className="divide-y divide-border text-[12.5px]">
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Periods spread</dt>
                <dd>FY2023 · FY2024 · FY2025</dd>
              </div>
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Template</dt>
                <dd className="text-right">CAM v4.2 manufacturing spread</dd>
              </div>
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Status</dt>
                <dd className={confirmed ? "text-positive" : "text-flag-foreground"}>
                  {confirmed ? "Confirmed by analyst" : "Draft, not yet confirmed"}
                </dd>
              </div>
            </dl>
          </Panel>

          <InspectorPanel
            inspect={inspect}
            focus={focus}
            appraisalId={a.id}
            amendedValue={amendedValue}
            editing={editing}
            setEditing={setEditing}
            onAmend={(am) => {
              setAmendments((prev) => [...prev, am]);
              setEditing(null);
              toast("Figure corrected", {
                description: `${am.item} ${am.fy} set to ${am.to.toFixed(2)} cr. Original extraction of ${am.from.toFixed(2)} cr retained against the source page.`,
              });
            }}
            onInspect={setInspect}
          />

          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Inline AI action
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Test each ratio against its CCB threshold and report the ones inside a 15% band of breaching,
              with the line item driving the move.
            </p>
            <button
              type="button"
              onClick={() =>
                toast("Threshold proximity check", {
                  description:
                    "DSCR 1.61 sits 7% above the 1.50 floor and fell 0.11x in one year; current ratio 1.28 sits 7% above the 1.20 floor. Working-capital cycle at 87 days is already 12 days beyond the 75-day sector benchmark. TOL/TNW has 0.66x of headroom.",
                })
              }
              className="mt-3 flex h-8 w-full items-center justify-center gap-1.5 rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              Which ratios are close to breaching
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SpreadBlock({
  id,
  title,
  subtitle,
  items,
  focus,
  inspect,
  onInspect,
  amendedValue,
  isAmended,
  clConfirmed,
}: {
  id: string;
  title: string;
  subtitle: string;
  items: LineItem[];
  focus: FY;
  inspect: Inspect;
  onInspect: (i: Inspect) => void;
  amendedValue: (k: string, fy: FY, base: number) => number;
  isAmended: (k: string, fy: FY) => boolean;
  clConfirmed: boolean;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <Panel title={title} subtitle={subtitle}>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-border text-[11.5px] uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">Line item</th>
              {PERIODS.map((p) => (
                <th
                  key={p}
                  className={cn("px-4 py-2 text-right font-medium", focus === p && "bg-accent text-foreground")}
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => (
              <tr key={item.key} className="hover:bg-surface-muted/60">
                <td className="px-4 py-2">
                  <span className={cn("text-foreground", item.emphasis && "font-semibold")}>{item.label}</span>
                </td>
                {PERIODS.map((p) => {
                  const cell: Cell = item.cells[p];
                  const low = cell.confidence === "low" && !(item.key === "cl" && clConfirmed);
                  const active = inspect?.kind === "cell" && inspect.itemKey === item.key && inspect.fy === p;
                  const value = amendedValue(item.key, p, cell.value);
                  return (
                    <td key={p} className={cn("px-2 py-1.5 text-right", focus === p && "bg-accent/40")}>
                      <button
                        type="button"
                        onClick={() => onInspect({ kind: "cell", itemKey: item.key, fy: p })}
                        title={`${item.label} ${p} — trace to ${SOURCE_DOCS[cell.sourceId]!.doc}`}
                        className={cn(
                          "group inline-flex items-center gap-1.5 rounded px-2 py-1 tabular-nums hover:bg-accent",
                          item.emphasis && "font-semibold",
                          active && "bg-accent ring-1 ring-inset ring-primary/50",
                          low && "border border-destructive/40 bg-destructive/5",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            low ? "bg-destructive" : isAmended(item.key, p) ? "bg-flag" : "bg-primary/50",
                          )}
                          aria-hidden
                        />
                        {value.toFixed(2)}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {items.some((i) => i.key === "cl") && !clConfirmed && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border bg-destructive/5 px-4 py-2.5 text-[12px] text-destructive">
            <CircleAlert className="h-3.5 w-3.5 shrink-0" />
            <span className="min-w-0 flex-1">
              Current liabilities FY2025 (32.70 cr) was extracted with low confidence — please confirm against page 12
              of the audited statement before the spread is locked.
            </span>
            <button
              type="button"
              onClick={() => onInspect({ kind: "cell", itemKey: "cl", fy: "FY2025" })}
              className="h-7 rounded border border-destructive/30 bg-surface px-2.5 text-[11.5px] font-medium text-destructive hover:bg-muted"
            >
              Open for check
            </button>
          </div>
        )}
        <p className="border-t border-border px-4 py-2 text-[11.5px] text-muted-foreground">
          Every figure is clickable — the marker opens the exact page and line it was lifted from.
        </p>
      </Panel>
    </section>
  );
}

function InspectorPanel({
  inspect,
  focus,
  appraisalId,
  amendedValue,
  editing,
  setEditing,
  onAmend,
  onInspect,
}: {
  inspect: Inspect;
  focus: FY;
  appraisalId: string;
  amendedValue: (k: string, fy: FY, base: number) => number;
  editing: { itemKey: string; fy: FY } | null;
  setEditing: (e: { itemKey: string; fy: FY } | null) => void;
  onAmend: (a: Amendment) => void;
  onInspect: (i: Inspect) => void;
}) {
  if (!inspect) {
    return (
      <Panel title="Source panel" subtitle="Click any figure or ratio">
        <p className="px-4 py-4 text-[12.5px] text-muted-foreground">
          Select a figure to see the document, page and line it came from, or a ratio to see how it was computed.
        </p>
      </Panel>
    );
  }

  if (inspect.kind === "ratio") {
    const ratio = RATIOS.find((r) => r.key === inspect.key) as Ratio;
    const der = ratio.derivation[0]!;
    return (
      <Panel title="How this was computed" subtitle={`${ratio.label} · ${der.fy}`}>
        <div className="space-y-3 px-4 py-3 text-[12.5px]">
          <p className="text-muted-foreground">{ratio.formula}</p>
          <ul className="divide-y divide-border rounded border border-border">
            {der.lines.map((l) => (
              <li key={l.label} className="flex items-center justify-between gap-3 px-3 py-2">
                <button
                  type="button"
                  onClick={() =>
                    l.itemKey
                      ? onInspect({ kind: "cell", itemKey: l.itemKey, fy: der.fy })
                      : onInspect({ kind: "source", sourceId: l.sourceId })
                  }
                  className="min-w-0 flex-1 text-left text-primary hover:underline"
                >
                  {l.label}
                </button>
                <span className="tabular-nums">{l.value}</span>
              </li>
            ))}
          </ul>
          <p className="rounded border border-border bg-surface-muted px-3 py-2 font-medium tabular-nums">{der.math}</p>
          {ratio.policy && (
            <p className="text-muted-foreground">
              {ratio.policy.text} ·{" "}
              <span className={cn(RATIO_TONE[ratio.status[focus]], "rounded border px-1.5 py-0.5 text-[11px]")}>
                {RATIO_LABEL[ratio.status[focus]]} at {focus}
              </span>
            </p>
          )}
          <p className="leading-relaxed text-foreground/90">{ratio.comment}</p>
          <Link to="/admin/policy" className="inline-block text-[12px] font-medium text-primary hover:underline">
            Open the policy threshold in admin →
          </Link>
        </div>
      </Panel>
    );
  }

  const sourceId = inspect.kind === "source" ? inspect.sourceId : ALL_ITEMS.find((i) => i.key === inspect.itemKey)!.cells[inspect.fy].sourceId;
  const src = SOURCE_DOCS[sourceId]!;
  const item = inspect.kind === "cell" ? ALL_ITEMS.find((i) => i.key === inspect.itemKey)! : null;
  const cell = item && inspect.kind === "cell" ? item.cells[inspect.fy] : null;
  const shown = item && inspect.kind === "cell" ? amendedValue(item.key, inspect.fy, cell!.value) : null;

  return (
    <Panel
      title="Source panel"
      subtitle={item && inspect.kind === "cell" ? `${item.label} · ${inspect.fy}` : "Traced document"}
    >
      <div className="space-y-3 px-4 py-3 text-[12.5px]">
        {item && inspect.kind === "cell" && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[22px] font-semibold tabular-nums">{shown!.toFixed(2)}</span>
            <span className="text-[11.5px] text-muted-foreground">INR crore</span>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          <SourceChip source={src.provenance} />
          {cell && <ConfidenceChip level={cell.confidence} />}
        </div>
        <div className="overflow-hidden rounded border border-border bg-surface-muted p-3">
          <p className="flex items-start gap-1.5 text-[12.5px] font-medium text-foreground">
            <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <span className="min-w-0 break-all">{src.doc}</span>
          </p>
          <p className="mt-1 text-[11.5px] text-muted-foreground">{src.locator}</p>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed text-muted-foreground">
            {src.excerpt.join("\n")}
          </pre>
          <p className="mt-2 text-[11px] text-muted-foreground">Ingested {src.ingested}</p>
        </div>
        {item && <p className="text-[11.5px] leading-relaxed text-muted-foreground">{item.definition}</p>}
        {cell?.note && (
          <p className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-[12px] leading-relaxed text-destructive">
            {cell.note}
          </p>
        )}

        {item && inspect.kind === "cell" && editing?.itemKey === item.key && editing.fy === inspect.fy ? (
          <AmendForm
            item={item}
            fy={inspect.fy}
            current={shown!}
            onCancel={() => setEditing(null)}
            onSubmit={(to, reason) =>
              onAmend({
                key: `${item.key}:${inspect.fy}`,
                item: item.label,
                fy: inspect.fy,
                from: shown!,
                to,
                reason,
                at: "31 July 2026, 07:41",
              })
            }
          />
        ) : (
          item &&
          inspect.kind === "cell" && (
            <button
              type="button"
              onClick={() => setEditing({ itemKey: item.key, fy: inspect.fy })}
              className="flex h-8 w-full items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <PenLine className="h-3.5 w-3.5" /> Correct this figure
            </button>
          )
        )}

        <Link
          to="/appraisals/$id/data"
          params={{ id: appraisalId }}
          hash={src.acqKey}
          className="inline-block text-[12px] font-medium text-primary hover:underline"
        >
          Open this source in the data console →
        </Link>
      </div>
    </Panel>
  );
}

function AmendForm({
  item,
  fy,
  current,
  onCancel,
  onSubmit,
}: {
  item: LineItem;
  fy: FY;
  current: number;
  onCancel: () => void;
  onSubmit: (to: number, reason: string) => void;
}) {
  const [value, setValue] = useState(current.toFixed(2));
  const [reason, setReason] = useState(
    item.key === "cl" ? "Confirmed against schedule 11 of the FY2025 audited statement" : "",
  );
  const parsed = Number(value);
  const valid = Number.isFinite(parsed) && parsed > 0 && reason.trim().length > 3;

  return (
    <form
      className="space-y-2 rounded border border-border p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSubmit(parsed, reason.trim());
      }}
    >
      <p className="field-label">
        Correct {item.label} · {fy}
      </p>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        inputMode="decimal"
        aria-label="Corrected value in INR crore"
        className="h-8 w-full rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <textarea
        rows={2}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for the change — recorded to the audit trail"
        aria-label="Reason for the change"
        className="w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!valid}
          className="h-8 flex-1 rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          Record correction
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-8 rounded border border-border px-3 text-[12.5px] font-medium hover:bg-muted"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
