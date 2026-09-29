import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowUpRight, FileSearch, Plus } from "lucide-react";
import type { CaseSummary, ReviewItem } from "@/api/types";
import { useCases } from "@/domain/cases";
import { useReviewQueue } from "@/domain/review";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { CasesTable } from "@/components/cases/CasesTable";
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
  component: Workbench,
});

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
      className="group flex min-w-[9.5rem] flex-1 items-start gap-3 rounded border border-border bg-surface px-4 py-3 transition-colors hover:border-primary/40"
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

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 px-4 py-5 sm:px-6">
      <section className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1 sm:min-w-[16rem]">
          <p className="field-label">{t("tenant.bank.unit")}</p>
          <h1 className="text-[20px] font-semibold tracking-tight">
            {t("page.home.greeting", { name: firstName })}
          </h1>
          <p className="mt-0.5 text-[13px] text-muted-foreground">
            {session ? `${session.user.roleLabel} · ${session.user.branch}` : ""}
          </p>
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:flex-1">
          <Counter
            testId="counter-in-progress"
            value={cases.data ? inProgress.length : "…"}
            label={t("page.home.counter.inProgress")}
            sub={t("page.home.counter.inProgressSub", { n: borrowers })}
            to="/appraisals"
          />
          <Counter
            testId="counter-review"
            value={openItems ?? "…"}
            label={t("page.home.counter.review")}
            sub={t("page.home.counter.reviewSub")}
            to={canReview ? "/exceptions" : "/appraisals"}
            tone={openItems ? "flag" : undefined}
          />
        </div>
        {canCreate && (
          <Link
            to="/appraisals/new"
            className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> {t("nav.newApplication")}
          </Link>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)]">
        <section className="min-w-0 rounded border border-border bg-surface">
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
            <div className="min-w-0">
              <h2 className="text-[14px] font-semibold">{t("page.home.inFlight")}</h2>
              <p className="text-[11.5px] text-muted-foreground">{t("page.home.inFlightSub")}</p>
            </div>
            <Link
              to="/appraisals"
              className="shrink-0 text-[12px] font-medium text-primary hover:underline"
            >
              {t("action.viewAll")}
            </Link>
          </header>
          <div className={cn(cases.data && inProgress.length > 0 ? "" : "p-4")}>
            <QueryView
              query={cases}
              loading={<LoadingBlock rows={4} className="border-0 p-0" />}
              isEmpty={() => inProgress.length === 0}
              empty={{
                title: t("state.noCases.title"),
                description: t("state.noCases.description"),
                action: canCreate ? (
                  <Link
                    to="/appraisals/new"
                    className="text-[12.5px] font-medium text-primary hover:underline"
                  >
                    {t("nav.newApplication")}
                  </Link>
                ) : undefined,
              }}
            >
              {() => <CasesTable cases={inProgress} />}
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
    </div>
  );
}

const MAX_ATTENTION = 8;

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
            <Link to="/exceptions" className="text-[12px] font-medium text-primary hover:underline">
              {t("nav.exceptionQueue")}
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
                to="/docready/$caseId/checklist"
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
    </section>
  );
}
