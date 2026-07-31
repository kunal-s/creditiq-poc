import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { ArrowUpRight, Check, Minus, Plus, RotateCcw, Sparkles, Upload } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import {
  AVAILABLE_RATIOS,
  BAND_LABEL,
  BAND_TONE,
  BASE_GRID,
  BASE_RATIOS,
  BOOK,
  addRatio,
  classify,
  fmtRatio,
  publishPolicy,
  reclassified,
  removeRatio,
  resetPolicy,
  setGridBand,
  setThreshold,
  useAdminState,
  type PolicyRatio,
} from "@/data/admin";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/admin/policy")({
  head: () => {
    const title = "Ratio and policy configurator — CreditIQ";
    const description =
      "Define the ratios Continental Commercial Bank underwrites on, their acceptable, marginal and adverse thresholds, and the CCB-1 to CCB-8 rating grid — previewed live against a seeded borrower before publishing.";
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
  component: PolicyConfigurator,
});

const NW = BOOK[0]!;

function PolicyConfigurator() {
  const s = useAdminState();
  const [adding, setAdding] = useState(false);
  const [version, setVersion] = useState("v6.3");

  const dirty = useMemo(() => {
    const rSame =
      s.ratios.length === BASE_RATIOS.length &&
      s.ratios.every((r) => {
        const b = BASE_RATIOS.find((x) => x.key === r.key);
        return b && b.acceptable === r.acceptable && b.marginal === r.marginal;
      });
    const gSame = s.grid.every((g) => {
      const b = BASE_GRID.find((x) => x.grade === g.grade)!;
      return b.scoreFrom === g.scoreFrom && b.scoreTo === g.scoreTo && b.watch === g.watch;
    });
    return !(rSame && gSame);
  }, [s.ratios, s.grid]);

  const preview = s.ratios.map((r) => {
    const value = NW.values[r.key];
    const published = BASE_RATIOS.find((b) => b.key === r.key) ?? r;
    return {
      ratio: r,
      value,
      band: value === undefined ? null : classify(r, value),
      wasBand: value === undefined ? null : classify(published, value),
    };
  });

  const breaches = preview.filter((p) => p.band === "adverse").length;
  const marginals = preview.filter((p) => p.band === "marginal").length;
  const moved = preview.filter((p) => p.band && p.wasBand && p.band !== p.wasBand);

  const bookImpact = useMemo(() => {
    const rows: { borrower: (typeof BOOK)[number]; ratio: PolicyRatio; from: string; to: string }[] = [];
    for (const r of s.ratios) {
      const published = BASE_RATIOS.find((b) => b.key === r.key);
      if (!published) continue;
      for (const x of reclassified(published, r)) rows.push({ borrower: x.borrower, ratio: r, from: x.from, to: x.to });
    }
    return rows;
  }, [s.ratios]);

  const watchBand = s.grid.filter((g) => g.watch).map((g) => g.grade);

  return (
    <div>
      <PageHeader
        eyebrow="Admin · Credit policy"
        title="Ratio and policy configurator"
        purpose="The ratios Continental Commercial Bank underwrites on, the thresholds that classify them, and the CCB-1 to CCB-8 grid. Change a number here and every appraisal's spread and rating follows — no code, no release."
        actions={
          <>
            <span className="hidden items-center gap-1.5 rounded border border-border bg-surface-muted px-2 py-1.5 text-[11.5px] text-muted-foreground lg:inline-flex">
              Policy owner: David Klein · Administrator
            </span>
            {dirty && (
              <button
                onClick={() => {
                  resetPolicy();
                  toast("Draft discarded", { description: "Published policy v6.2 restored." });
                }}
                className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
              >
                <RotateCcw className="h-3.5 w-3.5" /> Discard draft
              </button>
            )}
            <button
              onClick={() => {
                publishPolicy(version);
                toast.success(`Ratio policy ${version} published`, {
                  description: `Applies to every appraisal from the next spread refresh. ${bookImpact.length} borrower classifications change.`,
                });
              }}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Upload className="h-3.5 w-3.5" /> Publish {version}
            </button>
          </>
        }
      />

      <div className="space-y-4 px-6 py-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded border border-border bg-surface px-4 py-3 text-[12px]">
          <div>
            <p className="field-label">Published policy</p>
            <p className="mt-0.5 text-foreground">v6.2 · recalibrated 18 April 2026 · Credit Risk Policy</p>
          </div>
          <div>
            <p className="field-label">Draft</p>
            <p className={cn("mt-0.5", dirty ? "text-flag-foreground" : "text-muted-foreground")}>
              {dirty ? `${moved.length + bookImpact.length} classification changes pending` : "No unpublished changes"}
            </p>
          </div>
          <div>
            <p className="field-label">Applies to</p>
            <p className="mt-0.5 text-foreground">142 live exposures · West Region</p>
          </div>
          <div>
            <p className="field-label">Watch band</p>
            <p className="mt-0.5 text-foreground">{watchBand.join(" and ") || "None set"}</p>
          </div>
          {s.policyPublished && (
            <div>
              <p className="field-label">Last published from here</p>
              <p className="mt-0.5 text-positive">
                {s.policyPublished.version} · {s.policyPublished.at} · {s.policyPublished.by}
              </p>
            </div>
          )}
          <label className="ml-auto flex items-center gap-2 text-[12px] text-muted-foreground">
            Version label
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="h-8 w-20 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground"
            />
          </label>
        </div>

        <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="space-y-4">
            {/* ratio set */}
            <Panel
              title="Underwritten ratio set"
              subtitle={`${s.ratios.length} ratios · acceptable, marginal and adverse bands`}
              action={
                <button
                  onClick={() => setAdding((v) => !v)}
                  className="flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] hover:bg-muted"
                >
                  <Plus className="h-3.5 w-3.5" /> Add a ratio
                </button>
              }
            >
              {adding && (
                <div className="border-b border-border bg-surface-muted/50 px-4 py-3">
                  <p className="field-label">Available but not underwritten today</p>
                  <div className="mt-2 grid gap-2 md:grid-cols-3">
                    {AVAILABLE_RATIOS.filter((a) => !s.ratios.some((r) => r.key === a.key)).map((a) => (
                      <button
                        key={a.key}
                        onClick={() => {
                          addRatio(a.key);
                          setAdding(false);
                          toast.success(`${a.label} added to the draft policy`, { description: a.note });
                        }}
                        className="rounded border border-border bg-surface p-2.5 text-left hover:bg-muted"
                      >
                        <p className="text-[12.5px] font-medium text-foreground">{a.label}</p>
                        <p className="mt-0.5 text-[11.5px] text-muted-foreground">{a.formula}</p>
                      </button>
                    ))}
                    {AVAILABLE_RATIOS.every((a) => s.ratios.some((r) => r.key === a.key)) && (
                      <p className="text-[12.5px] text-muted-foreground">Every available ratio is already in the set.</p>
                    )}
                  </div>
                </div>
              )}
              <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Ratio</th>
                    <th className="px-2 py-2 font-medium">Test</th>
                    <th className="px-2 py-2 font-medium">Acceptable</th>
                    <th className="px-2 py-2 font-medium">Marginal to</th>
                    <th className="px-2 py-2 font-medium">Adverse beyond</th>
                    <th className="px-2 py-2 font-medium">Northwind FY2025</th>
                    <th className="px-2 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.ratios.map((r) => {
                    const base = BASE_RATIOS.find((b) => b.key === r.key);
                    const changed = base && (base.acceptable !== r.acceptable || base.marginal !== r.marginal);
                    const v = NW.values[r.key];
                    const band = v === undefined ? null : classify(r, v);
                    return (
                      <tr key={r.key} className={cn("align-top", changed && "bg-flag-soft/40")}>
                        <td className="px-4 py-2.5">
                          <p className="font-medium text-foreground">{r.label}</p>
                          <p className="mt-0.5 text-[11.5px] text-muted-foreground">{r.formula}</p>
                          <p className="mt-0.5 text-[11.5px] text-muted-foreground">{r.applies}</p>
                          {r.hardFloor && (
                            <p className="mt-1 inline-block rounded border border-critical/25 bg-critical-soft px-1.5 py-0.5 text-[10.5px] text-critical">
                              {r.hardFloor}
                            </p>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-muted-foreground">{r.kind === "min" ? "Minimum" : "Maximum"}</td>
                        <td className="px-2 py-2.5">
                          <ThresholdInput value={r.acceptable} unit={r.unit} onChange={(n) => setThreshold(r.key, "acceptable", n)} />
                        </td>
                        <td className="px-2 py-2.5">
                          <ThresholdInput value={r.marginal} unit={r.unit} onChange={(n) => setThreshold(r.key, "marginal", n)} />
                        </td>
                        <td className="px-2 py-2.5 text-muted-foreground">
                          {r.kind === "min" ? "Below " : "Above "}
                          {fmtRatio(r.marginal, r.unit)}
                        </td>
                        <td className="px-2 py-2.5">
                          {v !== undefined && band ? (
                            <span className="flex flex-wrap items-center gap-1.5">
                              <span className="tabular-nums text-foreground">{fmtRatio(v, r.unit)}</span>
                              <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px]", BAND_TONE[band])}>{BAND_LABEL[band]}</span>
                            </span>
                          ) : (
                            <span className="text-muted-foreground">Not spread</span>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-right">
                          <button
                            onClick={() => {
                              removeRatio(r.key);
                              toast(`${r.label} removed from the draft policy`);
                            }}
                            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            aria-label={`Remove ${r.label}`}
                          >
                            <Minus className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </Panel>

            {/* grid */}
            <Panel title="Risk-rating grid" subtitle="CCB-1 to CCB-8, the score bands behind them, and which grades sit in the watch band.">
              <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Grade</th>
                    <th className="px-2 py-2 font-medium">Description</th>
                    <th className="px-2 py-2 font-medium">Band</th>
                    <th className="px-2 py-2 font-medium">Score from</th>
                    <th className="px-2 py-2 font-medium">to</th>
                    <th className="px-2 py-2 font-medium">Watch</th>
                    <th className="px-2 py-2 font-medium">Delegation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.grid.map((g) => {
                    const base = BASE_GRID.find((b) => b.grade === g.grade)!;
                    const changed = base.scoreFrom !== g.scoreFrom || base.scoreTo !== g.scoreTo || base.watch !== g.watch;
                    const holders = BOOK.filter((b) => b.score >= g.scoreFrom && b.score <= g.scoreTo);
                    return (
                      <tr key={g.grade} className={cn(changed && "bg-flag-soft/40", g.watch && "border-l-2 border-l-flag")}>
                        <td className="px-4 py-2 font-medium text-foreground">{g.grade}</td>
                        <td className="px-2 py-2 text-muted-foreground">{g.label}</td>
                        <td className="px-2 py-2 text-muted-foreground">{g.band}</td>
                        <td className="px-2 py-2">
                          <ThresholdInput value={g.scoreFrom} unit="days" onChange={(n) => setGridBand(g.grade, { scoreFrom: n })} plain />
                        </td>
                        <td className="px-2 py-2">
                          <ThresholdInput value={g.scoreTo} unit="days" onChange={(n) => setGridBand(g.grade, { scoreTo: n })} plain />
                        </td>
                        <td className="px-2 py-2">
                          <button
                            onClick={() => setGridBand(g.grade, { watch: !g.watch })}
                            className={cn(
                              "rounded border px-1.5 py-0.5 text-[10.5px]",
                              g.watch ? "border-flag/35 bg-flag-soft text-flag-foreground" : "border-border bg-surface text-muted-foreground hover:bg-muted",
                            )}
                          >
                            {g.watch ? "In watch band" : "Not watch"}
                          </button>
                        </td>
                        <td className="px-2 py-2 text-muted-foreground">
                          {g.guidance}
                          {holders.length > 0 && (
                            <span className="mt-0.5 block text-[11.5px]">
                              {holders.length} on the book: {holders.map((h) => h.name.split(" ")[0]).join(", ")}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            </Panel>
          </div>

          {/* preview */}
          <div className="space-y-4">
            <Panel
              title="Preview — Northwind Manufacturing Ltd"
              subtitle="The seeded FY2025 spread run through the draft policy, so a change is felt before it is published."
              action={
                <Link
                  to="/appraisals/$id/spread"
                  params={{ id: "CAM-2026-0418" }}
                  className="flex h-8 items-center gap-1 rounded border border-border bg-surface px-2.5 text-[12px] hover:bg-muted"
                >
                  Open the spread <ArrowUpRight className="h-3 w-3" />
                </Link>
              }
            >
              <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
                {[
                  { n: preview.length - marginals - breaches, l: "Acceptable", t: "text-positive" },
                  { n: marginals, l: "Marginal", t: "text-flag-foreground" },
                  { n: breaches, l: "Adverse", t: "text-critical" },
                ].map((k) => (
                  <div key={k.l} className="px-4 py-3">
                    <p className={cn("text-[20px] font-semibold tabular-nums", k.t)}>{k.n}</p>
                    <p className="text-[11.5px] text-muted-foreground">{k.l}</p>
                  </div>
                ))}
              </div>
              <ul className="divide-y divide-border">
                {preview.map((p) => (
                  <li key={p.ratio.key} className="flex items-start justify-between gap-3 px-4 py-2">
                    <div className="min-w-0">
                      <p className="text-[12.5px] text-foreground">{p.ratio.label}</p>
                      <p className="text-[11.5px] text-muted-foreground">
                        {p.value === undefined ? "Not in this borrower's spread" : `${fmtRatio(p.value, p.ratio.unit)} against ${p.ratio.kind === "min" ? "min" : "max"} ${fmtRatio(p.ratio.acceptable, p.ratio.unit)}`}
                      </p>
                    </div>
                    {p.band && (
                      <span className="shrink-0 text-right">
                        <span className={cn("inline-block rounded border px-1.5 py-0.5 text-[10.5px]", BAND_TONE[p.band])}>
                          {BAND_LABEL[p.band]}
                        </span>
                        {p.wasBand && p.wasBand !== p.band && (
                          <span className="mt-0.5 block text-[11px] text-flag-foreground">was {p.wasBand}</span>
                        )}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <div className="border-t border-border bg-surface-muted/40 px-4 py-3 text-[12px] text-muted-foreground">
                {moved.length === 0 ? (
                  <>
                    Under the draft policy Northwind's classification is unchanged: {marginals} marginal ({preview.filter((p) => p.band === "marginal").map((p) => p.ratio.label).join(", ") || "none"}) and rated CCB-4 with the evidence-quality overlay.
                  </>
                ) : (
                  <>
                    <span className="font-medium text-foreground">{moved.length} of Northwind's ratios reclassify: </span>
                    {moved.map((m) => `${m.ratio.label} ${m.wasBand} to ${m.band}`).join("; ")}. The rating model would re-run on
                    the next spread refresh.
                  </>
                )}
              </div>
            </Panel>

            <Panel
              title="Impact across the book"
              subtitle={`${bookImpact.length} classification ${bookImpact.length === 1 ? "change" : "changes"} across ${BOOK.length} seeded borrowers`}
            >
              <ul className="divide-y divide-border">
                {bookImpact.map((row, i) => (
                  <li key={i} className="flex items-start justify-between gap-3 px-4 py-2.5">
                    <div className="min-w-0">
                      <Link
                        to="/borrowers/$slug"
                        params={{ slug: row.borrower.slug }}
                        className="text-[12.5px] text-primary hover:underline"
                      >
                        {row.borrower.name}
                      </Link>
                      <p className="text-[11.5px] text-muted-foreground">
                        {row.ratio.label} {fmtRatio(row.borrower.values[row.ratio.key]!, row.ratio.unit)} · {row.borrower.grade} ·{" "}
                        {row.borrower.exposure}
                      </p>
                    </div>
                    <span className="shrink-0 text-[11.5px] text-flag-foreground">
                      {row.from} → {row.to}
                    </span>
                  </li>
                ))}
                {bookImpact.length === 0 && (
                  <li className="px-4 py-4 text-[12.5px] text-muted-foreground">
                    No borrower on the seeded book changes classification under the draft. Move a threshold and this list fills as you
                    type.
                  </li>
                )}
              </ul>
            </Panel>

            <div className="rounded border border-border bg-surface p-4">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                "Show me which current borrowers this threshold change would reclassify" — the copilot back-tests the draft against the
                book and names each borrower, its analyst and the band it moves to.
              </p>
              <p className="mt-2 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                <Check className="h-3.5 w-3.5 text-positive" /> Published policy flows into every appraisal's spread and rating grid.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ThresholdInput({
  value,
  unit,
  onChange,
  plain,
}: {
  value: number;
  unit: PolicyRatio["unit"];
  onChange: (n: number) => void;
  plain?: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1">
      <input
        type="number"
        step={unit === "x" ? 0.05 : 1}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (!Number.isNaN(n)) onChange(n);
        }}
        className="h-8 w-20 rounded border border-border bg-surface px-2 text-[12.5px] tabular-nums text-foreground focus:border-primary focus:outline-none"
      />
      {!plain && <span className="text-[11.5px] text-muted-foreground">{unit === "days" ? "days" : unit}</span>}
    </span>
  );
}
