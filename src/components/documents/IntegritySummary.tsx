import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock,
  FileText,
  Info,
  Layers,
  Maximize2,
  RotateCw,
  ScanLine,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  UserCheck,
  Wrench,
} from "lucide-react";
import type { FileRecord, IntegrityFinding, LogicalDocument } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { t, tOr } from "@/config/terminology";
import { useReadAgain, useRecheckIntegrity, useReviewIntegrity } from "@/domain/documents";
import {
  KIND_TONE,
  STATE_TONE,
  humanTimes,
  localTime,
  madeAsOf,
  stateOf,
  type CheckKind,
  type IntegrityState,
  type MadeAs,
} from "@/domain/integrity";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";

/** F-07A: what a file's integrity checks came to, and what a person concluded — kept apart.
 * The status is the engine's (engine/integrity_status.py), never worked out here. Each part
 * says what was found, what is still unchecked, why it matters and what to do next. */

const STATE_ICON: Record<IntegrityState, typeof ShieldCheck> = {
  passed: ShieldCheck,
  review_recommended: ShieldQuestion,
  suspicious: ShieldAlert,
  suspicious_high: ShieldAlert,
  incomplete: Clock,
  failed: Wrench,
  not_checked: Clock,
  not_applicable: Info,
};

const STATE_FRAME: Record<IntegrityState, string> = {
  passed: "border-positive/30 bg-positive-soft/40",
  review_recommended: "border-flag/40 bg-flag/5",
  suspicious: "border-destructive/40 bg-destructive/5",
  suspicious_high: "border-destructive/50 bg-destructive/10",
  incomplete: "border-flag/40 bg-flag/5",
  failed: "border-flag/40 bg-flag/5",
  not_checked: "border-border bg-background",
  not_applicable: "border-border bg-background",
};

/** The file's integrity status in a word, as a chip. */
export function StateChip({ file, className }: { file: FileRecord; className?: string }) {
  const state = stateOf(file);
  const Icon = STATE_ICON[state];
  return (
    <Chip tone={STATE_TONE[state]} {...(className ? { className } : {})}>
      <Icon className="h-3 w-3" />
      {t(`fileIntegrity.state.${state}`)}
    </Chip>
  );
}

const title = (code: string) => tOr(`fileIntegrity.check.${code}`, code);
/** A finding as a short noun phrase ("Block over printed text"), for one-line lists. */
const short = (code: string) => tOr(`fileIntegrity.short.${code}`, title(code));

/** A check's result in plain words: passed, suspicious indicator, informational
 * observation, not applicable, not run, execution failed. */
export function KindLabel({ kind }: { kind: CheckKind }) {
  return (
    <span className={cn("text-[10.5px] font-medium", KIND_TONE[kind])} data-kind={kind}>
      {t(`fileIntegrity.kind.${kind}`)}
    </span>
  );
}

const BAND_BAR: Record<string, string> = {
  none: "bg-positive",
  weak: "bg-flag",
  moderate: "bg-flag",
  strong: "bg-destructive",
};

const BAND_BADGE: Record<string, string> = {
  none: "border-positive/40 bg-positive-soft text-positive",
  weak: "border-flag/40 bg-flag/10 text-flag-foreground",
  moderate: "border-flag/50 bg-flag/15 text-flag-foreground",
  strong: "border-destructive/40 bg-destructive/10 text-destructive",
};

/** The overall evidence strength in one badge, beside the status: "Score 75/100 · strong".
 * What it means is on hover; how it was reached is in the detailed evidence. */
export function ScoreBadge({ file }: { file: FileRecord }) {
  const status = file.integrity_status;
  if (status?.score == null || !status.band) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
        BAND_BADGE[status.band],
      )}
      title={t("fileIntegrity.score.explain")}
      data-testid="integrity-score-badge"
      data-score={status.score}
    >
      {t("fileIntegrity.score.short")} {status.score}/100
      <span className="font-normal">· {t(`fileIntegrity.score.band.${status.band}`)}</span>
    </span>
  );
}

const MADE_ICON: Record<MadeAs, typeof FileText> = {
  digital: FileText,
  scanned: ScanLine,
  mixed: Layers,
  image: ScanLine,
};

/** Digital or scanned, in one chip. What it means is on hover. */
export function MadeAsChip({
  file,
  documents,
}: {
  file: FileRecord;
  documents?: LogicalDocument[] | undefined;
}) {
  const made = madeAsOf(file, documents);
  if (!made) return null;
  const Icon = MADE_ICON[made.kind];
  return (
    <span
      className="inline-flex items-center gap-1 rounded border border-border bg-muted/40 px-1.5 py-0.5 text-[11px] font-medium text-foreground"
      title={t(`fileIntegrity.origin.explain.${made.kind}`)}
      data-testid="integrity-made-as"
      data-kind={made.kind}
    >
      <Icon className="h-3 w-3" />
      {t(`fileIntegrity.origin.${made.kind}`)}
    </span>
  );
}

/** Evidence strength, 0–100 (never 100): how strongly the file contradicts itself. With
 * `detail`, how it was reached, indicator by indicator. */
export function EvidenceStrength({ file, detail }: { file: FileRecord; detail?: boolean }) {
  const status = file.integrity_status;
  if (status?.score == null || !status.band) return null;
  return (
    <div className="mt-1.5" data-testid="integrity-score" data-score={status.score}>
      <div className="flex items-center gap-2 text-[11px]">
        <span className="font-medium text-foreground">{t("fileIntegrity.score.label")}</span>
        <span className="h-1.5 w-28 overflow-hidden rounded-full bg-muted" aria-hidden>
          <span
            className={cn("block h-full rounded-full", BAND_BAR[status.band])}
            style={{ width: `${Math.max(status.score, 2)}%` }}
          />
        </span>
        <span className="font-semibold tabular-nums text-foreground">{status.score}/100</span>
        <span className="text-muted-foreground">
          · {t(`fileIntegrity.score.band.${status.band}`)}
        </span>
      </div>
      <p className="text-[10px] text-muted-foreground">{t("fileIntegrity.score.explain")}</p>
      {detail && (status.score_parts?.length ?? 0) > 0 && (
        <ul
          className="mt-1 space-y-0.5 text-[10.5px] text-muted-foreground"
          data-testid="integrity-score-parts"
        >
          {(status.score_parts ?? []).map((p) => (
            <li key={p.code}>
              {t("fileIntegrity.score.part", {
                check: short(p.code),
                points: Math.round(p.points),
                adds: Math.round(p.adds),
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Next to an observation or a suspicious indicator: why it matters, from its configuration. */
function WhyItMatters({ f }: { f: IntegrityFinding }) {
  const why = f.method?.["limitations"];
  const next = f.method?.["next_step"];
  if (!why && !next) return null;
  return (
    <p className="text-[10.5px] text-muted-foreground">
      {why && (
        <>
          <span className="font-medium">{t("fileIntegrity.summary.whyMatters")}:</span> {why}{" "}
        </>
      )}
      {next && (
        <>
          <span className="font-medium">{t("fileIntegrity.summary.nextStep")}:</span> {next}
        </>
      )}
    </p>
  );
}

/** One finding on one line: what it is, what was measured, and the way to its place. */
function FindingLine({
  f,
  tone,
  onShow,
  detail,
}: {
  f: IntegrityFinding;
  tone: string;
  onShow?: ((f: IntegrityFinding) => void) | undefined;
  detail: boolean;
}) {
  const placed = (f.evidence ?? []).find((e) => e.rect);
  const measured = f.evidence?.[0]?.observed;
  const [open, setOpen] = useState(false);
  return (
    <li className="text-[11px]">
      <span className="flex flex-wrap items-baseline gap-x-1.5">
        {detail ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-label={t(open ? "fileIntegrity.summary.less" : "fileIntegrity.summary.more")}
            data-testid="finding-toggle"
            className="self-start text-muted-foreground hover:text-foreground"
          >
            {open ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className={cn("mt-1 h-1.5 w-1.5 shrink-0 self-start rounded-full", tone)} />
        )}
        {detail && (
          <span className={cn("mt-1 h-1.5 w-1.5 shrink-0 self-start rounded-full", tone)} />
        )}
        <span className="font-semibold text-foreground">{short(f.code)}</span>
        {measured && <span className="text-muted-foreground">— {humanTimes(measured)}</span>}
        {onShow && placed && (
          <button
            type="button"
            onClick={() => onShow(f)}
            className="ml-auto font-medium text-primary hover:underline"
          >
            {t("fileIntegrity.showOnPage", { page: placed.page })}
          </button>
        )}
      </span>
      {detail && open && (
        <span className="block pl-7">
          <span className="block text-[10.5px] text-muted-foreground">{humanTimes(f.finding)}</span>
          <WhyItMatters f={f} />
        </span>
      )}
    </li>
  );
}

/** Integrity, automated: the status in a sentence, the evidence strength, the counts that
 * are not zero, and one line per finding. `compact` (the Files page) leaves the reasons
 * and the scoring to the detailed evidence. */
export function IntegritySummary({
  caseId,
  file,
  onShow,
  compact = false,
  showEvidenceLink = true,
}: {
  caseId: string;
  file: FileRecord;
  /** Opens the place on the page a suspicious indicator points at, where the page is shown. */
  onShow?: ((f: IntegrityFinding) => void) | undefined;
  compact?: boolean;
  showEvidenceLink?: boolean;
}) {
  const status = file.integrity_status;
  const state = stateOf(file);
  const found = file.integrity ?? [];
  const by = (codes: readonly string[]) =>
    codes.map((c) => found.find((f) => f.code === c)).filter((f): f is IntegrityFinding => !!f);
  const suspicious = by(status?.suspicious ?? []);
  const informational = by(status?.informational ?? []);
  const failed = by(status?.failed ?? []);
  const pending = status?.pending ?? [];
  const recheck = useRecheckIntegrity(caseId);
  const readAgain = useReadAgain(caseId);
  const canUpload = useCan("document.upload");
  const counts = (
    [
      ["passed", status?.passed ?? 0, "text-positive"],
      ["suspicious", suspicious.length, "text-destructive"],
      ["informational", informational.length, "text-flag-foreground"],
      ["notRun", pending.length, "text-flag-foreground"],
      ["failed", failed.length, "text-flag-foreground"],
      ["notApplicable", status?.not_applicable ?? 0, "text-muted-foreground"],
    ] as const
  ).filter(([key, n]) => n > 0 || key === "passed");
  const canRecheck =
    canUpload && file.status === "registered" && (state === "incomplete" || state === "failed");
  const canReadAgain = canUpload && file.status === "exception";
  const running = recheck.isPending || recheck.isSuccess;

  return (
    <section
      className={cn("rounded-md border px-3 py-2.5", STATE_FRAME[state])}
      data-testid="integrity-summary"
      data-state={state}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
          {t("fileIntegrity.summary.title")}
        </p>
        <span className="flex flex-wrap items-center gap-1.5">
          <MadeAsChip file={file} />
          <StateChip file={file} />
          <ScoreBadge file={file} />
        </span>
      </div>
      <p className="mt-1 text-[12px] font-medium text-foreground" data-testid="integrity-headline">
        {t(`fileIntegrity.headline.${state}`, {
          n:
            state === "incomplete"
              ? pending.length
              : (status?.passed ?? 0) + (status?.not_applicable ?? 0),
        })}
      </p>
      {!compact && <EvidenceStrength file={file} detail />}
      <p
        className="mt-1.5 flex flex-wrap gap-x-2 text-[11px]"
        data-testid="integrity-summary-counts"
      >
        {counts.map(([key, n, tone], i) => (
          <span key={key} className={tone}>
            {i > 0 && <span className="mr-2 text-muted-foreground">·</span>}
            <span className="font-semibold tabular-nums">{n}</span>{" "}
            {t(`fileIntegrity.summary.count.${key}`)}
          </span>
        ))}
      </p>

      {(suspicious.length > 0 || informational.length > 0) && (
        <ul
          className="mt-2 space-y-1 border-t border-border/70 pt-1.5"
          data-testid="summary-findings"
        >
          {suspicious.map((f) => (
            <FindingLine
              key={f.code}
              f={f}
              tone="bg-destructive"
              onShow={onShow}
              detail={!compact}
            />
          ))}
          {informational.map((f) => (
            <FindingLine key={f.code} f={f} tone="bg-flag" detail={!compact} />
          ))}
        </ul>
      )}
      {pending.length > 0 && (
        <p className="mt-1.5 text-[11px] text-muted-foreground" data-testid="summary-not-run">
          <Clock className="mr-1 inline h-3 w-3" />
          <span className="font-medium text-foreground">
            {t("fileIntegrity.summary.notRunTitle")}:
          </span>{" "}
          {pending.map(short).join(" · ")}
          {(status?.unconfigured?.length ?? 0) > 0 && (
            <span className="block text-flag-foreground" data-testid="summary-unconfigured">
              {t("fileIntegrity.summary.unconfigured", { n: status?.unconfigured?.length ?? 0 })}
            </span>
          )}
        </p>
      )}
      {(failed.length > 0 || status?.stopped) && (
        <p className="mt-1.5 text-[11px] text-muted-foreground" data-testid="summary-failed">
          <Wrench className="mr-1 inline h-3 w-3" />
          {status?.stopped && file.reason
            ? t("fileIntegrity.summary.stopped", { reason: file.reason })
            : failed.map((f) => `${short(f.code)}: ${f.finding}`).join(" · ")}
        </p>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border/70 pt-1.5">
        {canRecheck && (
          <button
            type="button"
            onClick={() => recheck.mutate(file.id)}
            disabled={running}
            title={t("fileIntegrity.recheckHelp")}
            data-testid="integrity-recheck"
            className="inline-flex items-center gap-1 rounded bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            <RotateCw className={cn("h-3 w-3", running && "animate-spin")} />
            {t(running ? "fileIntegrity.rechecking" : "fileIntegrity.summary.runRemaining")}
          </button>
        )}
        {canReadAgain && (
          <button
            type="button"
            onClick={() => readAgain.mutate(file.id)}
            disabled={readAgain.isPending}
            title={t("documents.readAgainHelp")}
            className="inline-flex items-center gap-1 rounded bg-primary px-2 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            <RotateCw className={cn("h-3 w-3", readAgain.isPending && "animate-spin")} />
            {t(readAgain.isPending ? "documents.readingAgain" : "documents.readAgain")}
          </button>
        )}
        {showEvidenceLink && (
          <Link
            to="/appraisals/$caseId/files/$fileId/integrity"
            params={{ caseId, fileId: file.id }}
            data-testid="integrity-open-view"
            className="inline-flex items-center gap-1 rounded border border-primary/40 bg-background px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/10"
          >
            <Maximize2 className="h-3 w-3" />
            {t("fileIntegrity.summary.openEvidence")}
          </Link>
        )}
        <span className="ml-auto text-[10px] italic text-muted-foreground">
          {t("fileIntegrity.caveat")}
        </span>
      </div>
    </section>
  );
}

const DECISIONS = ["genuine", "altered", "unclear", "not_completed"] as const;
type Decision = (typeof DECISIONS)[number];

const DECISION_TONE: Record<Decision, string> = {
  genuine: "border-positive/50 bg-positive-soft text-positive",
  altered: "border-destructive/50 bg-destructive/10 text-destructive",
  unclear: "border-flag/50 bg-flag/10 text-flag-foreground",
  not_completed: "border-border bg-muted text-muted-foreground",
};

/** A person's conclusion on the file, separate from what the checks found: recorded with a
 * reason, the reviewer and the time, never set by the checks. */
export function HumanReview({ caseId, file }: { caseId: string; file: FileRecord }) {
  const review = file.integrity_review ?? null;
  const canDecide = useCan("review.decide");
  const save = useReviewIntegrity(caseId);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  const error = save.error instanceof Error ? save.error.message : null;

  return (
    <section
      className="rounded-md border border-border bg-background px-3 py-2.5"
      data-testid="integrity-review"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          data-testid="integrity-review-toggle"
          className="flex items-center gap-1 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          <UserCheck className="h-3.5 w-3.5" />
          {t("fileIntegrity.review.title")}
        </button>
        {review ? (
          <span
            className={cn(
              "rounded border px-1.5 py-0.5 text-[11px] font-semibold",
              DECISION_TONE[review.decision],
            )}
            data-testid="integrity-review-decision"
          >
            {t(`fileIntegrity.review.decision.${review.decision}`)}
          </span>
        ) : (
          <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] font-semibold text-muted-foreground">
            {t("fileIntegrity.review.pending")}
          </span>
        )}
      </div>
      {review && (
        <p className="mt-1 text-[11px] text-foreground">
          “{review.reason || "—"}”{" "}
          <span className="text-muted-foreground">
            {t("fileIntegrity.review.by", {
              decision: t(`fileIntegrity.review.decision.${review.decision}`),
              who: review.decided_by,
              when: localTime(review.decided_at),
            })}
          </span>
        </p>
      )}
      {open && (
        <p className="mt-1 text-[10.5px] text-muted-foreground">
          {t("fileIntegrity.review.separate")}
        </p>
      )}
      {!open ? null : canDecide ? (
        <form
          className="mt-2 space-y-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (decision)
              save.mutate(
                { fileId: file.id, decision, reason },
                {
                  onSuccess: () => {
                    setDecision(null);
                    setReason("");
                  },
                },
              );
          }}
        >
          <div
            className="flex flex-wrap gap-1.5"
            role="radiogroup"
            aria-label={t("fileIntegrity.review.title")}
          >
            {DECISIONS.map((d) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={decision === d}
                onClick={() => setDecision(d)}
                data-testid={`integrity-decide-${d}`}
                className={cn(
                  "rounded border px-2 py-1 text-[11px] font-medium",
                  decision === d
                    ? DECISION_TONE[d]
                    : "border-border text-foreground hover:bg-muted",
                )}
              >
                {t(`fileIntegrity.review.decision.${d}`)}
              </button>
            ))}
          </div>
          <label className="block text-[11px] text-muted-foreground">
            {t("fileIntegrity.review.reason")}
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              placeholder={t("fileIntegrity.review.reasonHint")}
              data-testid="integrity-review-reason"
              className="mt-0.5 block w-full rounded border border-border bg-background px-2 py-1 text-[11.5px] text-foreground"
            />
          </label>
          {error && (
            <p className="flex items-center gap-1 text-[11px] text-destructive">
              <CircleAlert className="h-3 w-3" />
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={!decision || save.isPending}
            data-testid="integrity-review-save"
            className="rounded bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {t(save.isPending ? "fileIntegrity.review.saving" : "fileIntegrity.review.save")}
          </button>
        </form>
      ) : (
        <p className="mt-1 text-[10.5px] text-muted-foreground">
          {t("fileIntegrity.review.cannot")}
        </p>
      )}
    </section>
  );
}
