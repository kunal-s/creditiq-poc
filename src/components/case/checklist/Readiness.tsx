import { AlertTriangle, Check, Clock, Minus, OctagonX, X, type LucideIcon } from "lucide-react";
import type { ChecklistItemState, ChecklistStatus } from "@/api/types";
import { t } from "@/config/terminology";
import { bySection, readinessBreakdown } from "@/domain/checklist";
import { Chip } from "@/components/common/Panel";
import { cn } from "@/lib/utils";
import { TONE } from "./status";

// Document readiness, said one way on every screen: how many of the requirements are satisfied,
// the rest as not satisfied broken down by why, and every document named under its section with
// a tick or a cross. The Overview shows them as two tabs; the Document readiness step's list
// counts the same requirements with the same words (its filters), so the two always agree.

/** The glyph and colours of a status: a tick, a cross, an exclamation, a clock, a dash, each on a
 * pale tint of its colour. The word goes with it in a chip of the same tint (as on the Document
 * readiness step), so colour is never the only signal. */
const MARK: Record<ChecklistStatus, { icon: LucideIcon; dot: string }> = {
  satisfied: {
    icon: Check,
    dot: "bg-positive-soft text-positive ring-1 ring-positive/45",
  },
  missing: {
    icon: X,
    dot: "bg-critical-soft text-destructive ring-1 ring-destructive/35",
  },
  insufficient: {
    icon: AlertTriangle,
    dot: "bg-flag-soft text-flag-foreground ring-1 ring-flag/60",
  },
  in_review: { icon: Clock, dot: "bg-info-soft text-info ring-1 ring-info/50" },
  waived: {
    icon: Minus,
    dot: "bg-muted text-muted-foreground ring-1 ring-border",
  },
};

const BAR: Record<"satisfied" | "in_review" | "insufficient" | "missing", string> = {
  satisfied: "bg-positive",
  in_review: "bg-info/35",
  insufficient: "bg-flag/40",
  missing: "bg-destructive/30",
};

export function StatusMark({ status, className }: { status: ChecklistStatus; className?: string }) {
  const { icon: Icon, dot } = MARK[status];
  return (
    <span
      aria-hidden
      className={cn("grid size-[18px] shrink-0 place-items-center rounded-full", dot, className)}
    >
      <Icon className="size-3" strokeWidth={3} />
    </span>
  );
}

/** The count of satisfied requirements against all of them, then the two halves, then why the
 * not-satisfied ones are not: figures to read, each part of the one before it. */
export function DocumentReadiness({ items }: { items: ChecklistItemState[] }) {
  const b = readinessBreakdown(items);
  const parts = [
    { key: "missing" as const, n: b.missing },
    { key: "insufficient" as const, n: b.insufficient },
    { key: "in_review" as const, n: b.inReview },
  ];
  const segments = [
    { key: "satisfied" as const, n: b.satisfied },
    { key: "in_review" as const, n: b.inReview },
    { key: "insufficient" as const, n: b.insufficient },
    { key: "missing" as const, n: b.missing },
  ].filter((s) => s.n > 0);

  return (
    <div className="min-w-0" data-testid="document-readiness">
      {/* The headline: satisfied of all. */}
      <p className="flex flex-wrap items-baseline gap-x-2">
        <span
          className="tabular text-[34px] font-semibold leading-none tracking-tight text-foreground"
          data-testid="document-readiness-total"
        >
          {t("journey.readiness.ofTotal", { n: b.satisfied, total: b.total })}
        </span>
        <span className="text-[13px] text-muted-foreground">
          {t("journey.readiness.satisfiedOf")}
        </span>
      </p>

      {/* Every requirement once: satisfied first, then the not satisfied by why. */}
      <div
        aria-hidden
        className="mt-2.5 flex h-2 gap-0.5 overflow-hidden rounded-full bg-muted"
        data-testid="document-readiness-bar"
      >
        {segments.map((s) => (
          <span
            key={s.key}
            className={cn("h-full first:rounded-l-full last:rounded-r-full", BAR[s.key])}
            style={{ flexGrow: s.n, flexBasis: 0 }}
          />
        ))}
      </div>

      {/* The two halves, which always add up to the whole. */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Half
          label={t("journey.readiness.satisfied")}
          n={b.satisfied}
          // Nothing satisfied yet is not a success.
          tone={b.satisfied > 0 ? "text-positive" : "text-muted-foreground"}
          note={b.waived > 0 ? t("journey.readiness.includesWaived", { n: b.waived }) : undefined}
          testId="document-readiness-satisfied"
          mark="satisfied"
        />
        <Half
          label={t("journey.readiness.notSatisfied")}
          n={b.notSatisfied}
          tone={b.notSatisfied > 0 ? "text-critical-text" : "text-muted-foreground"}
          testId="document-readiness-not_satisfied"
          mark={b.notSatisfied > 0 ? "missing" : "satisfied"}
        />
      </div>

      {/* Why the not-satisfied are not: parts of the second half, not counts beside it. */}
      {b.notSatisfied > 0 ? (
        <div
          className="mt-2.5 rounded-md bg-surface-muted/70 px-3 py-2"
          data-testid="document-readiness-breakdown"
        >
          <p className="text-[11.5px] text-muted-foreground">
            {t("journey.readiness.breakdown", { n: b.notSatisfied })}
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
            {parts.map((p) => (
              <li
                key={p.key}
                className={cn(
                  "inline-flex items-center gap-1.5 py-0.5 text-[12.5px]",
                  p.n === 0 && "text-muted-foreground",
                )}
                data-testid={`document-readiness-${p.key}`}
              >
                <StatusMark status={p.key} className="size-4" />
                <span>{t(`docStatus.${p.key}`)}</span>
                <span className="tabular font-semibold text-foreground">{p.n}</span>
              </li>
            ))}
          </ul>
          {b.blocking > 0 && (
            <p
              className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-critical-text"
              data-testid="document-readiness-blocking"
            >
              <OctagonX className="size-3.5" aria-hidden />
              {t("journey.readiness.blockingNote", { n: b.blocking })}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-2.5 text-[12px] font-medium text-positive">
          {t("journey.readiness.noneNotSatisfied")}
        </p>
      )}
    </div>
  );
}

function Half({
  label,
  n,
  tone,
  note,
  testId,
  mark,
}: {
  label: string;
  n: number;
  tone: string;
  note?: string | undefined;
  testId: string;
  mark: ChecklistStatus;
}) {
  return (
    <div
      className="flex min-w-0 items-center gap-2.5 rounded-md border border-border bg-surface px-3 py-2"
      data-testid={testId}
    >
      <StatusMark status={mark} />
      <span className="min-w-0">
        <span className={cn("tabular block text-[22px] font-semibold leading-none", tone)}>
          {n}
        </span>
        <span className="mt-1 block text-[12px] font-medium text-foreground">{label}</span>
        {note && <span className="block text-[11px] text-muted-foreground">{note}</span>}
      </span>
    </div>
  );
}

/** Every document under its section, with a tick, a cross or a mark for where it stands and the
 * word for it; one that stops credit review says so. */
export function DocumentStatusList({
  items,
  sections,
}: {
  items: ChecklistItemState[];
  sections: string[] | undefined;
}) {
  return (
    <div className="min-w-0 space-y-3" data-testid="document-status">
      {bySection(items, sections).map(({ section, items: own }) => (
        <section key={section} data-testid="document-status-section" data-section={section}>
          <h4 className="text-[12px] font-semibold text-foreground">{section}</h4>
          <ul className="mt-1 divide-y divide-border/70 rounded-md border border-border bg-surface">
            {own.map((item) => {
              const open = item.status !== "satisfied" && item.status !== "waived";
              return (
                <li
                  key={item.item_id}
                  className="flex items-start gap-2.5 px-2.5 py-1.5"
                  data-testid="document-status-item"
                  data-item={item.item_id}
                  data-status={item.status}
                >
                  <StatusMark status={item.status} className="mt-px" />
                  <span className="min-w-0 flex-1">
                    <span className="text-[13px] leading-[18px] text-foreground">{item.name}</span>
                    {item.blocking && open && (
                      <span className="mt-0.5 block text-[11px] text-critical-text">
                        {t("journey.status.blocks")}
                      </span>
                    )}
                  </span>
                  <Chip tone={TONE[item.status]} className="shrink-0">
                    {t(`docStatus.${item.status}`)}
                  </Chip>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
