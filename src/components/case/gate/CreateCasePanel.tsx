import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  CheckCircle2,
  Files,
  Info,
  ListChecks,
  Loader2,
  ShieldCheck,
  Target,
  TextSearch,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import type { AssessmentGate, Readiness } from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { useOpenAssessment } from "@/domain/cases";
import {
  countItems,
  pointsToGo,
  readyForCredit,
  scoreText,
  toGoText,
  useTaxonomy,
} from "@/domain/checklist";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";
import { gateConditions } from "./conditions";

const DONE = new Set(["satisfied", "waived"]);

/** Where the case stands, once, at the head of the Document readiness step (F-13.4, F-13.5,
 * F-13 gate): the verdict, then the gate's three conditions, each drawn — the weighted score
 * against the review gate, no blocking requirement open, every file read — then the counts by
 * status and each gate. While the case is not yet created, how many of the three are met and the
 * action that creates it; only a role holding `review.decide` sees the action. */
export function ReadinessPanel({
  caseId,
  r,
  gate,
  blockingFindings = 0,
}: {
  caseId: string;
  r: Readiness;
  /** The case-creation gate, once the engine has worked it out. */
  gate: AssessmentGate | null;
  /** Failed blocking cross-checks (F-19.5): shown here, decided on their tab. */
  blockingFindings?: number;
}) {
  const mutation = useOpenAssessment(caseId);
  const mayCreate = useCan("review.decide");
  const taxonomy = useTaxonomy();
  const ready = readyForCredit(r);
  // As printed everywhere: never the gate's figure while the gate is unmet.
  const score = scoreText(r.score_pct, r.gate_pct);
  const counts = countItems(r.items);
  const blocking = r.items.filter((i) => i.blocking);
  const blockingDone = blocking.filter((i) => DONE.has(i.status)).length;
  const pending = gate && !gate.open;
  const conditions = pending ? gateConditions(gate) : [];
  const met = conditions.filter((c) => c.met).length;
  // What stands in the way, named on the action and on the count of conditions.
  const unmet = conditions
    .filter((c) => !c.met)
    .map((c) => c.label)
    .join("; ");
  const files = conditions.find((c) => c.key === "open_exceptions");
  const required = conditions.find((c) => c.key === "required_fields");
  const gaps = gate?.required_fields ?? [];
  const tiles = 2 + (files ? 1 : 0) + (required ? 1 : 0);
  // Creating the case with conditions not met (F-04.10): only with a reason, which the engine records.
  const [anyway, setAnyway] = useState(false);
  const [reason, setReason] = useState("");
  const gates = [
    {
      label: t("readiness.reviewGate"),
      help: t("readiness.reviewGateHelp"),
      threshold: r.gate_pct,
      met: r.gate_met,
    },
    ...(taxonomy.data
      ? [
          {
            label: t("readiness.disbursementGate"),
            help: t("readiness.disbursementGateHelp"),
            threshold: taxonomy.data.disbursement_gate_threshold,
            met: r.score_pct >= taxonomy.data.disbursement_gate_threshold && r.blocking_open === 0,
          },
        ]
      : []),
  ];
  const statuses = [
    { key: "satisfied", n: counts.satisfied },
    { key: "insufficient", n: counts.insufficient },
    { key: "missing", n: counts.missing },
    { key: "in_review", n: counts.in_review },
    { key: "waived", n: counts.waived },
  ] as const;
  const verdict = pending
    ? gate.can_open
      ? t("assessment.gateTitle")
      : t("assessment.gateTitleBlocked")
    : ready
      ? t("readinessGates.readyForCredit")
      : t("readiness.notReady");
  const go = pending ? gate.can_open : ready;

  return (
    <Panel
      title={t("caseHeader.readiness")}
      subtitle={pending ? t("assessment.gateIntro") : undefined}
      testId="create-case-panel"
      action={
        pending && (
          <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span
              className="flex items-center gap-2"
              title={t("assessment.conditionsHelp")}
              data-testid="gate-progress"
            >
              <span className="flex gap-1" aria-hidden>
                {conditions.map((c) => (
                  <span
                    key={c.key}
                    className={cn("h-1.5 w-5 rounded-full", c.met ? "bg-primary" : "bg-border")}
                  />
                ))}
              </span>
              <span className="text-[12px] text-muted-foreground">
                {t("assessment.conditionsMet", { met, total: conditions.length })}
              </span>
            </span>
            {mayCreate && (
              <button
                type="button"
                disabled={!gate.can_open || mutation.isPending}
                onClick={() => mutation.mutate(undefined)}
                title={
                  gate.can_open
                    ? t("assessment.createHelp")
                    : `${t("assessment.createBlocked")} ${unmet}`
                }
                data-testid="create-case"
                className={cn(
                  "inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12.5px] font-medium",
                  gate.can_open && !mutation.isPending
                    ? "bg-primary text-primary-foreground hover:opacity-90"
                    : "cursor-not-allowed border border-border text-muted-foreground",
                )}
              >
                {mutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
                {mutation.isPending ? t("assessment.creating") : t("assessment.create")}
              </button>
            )}
          </span>
        )
      }
    >
      <div data-testid="checklist-summary">
        {/* The verdict, the blocking requirements, and the cross-checks that block. */}
        <div
          className="flex items-start gap-2.5 px-4 py-3"
          data-testid="gate-banner"
          data-ready={ready}
        >
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent text-primary">
            {go ? (
              <ShieldCheck className="h-4 w-4" aria-hidden />
            ) : (
              <AlertTriangle className="h-4 w-4" aria-hidden />
            )}
          </span>
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-foreground">{verdict}</p>
            <p className="mt-0.5 text-[12px] text-muted-foreground" data-testid="blocking-gaps">
              {r.blocking_open > 0
                ? t("readiness.blockingOpen", { n: r.blocking_open })
                : t("readiness.noBlocking")}
            </p>
            {gate?.open && gate.opened_at && (
              <p className="mt-0.5 text-[12px] text-primary" data-testid="assessment-created">
                {t("assessment.created", { at: gate.opened_at.slice(0, 10) })}
              </p>
            )}
            {gate?.open && gate.opened_anyway && (
              <p className="mt-0.5 text-[12px] text-muted-foreground" data-testid="created-anyway">
                {t("assessment.anyway.recorded", { reason: gate.opened_anyway })}
              </p>
            )}
            {blockingFindings > 0 && (
              <Link
                to="/appraisals/$caseId/cross-verification"
                params={{ caseId }}
                className="mt-1 inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
                data-testid="blocking-findings"
              >
                {t("readiness.blockingFindings", { n: blockingFindings })} →
              </Link>
            )}
          </div>
        </div>

        {/* Each condition, drawn. */}
        <ul
          className={cn(
            "grid divide-y divide-border border-t border-border md:divide-x md:divide-y-0",
            tiles >= 4
              ? "md:grid-cols-2 xl:grid-cols-4"
              : tiles === 3
                ? "md:grid-cols-3"
                : "md:grid-cols-2",
          )}
          data-testid="gate-conditions"
        >
          <Tile
            condition="review_gate"
            met={r.gate_met}
            label={t("assessment.condition.reviewGate", { score, gate: Math.round(r.gate_pct) })}
            icon={<Target className="h-3.5 w-3.5" />}
            title={t("assessment.tile.reviewGate")}
          >
            <div className="flex items-center gap-3">
              {/* The score is shown once, in the ring. */}
              <Ring value={r.score_pct} text={score} target={r.gate_pct} met={r.gate_met} />
              <div className="text-[12px]">
                <p className="font-medium text-foreground">{t("readiness.score")}</p>
                <p className="text-muted-foreground">
                  {t("assessment.tile.needs", { gate: Math.round(r.gate_pct) })}
                </p>
                {!r.gate_met && <p className="text-muted-foreground">{toGoText(pointsToGo(r))}</p>}
              </div>
            </div>
          </Tile>

          <Tile
            condition="blocking_items"
            met={r.blocking_open === 0}
            label={t("readiness.blockingOpen", { n: r.blocking_open })}
            icon={<ListChecks className="h-3.5 w-3.5" />}
            title={t("assessment.tile.blocking")}
          >
            <p className="text-[12px]">
              <span className="mr-1 text-[20px] font-semibold leading-none tabular-nums text-foreground">
                {r.blocking_open}
              </span>
              <span className="text-muted-foreground">{t("assessment.tile.blockingOpen")}</span>
            </p>
            {blocking.length > 0 && (
              <>
                <span className="mt-2 flex gap-0.5" aria-hidden>
                  {blocking.map((i) => (
                    <span
                      key={i.item_id}
                      title={i.name}
                      className={cn(
                        "h-1.5 flex-1 rounded-sm",
                        DONE.has(i.status) ? "bg-primary" : "bg-primary/15",
                      )}
                    />
                  ))}
                </span>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {t("assessment.tile.blockingDone", {
                    done: blockingDone,
                    total: blocking.length,
                  })}
                </p>
              </>
            )}
            {r.blocking_open > 0 && (
              <a
                href="#checklist"
                className="mt-1 inline-block text-[11.5px] font-medium text-primary hover:underline"
              >
                {t("assessment.tile.showItems")} →
              </a>
            )}
          </Tile>

          {files && (
            <Tile
              condition="open_exceptions"
              met={files.met}
              label={files.label}
              icon={<Files className="h-3.5 w-3.5" />}
              title={t("assessment.tile.files")}
            >
              <p className="flex items-center gap-2 text-[12px]">
                {files.met ? (
                  <CheckCircle2 className="h-5 w-5 text-primary" aria-hidden />
                ) : (
                  <span className="text-[20px] font-semibold leading-none tabular-nums text-foreground">
                    {gate?.open_exceptions ?? 0}
                  </span>
                )}
                <span className="text-muted-foreground">
                  {files.met
                    ? t("assessment.condition.openExceptionsClear")
                    : t("assessment.tile.filesUnread")}
                </span>
              </p>
              {!files.met && (
                <Link
                  to="/appraisals/$caseId/documents"
                  params={{ caseId }}
                  className="mt-1 inline-block text-[11.5px] font-medium text-primary hover:underline"
                >
                  {t("assessment.tile.showFiles")} →
                </Link>
              )}
            </Tile>
          )}

          {required && (
            <Tile
              condition="required_fields"
              met={required.met}
              label={required.label}
              icon={<TextSearch className="h-3.5 w-3.5" />}
              title={t("assessment.tile.requiredFields")}
            >
              {required.met ? (
                <p className="flex items-center gap-2 text-[12px]">
                  <CheckCircle2 className="h-5 w-5 text-primary" aria-hidden />
                  <span className="text-muted-foreground">
                    {t("assessment.tile.requiredFieldsClear")}
                  </span>
                </p>
              ) : (
                <>
                  <p className="text-[12px]">
                    <span className="mr-1 text-[20px] font-semibold leading-none tabular-nums text-foreground">
                      {gaps.length}
                    </span>
                    <span className="text-muted-foreground">
                      {t("assessment.tile.requiredFieldsOpen")}
                    </span>
                  </p>
                  <ul className="mt-2 space-y-1.5 text-[12px]" data-testid="gate-required-fields">
                    {gaps.map((g) => (
                      <li key={g.field} data-testid="required-field-gap" data-field={g.field}>
                        <p className="font-medium text-foreground">{g.label}</p>
                        {(g.stops ?? []).length > 0 && (
                          <p className="text-[11.5px] text-muted-foreground">
                            {t("assessment.tile.stops", { stops: (g.stops ?? []).join(", ") })}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </Tile>
          )}
        </ul>

        {/* Creating the case with conditions not met: a reason is required and recorded (F-04.10). */}
        {pending && !gate.can_open && mayCreate && (
          <div className="border-t border-border px-4 py-2.5" data-testid="create-anyway">
            {!anyway ? (
              <button
                type="button"
                onClick={() => setAnyway(true)}
                className="text-[12px] font-medium text-primary hover:underline"
                data-testid="create-anyway-open"
              >
                {t("assessment.anyway.open")}
              </button>
            ) : (
              <form
                className="grid gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (reason.trim()) mutation.mutate(reason.trim());
                }}
              >
                <p className="text-[12.5px] font-semibold text-foreground">
                  {t("assessment.anyway.title")}
                </p>
                <p className="text-[12px] text-muted-foreground">{t("assessment.anyway.help")}</p>
                <label className="grid gap-1">
                  <span className="field-label">{t("assessment.anyway.reason")}</span>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={3}
                    maxLength={2000}
                    placeholder={t("assessment.anyway.placeholder")}
                    className="w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] focus:outline-none focus:ring-2 focus:ring-primary/40"
                    data-testid="create-anyway-reason"
                  />
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="submit"
                    disabled={!reason.trim() || mutation.isPending}
                    className={cn(
                      "inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12.5px] font-medium",
                      reason.trim() && !mutation.isPending
                        ? "bg-primary text-primary-foreground hover:opacity-90"
                        : "cursor-not-allowed border border-border text-muted-foreground",
                    )}
                    data-testid="create-anyway-submit"
                  >
                    {mutation.isPending && (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                    )}
                    {t("assessment.anyway.submit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAnyway(false);
                      setReason("");
                    }}
                    className="rounded border border-border px-3 py-1.5 text-[12.5px] text-muted-foreground hover:bg-surface-muted"
                  >
                    {t("assessment.anyway.cancel")}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {/* The counts by status and each gate. */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border px-4 py-2.5">
          <dl className="grid grid-cols-3 gap-x-4 gap-y-1 text-[12px] sm:flex sm:flex-wrap">
            {statuses.map((s) => (
              <div key={s.key} className="flex gap-1">
                <dt className="text-muted-foreground">{t(`docStatus.${s.key}`)}</dt>
                <dd
                  className={cn(
                    "tabular font-semibold",
                    s.n > 0 ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {s.n}
                </dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-wrap gap-2 sm:ml-auto">
            {gates.map((g) => (
              <span
                key={g.label}
                data-testid="gate"
                title={`${g.help} ${t("readiness.threshold", { threshold: Math.round(g.threshold), score })}`}
              >
                <Chip tone={g.met ? "primary" : "muted"}>
                  {g.label} {Math.round(g.threshold)}% ·{" "}
                  {g.met ? t("readiness.met") : t("readiness.notMet")}
                </Chip>
              </span>
            ))}
          </div>
        </div>
        {r.provisional && (
          <p
            className="flex items-start gap-2 border-t border-border bg-accent/40 px-4 py-2 text-[12px] text-accent-foreground"
            data-testid="provisional"
          >
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
            {t("checklist.provisionalHelp")}
          </p>
        )}
        {mutation.isError && (
          <p
            className="border-t border-border px-4 py-2 text-[12px] text-critical-text"
            data-testid="create-case-error"
          >
            {t("assessment.error.failed")}
          </p>
        )}
      </div>
    </Panel>
  );
}

/** One condition: its name, met or not, and its picture. */
function Tile({
  condition,
  met,
  label,
  icon,
  title,
  children,
}: {
  condition: string;
  met: boolean;
  label: string;
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <li
      className="px-4 py-3"
      data-testid="gate-condition"
      data-condition={condition}
      data-met={met}
      title={label}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {icon}
          {title}
        </span>
        <Chip tone={met ? "primary" : "muted"}>
          {t(met ? "assessment.tile.met" : "assessment.tile.notMet")}
        </Chip>
      </div>
      {children}
    </li>
  );
}

/** The score as a ring: the solid arc is the score, the pale arc after it is the way still
 * to go to the gate, and the rest of the ring is grey. */
function Ring({
  value,
  text,
  target,
  met,
}: {
  value: number;
  /** The score as printed. */
  text: string;
  target: number;
  met: boolean;
}) {
  const r = 20;
  const c = 2 * Math.PI * r;
  const clamp = (pct: number) => Math.min(100, Math.max(0, pct)) / 100;
  const done = clamp(value) * c;
  const gap = Math.max(0, clamp(target) * c - done);
  const arc = { cx: 26, cy: 26, r, fill: "none", strokeWidth: 5, transform: "rotate(-90 26 26)" };
  return (
    <svg width="52" height="52" viewBox="0 0 52 52" role="img" aria-label={`${text}%`}>
      <circle {...arc} className="stroke-border" />
      {!met && gap > 0 && (
        <circle
          {...arc}
          strokeDasharray={`${gap} ${c}`}
          strokeDashoffset={-done}
          className="stroke-primary/20"
        />
      )}
      <circle {...arc} strokeDasharray={`${done} ${c}`} className="stroke-primary" />
      <text
        x="26"
        y="30"
        textAnchor="middle"
        className="tabular fill-foreground text-[11px] font-semibold"
        data-testid="readiness-score"
      >
        {text}%
      </text>
    </svg>
  );
}
