import { useState } from "react";
import { AlertTriangle, CheckCircle2, HelpCircle, MinusCircle } from "lucide-react";
import type { NormOutcome, NormResult, PolicyAssessment } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { usePolicy } from "@/domain/findings";
import { cn } from "@/lib/utils";

// The Policy tab (FRD §6, F-20): every norm with the required and actual
// value, the figures it used with their pages, and pass or deviation. The
// deviations, by category, are what the CAM summarises (F-20.4).

const OUTCOMES: NormOutcome[] = ["deviation", "cannot_evaluate", "pass", "not_applicable"];
const FAMILIES = ["eligibility", "ratios", "security_cover", "documentation"] as const;

const ICON = {
  deviation: AlertTriangle,
  cannot_evaluate: HelpCircle,
  pass: CheckCircle2,
  not_applicable: MinusCircle,
} as const;
const TONE = {
  deviation: "text-destructive",
  cannot_evaluate: "text-flag-foreground",
  pass: "text-positive",
  not_applicable: "text-muted-foreground",
} as const;

function amount(value: number | null | undefined, unit: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  switch (unit) {
    case "x":
      return `${value.toFixed(2)}x`;
    case "%":
      return `${value.toFixed(1)}%`;
    case "days":
      return `${Math.round(value)} days`;
    case "years":
      return `${value} years`;
    case "inr":
      return formatInr(value);
    case "rank":
      return t("policy.rank", { n: value });
    default:
      return String(value);
  }
}

/** An input as a reader expects it: rupees, years, a rank or a count. */
function inputValue(name: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (name === "vintage_years" || name === "audited_years") return amount(value, "years");
  if (name === "bureau_rank") return amount(value, "rank");
  if (name === "blocking_items_open") return String(value);
  return formatInr(value);
}

function NormRow({ caseId, norm }: { caseId: string; norm: NormResult }) {
  const viewer = useDocViewer();
  const Icon = ICON[norm.outcome];
  return (
    <li
      className="space-y-1.5 px-4 py-3"
      data-testid="norm"
      data-norm={norm.id}
      data-outcome={norm.outcome}
    >
      <div className="flex flex-wrap items-start gap-2">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", TONE[norm.outcome])} />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-foreground">
            {norm.label}
            {norm.outcome === "deviation" && <Chip tone="critical">{norm.category_label}</Chip>}
            {norm.provisional && <Chip tone="muted">{t("policy.provisional")}</Chip>}
          </p>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">{norm.formula}</p>
        </div>
        <div className="grid shrink-0 grid-cols-2 gap-x-4 text-right text-[12px]">
          <span className="text-muted-foreground">{t("policy.required")}</span>
          <span className="text-muted-foreground">{t("policy.actual")}</span>
          <span className="tabular">{norm.required}</span>
          <span
            className={cn("tabular font-semibold", TONE[norm.outcome])}
            data-testid="norm-actual"
          >
            {norm.outcome === "cannot_evaluate" || norm.outcome === "not_applicable"
              ? t(`policy.outcome.${norm.outcome}`)
              : amount(norm.actual, norm.unit)}
          </span>
        </div>
      </div>
      {(norm.missing ?? []).length > 0 && (
        <p className="ml-6 text-[12px] text-flag-foreground" data-testid="norm-missing">
          {t("policy.missing", { inputs: (norm.missing ?? []).join(", ") })}
        </p>
      )}
      {norm.outcome !== "not_applicable" && (norm.inputs ?? []).length > 0 && (
        <ul className="ml-6 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px]">
          {(norm.inputs ?? []).map((input) => {
            const e = input.evidence?.[0];
            return (
              <li
                key={input.name}
                className="inline-flex items-center gap-1"
                data-testid="norm-input"
              >
                <span className="text-muted-foreground">{input.label}</span>
                {e ? (
                  <button
                    type="button"
                    onClick={() =>
                      viewer.open({
                        caseId,
                        documentId: e.document_id,
                        page: e.page,
                        bbox: e.bbox ?? null,
                      })
                    }
                    className="tabular font-medium text-primary underline decoration-dotted underline-offset-2"
                  >
                    {inputValue(input.name, input.value)}
                  </button>
                ) : (
                  <span className="tabular font-medium">{inputValue(input.name, input.value)}</span>
                )}
                {input.relies_on_manual && <Chip tone="flag">{t("crossCheck.manual")}</Chip>}
              </li>
            );
          })}
        </ul>
      )}
    </li>
  );
}

function Summary({ policy }: { policy: PolicyAssessment }) {
  const deviations = policy.norms.filter((n) => n.outcome === "deviation");
  const byCategory = new Map<string, string[]>();
  for (const d of deviations)
    byCategory.set(d.category_label, [...(byCategory.get(d.category_label) ?? []), d.label]);
  return (
    <div
      className="rounded border border-border bg-surface px-4 py-3"
      data-testid="deviation-summary"
    >
      <p className="text-[13px] font-semibold">
        {deviations.length === 0
          ? t("policy.noDeviations")
          : t("policy.deviations", { n: deviations.length })}
      </p>
      {[...byCategory].map(([category, labels]) => (
        <p key={category} className="mt-0.5 text-[12px] text-muted-foreground">
          <span className="font-medium text-foreground">{category}:</span> {labels.join(", ")}
        </p>
      ))}
      {policy.period && (
        <p className="mt-1 text-[11.5px] text-muted-foreground">
          {t("policy.period", { period: policy.period })}
        </p>
      )}
    </div>
  );
}

export function PolicyPanel({ caseId }: { caseId: string }) {
  const policy = usePolicy(caseId);
  const [filter, setFilter] = useState<NormOutcome | "all">("all");
  return (
    <QueryView query={policy}>
      {(p) => {
        const count = (o: NormOutcome) => p.norms.filter((n) => n.outcome === o).length;
        const shown = p.norms.filter((n) => filter === "all" || n.outcome === filter);
        return (
          <div className="space-y-4">
            <Summary policy={p} />
            <Panel
              title={t("policy.title")}
              subtitle={t("policy.summary", {
                n: p.norms.length,
                deviation: count("deviation"),
                cannot: count("cannot_evaluate"),
                pass: count("pass"),
              })}
              testId="norms"
            >
              <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2">
                {(["all", ...OUTCOMES] as const).map((o) => (
                  <button
                    key={o}
                    type="button"
                    aria-pressed={filter === o}
                    onClick={() => setFilter(o)}
                    data-testid={`norms-filter-${o}`}
                    className={cn(
                      "rounded border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
                      filter === o
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-surface text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {t(`policy.filter.${o}`, { n: o === "all" ? p.norms.length : count(o) })}
                  </button>
                ))}
              </div>
              <div className="divide-y divide-border">
                {FAMILIES.map((family) => {
                  const norms = shown.filter((n) => n.family === family);
                  if (norms.length === 0) return null;
                  return (
                    <div key={family}>
                      <p className="bg-surface-muted/70 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                        {t(`policy.family.${family}`)}
                      </p>
                      <ul className="divide-y divide-border">
                        {norms.map((n) => (
                          <NormRow key={n.id} caseId={caseId} norm={n} />
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </Panel>
          </div>
        );
      }}
    </QueryView>
  );
}
