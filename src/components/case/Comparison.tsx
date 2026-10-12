import { useState } from "react";
import { toast } from "sonner";
import type {
  AreaScore,
  CaseComparison,
  ComparisonArea,
  ComparisonItem,
  ComparisonNote,
  ComparisonStatus,
  ReferenceRecord,
  Verdict,
} from "@/api/types";
import { stepSentence } from "@/components/case/ApprovingAuthority";
import { Chip, Panel, type Tone } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { decisionButton } from "@/components/review/styles";
import { t, tOr } from "@/config/terminology";
import { usePolicyConfig } from "@/domain/admin";
import { formatDate } from "@/domain/cases";
import {
  AREAS,
  FILTERS,
  matches,
  useAdjudicate,
  useComparison,
  useConfirmReference,
  type ComparisonFilter,
} from "@/domain/comparison";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

// The Comparison tab (FRD F-25): CreditIQ's deviations and approving
// authority beside RBL's confirmed record, for the reviewer to adjudicate.
// Decisions are recorded beside the output and never change it (F-25.5).

const STATUS_TONE: Record<ComparisonStatus, Tone> = {
  agree: "positive",
  differ: "flag",
  new: "info",
  missed: "critical",
};

const GRID = "sm:grid sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_7rem] sm:gap-3";

function RecordBar({ caseId, record }: { caseId: string; record: ReferenceRecord }) {
  const session = useSession();
  const confirm = useConfirmReference(caseId);
  const self = session?.user.id === record.imported_by;
  return (
    <div
      className="space-y-1 rounded border border-border bg-surface px-4 py-3 text-[12.5px]"
      data-testid="record-status"
      data-confirmed={record.confirmed_by ? "true" : "false"}
    >
      <p className="text-foreground">
        {t("comparison.record.imported", {
          workbook: record.workbook_name,
          date: formatDate(record.imported_at),
        })}
      </p>
      {record.confirmed_by ? (
        <p className="text-positive">
          {t("comparison.record.confirmed", {
            name: record.confirmed_by_name ?? record.confirmed_by,
            date: formatDate(record.confirmed_at ?? record.imported_at),
          })}
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-flag-foreground">{t("comparison.record.unconfirmed")}</span>
          <button
            type="button"
            disabled={self || confirm.isPending}
            onClick={() =>
              confirm.mutate(undefined, {
                onSuccess: () => toast.success(t("review.recorded")),
              })
            }
            className="h-7 rounded bg-primary px-2.5 text-[11.5px] font-medium text-primary-foreground disabled:opacity-40"
            data-testid="record-confirm"
          >
            {t("comparison.record.confirm")}
          </button>
          {self && (
            <span className="text-[11.5px] text-muted-foreground" data-testid="record-self-confirm">
              {t("comparison.record.selfConfirm")}
            </span>
          )}
        </div>
      )}
      {!record.deviations_recorded && (
        <p className="text-muted-foreground" data-testid="record-none-recorded">
          {t("comparison.record.noneRecorded")}
        </p>
      )}
    </div>
  );
}

function noteText(
  item: ComparisonItem,
  kind: ComparisonNote,
  categoryLabel: (key: string) => string,
): string {
  const norm = item.norm;
  const record = item.record_deviation;
  switch (kind) {
    case "value_differs":
      return t("comparison.note.value_differs", {
        creditiq: item.creditiq_text ?? "—",
        record: record?.recorded_value ?? "—",
      });
    case "category_differs":
      return t("comparison.note.category_differs", {
        creditiq: norm?.category_label ?? "—",
        record: record?.category ? categoryLabel(record.category) : "—",
      });
    case "pass":
      return t("comparison.note.pass", {
        actual: norm?.actual_text ?? "—",
        required: norm?.required ?? "—",
      });
    case "cannot_evaluate": {
      const names = norm?.reason_inputs?.length ? norm.reason_inputs : (norm?.missing ?? []);
      const inputs = names
        .map((n) => norm?.inputs?.find((i) => i.name === n)?.label ?? tOr(`policy.input.${n}`, n))
        .join(", ");
      return t("comparison.note.cannot_evaluate", { inputs: inputs || "—" });
    }
    default:
      return t(`comparison.note.${kind}`);
  }
}

function CreditIqCell({ caseId, item }: { caseId: string; item: ComparisonItem }) {
  const viewer = useDocViewer();
  if (item.area === "approving_authority") {
    const required = item.required?.required;
    return (
      <span className="font-medium">
        {required
          ? `${required.label} · ${t("approvingAuthority.level", { n: required.level })}`
          : "—"}
      </span>
    );
  }
  const norm = item.norm;
  if (!norm) return <span className="text-muted-foreground">—</span>;
  const text =
    norm.outcome === "deviation" || norm.outcome === "pass"
      ? (item.creditiq_text ?? norm.actual_text ?? t("policy.unbounded"))
      : t(`policy.outcome.${norm.outcome}`);
  const evidence = norm.inputs?.find((i) => (i.evidence ?? []).length > 0)?.evidence?.[0];
  return (
    <span className="space-y-0.5">
      {evidence ? (
        <button
          type="button"
          onClick={() =>
            viewer.open({
              caseId,
              documentId: evidence.document_id,
              page: evidence.page,
              bbox: evidence.bbox ?? null,
            })
          }
          className="tabular block text-left font-medium text-primary underline decoration-dotted underline-offset-2"
          data-testid="comparison-creditiq-evidence"
        >
          {text}
        </button>
      ) : (
        <span className="tabular block font-medium">{text}</span>
      )}
      <span className="block text-[11.5px] text-muted-foreground">{norm.required}</span>
    </span>
  );
}

function RecordCell({ item }: { item: ComparisonItem }) {
  const source = item.record_deviation?.source_ref ?? item.record_approval?.source_ref;
  if (!item.record_text) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="space-y-0.5">
      <span className="block font-medium">{item.record_text}</span>
      {item.record_deviation?.approved_by_text && (
        <span className="block text-[11.5px] text-muted-foreground">
          {item.record_deviation.approved_by_text}
        </span>
      )}
      {source && (
        <span
          className="block text-[11.5px] text-muted-foreground"
          data-testid="comparison-record-where"
        >
          {t("comparison.record.where")}: {source}
        </span>
      )}
    </span>
  );
}

function AuthorityDetail({ item }: { item: ComparisonItem }) {
  const required = item.required;
  if (!required) return null;
  const governing = required.steps.find((s) => s.governs);
  return (
    <div
      className="space-y-1 text-[12px] text-muted-foreground"
      data-testid="comparison-authority-detail"
    >
      {governing && (
        <p>
          {t("comparison.authority.ruleApplied", {
            rule: stepSentence(governing, required.amount_inr),
          })}
        </p>
      )}
      {item.authority_on_record_deviations && (
        <p data-testid="comparison-authority-on-record">
          {t("comparison.authority.onRecord", {
            authority: item.authority_on_record_deviations.label,
          })}
        </p>
      )}
      <Details title={t("approvingAuthority.how")}>
        <ol className="list-decimal space-y-1 pl-5">
          {required.steps.map((s) => (
            <li key={s.rule} className={cn(s.governs && "font-medium text-foreground")}>
              {stepSentence(s, required.amount_inr)}
              {s.governs && <> · {t("approvingAuthority.governs")}</>}
            </li>
          ))}
        </ol>
      </Details>
    </div>
  );
}

function Adjudicate({ caseId, item }: { caseId: string; item: ComparisonItem }) {
  const adjudicate = useAdjudicate(caseId);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [reason, setReason] = useState("");
  const [changing, setChanging] = useState(false);
  const decided = item.adjudication;
  if (!item.adjudicable) return null;
  const current = decided && !decided.stale;
  const save = () => {
    if (!verdict) return;
    adjudicate.mutate(
      { area: item.area, key: item.key, body: { verdict, reason: reason.trim() } },
      {
        onSuccess: () => {
          setVerdict(null);
          setReason("");
          setChanging(false);
          toast.success(t("review.recorded"));
        },
      },
    );
  };
  return (
    <div className="space-y-1.5" data-testid="comparison-adjudication">
      {decided && (
        <p
          className="text-[12px] text-foreground"
          data-testid="adjudication-decided"
          data-verdict={decided.verdict}
        >
          {t("comparison.decided", {
            verdict: t(
              decided.verdict === "valid" ? "adjudication.valid" : "adjudication.notValid",
            ),
            name: decided.decided_by_name,
            date: formatDate(decided.decided_at),
          })}
          {decided.reason && <span className="text-muted-foreground"> · {decided.reason}</span>}
        </p>
      )}
      {decided?.stale && (
        <p className="text-[12px] text-flag-foreground" data-testid="adjudication-stale">
          {t("comparison.stale")}
        </p>
      )}
      {current && !changing ? (
        <button
          type="button"
          onClick={() => setChanging(true)}
          className="text-[11.5px] font-medium text-primary hover:underline"
          data-testid="adjudication-change"
        >
          {t("comparison.change")}
        </button>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            aria-pressed={verdict === "valid"}
            onClick={() => setVerdict("valid")}
            className={cn(
              decisionButton,
              verdict === "valid"
                ? "border-positive bg-positive-soft text-positive"
                : "border-positive/40 bg-surface text-positive hover:bg-positive-soft",
            )}
            data-testid="adjudicate-valid"
          >
            {t("adjudication.valid")}
          </button>
          <button
            type="button"
            aria-pressed={verdict === "not_valid"}
            onClick={() => setVerdict("not_valid")}
            className={cn(
              decisionButton,
              verdict === "not_valid"
                ? "border-foreground/40 bg-muted text-foreground"
                : "border-border bg-surface text-foreground hover:bg-muted",
            )}
            data-testid="adjudicate-not-valid"
          >
            {t("adjudication.notValid")}
          </button>
          {verdict && (
            <>
              <input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={t("comparison.reason")}
                aria-label={t("comparison.reason")}
                className="h-7 min-w-0 flex-1 basis-48 rounded border border-border bg-surface px-2 text-[12px] outline-none focus:border-primary/60"
                data-testid="adjudication-reason"
                autoFocus
              />
              <button
                type="button"
                disabled={adjudicate.isPending || reason.trim().length < 3}
                onClick={save}
                title={reason.trim().length < 3 ? t("comparison.reasonRequired") : undefined}
                className="h-7 rounded bg-primary px-2.5 text-[11.5px] font-medium text-primary-foreground disabled:opacity-40"
                data-testid="adjudication-save"
              >
                {t("comparison.save")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setVerdict(null);
                  setReason("");
                  setChanging(false);
                }}
                className="text-[11.5px] text-muted-foreground hover:underline"
              >
                {t("comparison.cancel")}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ItemRow({
  caseId,
  item,
  categoryLabel,
}: {
  caseId: string;
  item: ComparisonItem;
  categoryLabel: (key: string) => string;
}) {
  return (
    <li
      className="space-y-2 px-4 py-3"
      data-testid="comparison-item"
      data-area={item.area}
      data-key={item.key}
      data-status={item.status}
    >
      <div className={cn("space-y-2 text-[12.5px] sm:space-y-0", GRID)}>
        <div className="min-w-0">
          <p className="font-medium text-foreground">{item.label}</p>
          <p className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-muted-foreground">
            {item.area === "deviations" && <span className="tabular">{item.key}</span>}
            {item.norm && item.norm.outcome === "deviation" && (
              <Chip tone="muted">{item.norm.category_label}</Chip>
            )}
          </p>
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-muted-foreground sm:hidden">
            {t("comparison.column.creditiq")}
          </p>
          <CreditIqCell caseId={caseId} item={item} />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] text-muted-foreground sm:hidden">
            {t("comparison.column.record")}
          </p>
          <RecordCell item={item} />
        </div>
        <div>
          <Chip tone={STATUS_TONE[item.status]}>
            <span data-testid="comparison-status">{t(`comparisonStatus.${item.status}`)}</span>
          </Chip>
        </div>
      </div>
      {(item.notes ?? []).length > 0 && (
        <ul className="space-y-0.5 text-[12px] text-muted-foreground">
          {(item.notes ?? []).map((kind) => (
            <li key={kind} data-testid="comparison-note" data-note={kind}>
              {noteText(item, kind, categoryLabel)}
            </li>
          ))}
        </ul>
      )}
      {item.area === "approving_authority" && <AuthorityDetail item={item} />}
      <Adjudicate caseId={caseId} item={item} />
    </li>
  );
}

function ScoreLine({ score }: { score: AreaScore }) {
  if (score.area === "approving_authority")
    return (
      <span data-testid="area-score" data-area={score.area}>
        {t("comparison.score.authority", {
          valid: score.valid,
          total: score.recorded_total,
          pending: score.pending,
        })}
      </span>
    );
  return (
    <span data-testid="area-score" data-area={score.area}>
      {t("comparison.score.found", { found: score.found_in_record, total: score.recorded_total })}
      {" · "}
      {t("comparison.score.upheld", {
        valid: score.valid,
        total: score.flagged_total,
        pending: score.pending,
      })}
    </span>
  );
}

function ComparisonView({ caseId, comparison }: { caseId: string; comparison: CaseComparison }) {
  const [filter, setFilter] = useState<ComparisonFilter>("all");
  const policy = usePolicyConfig();
  const record = comparison.record;
  const categoryLabel = (key: string) =>
    policy.data?.deviation_categories?.find((c) => c.key === key)?.label ?? key.replace(/_/g, " ");
  if (!record) {
    return (
      <div className="space-y-3">
        <p
          className="rounded border border-dashed border-border bg-surface px-4 py-6 text-center text-[13px] text-muted-foreground"
          data-testid="comparison-waiting"
        >
          {t("comparison.record.waiting")}
        </p>
        <p className="text-[12px] text-muted-foreground" data-testid="comparison-other-areas">
          {t("comparison.otherAreas")}
        </p>
      </div>
    );
  }
  const items = comparison.items;
  const authority = items.find((i) => i.area === "approving_authority");
  const count = (f: ComparisonFilter) => items.filter((i) => matches(i, f)).length;
  return (
    <div className="space-y-4">
      <RecordBar caseId={caseId} record={record} />
      <div className="space-y-1" data-testid="comparison-header">
        <p className="text-[14px] font-semibold text-foreground" data-testid="comparison-counts">
          {t("comparison.countsDeviations", {
            agree: comparison.counts.agree,
            differ: comparison.counts.differ,
            new: comparison.counts.new,
            missed: comparison.counts.missed,
          })}
        </p>
        <p className="text-[12px] text-muted-foreground">{t("comparison.overlayNote")}</p>
        {comparison.provisional_norms && (
          <p
            className="text-[12px] text-flag-foreground"
            data-testid="comparison-provisional-norms"
          >
            {t("comparison.provisionalNorms")}
          </p>
        )}
        {authority && !authority.scored && (
          <p className="text-[12px] text-flag-foreground" data-testid="comparison-not-scored">
            {t("comparison.notScored")}
          </p>
        )}
      </div>
      <div className="flex flex-wrap gap-1.5" role="group">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
            data-testid={`comparison-filter-${f}`}
            className={cn(
              "rounded border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
              filter === f
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-surface text-muted-foreground hover:bg-muted",
            )}
          >
            {t(`comparison.filter.${f}`, { n: count(f) })}
          </button>
        ))}
      </div>
      {AREAS.map((area: ComparisonArea) => {
        const all = items.filter((i) => i.area === area);
        if (all.length === 0) return null;
        const shown = all.filter((i) => matches(i, filter));
        const score = comparison.scores.find((s) => s.area === area);
        return (
          <Panel
            key={area}
            title={t(`comparison.area.${area}`)}
            subtitle={score ? <ScoreLine score={score} /> : undefined}
            testId={`comparison-area-${area}`}
          >
            <div
              className={cn(
                "hidden border-b border-border px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground",
                GRID,
              )}
            >
              <span>{t("comparison.column.item")}</span>
              <span>{t("comparison.column.creditiq")}</span>
              <span>{t("comparison.column.record")}</span>
              <span>{t("comparison.column.status")}</span>
            </div>
            <ul className="divide-y divide-border">
              {shown.map((item) => (
                <ItemRow key={item.key} caseId={caseId} item={item} categoryLabel={categoryLabel} />
              ))}
            </ul>
          </Panel>
        );
      })}
      <p className="text-[12px] text-muted-foreground" data-testid="comparison-other-areas">
        {t("comparison.otherAreas")}
      </p>
    </div>
  );
}

export function ComparisonPanel({ caseId }: { caseId: string }) {
  const comparison = useComparison(caseId);
  return (
    <QueryView query={comparison}>
      {(c) => <ComparisonView caseId={caseId} comparison={c} />}
    </QueryView>
  );
}
