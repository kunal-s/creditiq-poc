import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import { AlertTriangle, ArrowUpRight, FileSearch, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import type { CaseSummary, ReviewItem, Stage } from "@/api/types";
import { stageLabel, useCases } from "@/domain/cases";
import { readyForCredit, useChecklists } from "@/domain/checklist";
import { useReviewQueue } from "@/domain/review";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { CasesTable } from "@/components/cases/CasesTable";
import { homePath } from "@/components/shell/nav";
import { ErrorState, LoadingBlock, QueryView } from "@/components/common/States";
import { reviewItemPath } from "@/components/review/reviewLinks";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: t("tenant.product.documentTitleTemplate") },
      { name: "description", content: t("tenant.product.metaDescription") },
    ],
  }),
  component: Home,
});

/** A role without the workbench (the Administrator) starts on its own screen instead. */
function Home() {
  const session = useSession();
  if (session && !session.user.navGroups.includes("workbench")) {
    return <Navigate to={homePath(session.user)} replace />;
  }
  return <Workbench />;
}

function Counter({
  value,
  label,
  sub,
  to,
  tone,
  testId,
}: {
  value: number | string;
  label: string;
  sub: string;
  to: string;
  tone?: "flag" | undefined;
  testId: string;
}) {
  return (
    <Link
      to={to}
      data-testid={testId}
      className="group flex min-w-0 items-start gap-3 rounded border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/40 sm:w-44"
    >
      <span
        className={cn(
          "text-[28px] font-semibold leading-none tabular",
          tone === "flag" ? "text-flag-foreground" : "text-foreground",
        )}
        data-testid={`${testId}-value`}
      >
        {value}
      </span>
      <span className="min-w-0">
        <span className="block text-[12.5px] font-medium text-foreground">{label}</span>
        <span className="block text-[11.5px] text-muted-foreground">{sub}</span>
      </span>
      <ArrowUpRight className="ml-auto h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
    </Link>
  );
}

/** The part of the day by the user's own clock, for the greeting only. */
function dayPart(): "morning" | "afternoon" | "evening" {
  const hour = new Date().getHours();
  return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
}

function Workbench() {
  const session = useSession();
  const cases = useCases();
  const canReview = session?.user.permissions.includes("review.read") ?? false;
  const canCreate = session?.user.permissions.includes("case.create") ?? false;
  const review = useReviewQueue();
  const list = cases.data ?? [];
  const inProgress = list.filter((c) => c.stage !== "Completed");
  const borrowers = new Set(inProgress.map((c) => c.borrower)).size;
  const openItems = canReview
    ? review.data?.length
    : cases.data?.reduce((n, c) => n + c.open_review_items, 0);
  const firstName = session?.user.name.split(" ")[0] ?? "";
  const [filter, setFilter] = useState<Filter>(ALL);
  const checklists = useChecklists(inProgress.map((c) => c.id));
  const ready = checklists.filter((q) => q.data && readyForCredit(q.data)).length;
  const stages = [...new Set(list.map((c) => c.stage))];
  const shown = list.filter(
    (c) =>
      (filter.stage === "" ? c.stage !== "Completed" : c.stage === filter.stage) &&
      (!filter.mine || c.rm === session?.user.name) &&
      (!filter.review || c.open_review_items > 0),
  );

  return (
    <div className="space-y-5 px-4 py-5 sm:px-6">
      <section className="flex flex-wrap items-center gap-4">
        {/* As the original: a greeting by the hour, today and where the desk stands. */}
        <div className="min-w-0 flex-1 sm:min-w-[16rem]">
          <h1 className="text-[20px] font-semibold tracking-tight">
            {t(`page.home.greeting.${dayPart()}`, { name: firstName })}
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {[
              new Date().toLocaleDateString("en-IN", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              }),
              session?.user.branch,
              openItems ? t("page.home.waiting", { n: openItems }) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {/* The counts in a row between the greeting and the action, as the original design. */}
        <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
          <Counter
            testId="counter-in-progress"
            value={cases.data ? inProgress.length : "…"}
            label={t("page.home.counter.inProgress")}
            sub={t("page.home.counter.inProgressSub", { n: borrowers })}
            to="/"
          />
          <Counter
            testId="counter-review"
            value={openItems ?? "…"}
            label={t("page.home.counter.review")}
            sub={t("page.home.counter.reviewSub")}
            to={canReview ? "/review" : "/"}
            tone={openItems ? "flag" : undefined}
          />
          <Counter
            testId="counter-ready"
            value={cases.data ? ready : "…"}
            label={t("readinessGates.readyForCredit")}
            sub={t("console.kpi.readyNote")}
            to="/"
          />
        </div>
        {canCreate && (
          <Link
            to="/appraisals/new"
            className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> {t("nav.newCase")}
          </Link>
        )}
      </section>

      <div className="grid gap-5 @min-[65rem]/main:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
        <section className="min-w-0 rounded border border-border bg-surface">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
            {/* On a phone the filters go below the title, in one row. */}
            <div className="min-w-0 flex-1 basis-56">
              <h2 className="text-[14px] font-semibold">{t("page.home.inFlight")}</h2>
              <p className="text-[11.5px] text-muted-foreground">{t("page.home.inFlightSub")}</p>
            </div>
            <Link
              to="/appraisals"
              className="order-last text-[12px] font-medium text-primary hover:underline sm:order-none"
            >
              {t("page.home.viewAll")}
            </Link>
            <CaseFilters
              value={filter}
              onChange={setFilter}
              stages={stages}
              showOwner={session?.user.permissions.includes("case.read.all") ?? false}
            />
          </header>
          <div className={cn(cases.data && shown.length > 0 ? "" : "p-4")}>
            <QueryView
              query={cases}
              loading={<LoadingBlock rows={4} className="border-0 p-0" />}
              isEmpty={() => shown.length === 0}
              empty={{
                title: t("state.noCases.title"),
                description: t("state.noCases.description"),
                action: canCreate ? (
                  <Link
                    to="/appraisals/new"
                    className="text-[12.5px] font-medium text-primary hover:underline"
                  >
                    {t("nav.newCase")}
                  </Link>
                ) : undefined,
              }}
            >
              {() => <CasesTable cases={shown} />}
            </QueryView>
          </div>
        </section>

        <NeedsAttention
          canReview={canReview}
          cases={list}
          review={review.data}
          loading={canReview ? review.isLoading : cases.isLoading}
          error={canReview ? review.error : null}
          onRetry={() => void review.refetch()}
        />
      </div>
      {cases.data && list.length > 0 && (
        <Portfolio
          stages={stages}
          list={list}
          ready={ready}
          blocking={checklists.reduce((n, q) => n + (q.data?.blocking_open ?? 0), 0)}
        />
      )}
    </div>
  );
}

/** The book at a glance, as the original design: what is open, ready and blocked, and how the
 * appraisals spread across the stages. */
function Portfolio({
  stages,
  list,
  ready,
  blocking,
}: {
  stages: Stage[];
  list: CaseSummary[];
  ready: number;
  blocking: number;
}) {
  const byStage = stages.map((st) => ({ st, n: list.filter((c) => c.stage === st).length }));
  const max = Math.max(1, ...byStage.map((b) => b.n));
  const open = list.filter((c) => c.stage !== "Completed").length;
  return (
    <section className="rounded border border-border bg-surface" data-testid="portfolio">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h2 className="text-[14px] font-semibold">{t("page.home.portfolio.title")}</h2>
        <Link to="/memos" className="text-[12px] font-medium text-primary hover:underline">
          {t("nav.memoLibrary")}
        </Link>
      </header>
      <div className="grid gap-x-6 gap-y-4 px-4 py-4 sm:grid-cols-2 lg:grid-cols-4">
        <Glance
          label={t("page.home.portfolio.open")}
          value={open}
          note={t("page.home.portfolio.openNote", { n: list.length })}
        />
        <Glance
          label={t("page.home.portfolio.ready")}
          value={ready}
          note={t("console.kpi.readyNote")}
        />
        <Glance
          label={t("page.home.portfolio.blocking")}
          value={blocking}
          note={t("page.home.portfolio.blockingNote")}
        />
        <div className="min-w-0">
          <p className="field-label">{t("page.home.portfolio.byStage")}</p>
          <ul
            className="mt-2 flex h-16 items-end gap-1.5"
            aria-label={t("page.home.portfolio.byStage")}
          >
            {byStage.map(({ st, n }) => (
              <li
                key={st}
                className="flex min-w-0 flex-1 flex-col items-center gap-0.5"
                title={`${stageLabel(st)} · ${n}`}
              >
                <span className="tabular text-[10.5px] text-muted-foreground">{n}</span>
                <span
                  className="w-full rounded-sm bg-primary/70"
                  style={{ height: `${(n / max) * 40 + 2}px` }}
                />
                <span className="w-full truncate text-center text-[9.5px] text-muted-foreground">
                  {stageLabel(st)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Glance({ label, value, note }: { label: string; value: number; note: string }) {
  return (
    <div className="min-w-0">
      <p className="field-label">{label}</p>
      <p className="tabular mt-1 text-[24px] font-semibold leading-none text-foreground">{value}</p>
      <p className="mt-1 text-[11.5px] text-muted-foreground">{note}</p>
    </div>
  );
}

type Filter = { stage: Stage | ""; mine: boolean; review: boolean };
const ALL: Filter = { stage: "", mine: false, review: false };

/** Stage, owner and open-review filters over the case list. */
function CaseFilters({
  value,
  onChange,
  stages,
  showOwner,
}: {
  value: Filter;
  onChange: (f: Filter) => void;
  stages: Stage[];
  showOwner: boolean;
}) {
  const toggle = "rounded border px-2 py-1 text-[11.5px] font-medium transition-colors";
  const on = "border-primary bg-primary text-primary-foreground";
  const off = "border-border bg-surface text-muted-foreground hover:bg-muted";
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="case-filters">
      <select
        aria-label={t("term.stage")}
        value={value.stage}
        onChange={(e) => onChange({ ...value, stage: e.target.value as Stage | "" })}
        className="h-7 rounded border border-border bg-surface px-1.5 text-[11.5px]"
      >
        <option value="">{t("page.home.filter.open")}</option>
        {stages.map((s) => (
          <option key={s} value={s}>
            {stageLabel(s)}
          </option>
        ))}
      </select>
      {showOwner && (
        <button
          type="button"
          aria-pressed={value.mine}
          onClick={() => onChange({ ...value, mine: !value.mine })}
          className={cn(toggle, value.mine ? on : off)}
        >
          {t("page.home.filter.mine")}
        </button>
      )}
      <button
        type="button"
        aria-pressed={value.review}
        onClick={() => onChange({ ...value, review: !value.review })}
        className={cn(toggle, value.review ? on : off)}
      >
        {t("page.home.filter.review")}
      </button>
    </div>
  );
}

/** As the original: the three most pressing, the rest in the queue. */
const MAX_ATTENTION = 3;

function NeedsAttention({
  canReview,
  cases,
  review,
  loading,
  error,
  onRetry,
}: {
  canReview: boolean;
  cases: CaseSummary[];
  review: ReviewItem[] | undefined;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const borrower = (id: string) => cases.find((c) => c.id === id)?.borrower ?? id;
  const flagged = cases.filter((c) => c.open_review_items > 0);
  const pressingCase = [...flagged].sort((a, b) => b.open_review_items - a.open_review_items)[0];
  const count = canReview ? (review?.length ?? 0) : flagged.length;

  return (
    <section
      className="min-w-0 rounded border border-border bg-surface"
      data-testid="needs-attention"
    >
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h2 className="text-[14px] font-semibold">{t("page.home.attention")}</h2>
        <div className="flex items-center gap-2">
          <span className="rounded bg-flag-soft px-1.5 py-0.5 text-[11px] font-medium text-flag-foreground">
            {t("page.home.attentionCount", { n: count })}
          </span>
          {canReview && (
            <Link to="/review" className="text-[12px] font-medium text-primary hover:underline">
              {t("nav.reviewQueue")}
            </Link>
          )}
        </div>
      </header>
      {error ? (
        <div className="p-4">
          <ErrorState error={error} compact onRetry={onRetry} />
        </div>
      ) : loading ? (
        <div className="p-4">
          <LoadingBlock rows={3} className="border-0 p-0" />
        </div>
      ) : count === 0 ? (
        <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
          {t("page.home.attentionEmpty")}
        </p>
      ) : canReview ? (
        <ul className="divide-y divide-border">
          {(review ?? []).slice(0, MAX_ATTENTION).map((item) => (
            <li key={item.id}>
              <Link
                to={reviewItemPath(item.kind, item.case_id)}
                className="flex gap-3 px-4 py-3 transition-colors hover:bg-surface-muted"
              >
                <span
                  className={cn(
                    "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded",
                    item.kind === "finding" || item.kind === "quality"
                      ? "bg-critical-soft text-critical"
                      : "bg-info-soft text-info",
                  )}
                >
                  {item.kind === "finding" || item.kind === "quality" ? (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  ) : (
                    <FileSearch className="h-3.5 w-3.5" />
                  )}
                </span>
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium text-foreground">
                    {t(`reviewKind.${item.kind}`)}
                  </span>
                  <span className="mt-0.5 block break-words text-[11.5px] leading-snug text-muted-foreground">
                    {item.summary}
                  </span>
                  <span className="mt-1 block text-[11px] text-muted-foreground">
                    {borrower(item.case_id)} · {item.case_id}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <ul className="divide-y divide-border">
          {flagged.slice(0, MAX_ATTENTION).map((c) => (
            <li key={c.id}>
              <Link
                to="/appraisals/$caseId/completeness"
                hash="checklist"
                params={{ caseId: c.id }}
                className="flex gap-3 px-4 py-3 transition-colors hover:bg-surface-muted"
              >
                <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded bg-info-soft text-info">
                  <FileSearch className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium text-foreground">
                    {c.borrower}
                  </span>
                  <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
                    {t("cases.reviewOpen", { n: c.open_review_items })} · {c.id}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {/* As the original: a note on the most pressing appraisal and what the copilot does there. */}
      {pressingCase && (
        <p className="flex gap-2 border-t border-border bg-surface-muted/60 px-4 py-3 text-[12px] leading-relaxed text-muted-foreground">
          <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
          <span>
            {t("page.home.note", {
              borrower: pressingCase.borrower,
              n: pressingCase.open_review_items,
            })}{" "}
            <Link
              to="/appraisals/$caseId"
              params={{ caseId: pressingCase.id }}
              className="font-medium text-primary hover:underline"
            >
              {t("page.home.noteOpen")}
            </Link>
          </span>
        </p>
      )}
    </section>
  );
}
