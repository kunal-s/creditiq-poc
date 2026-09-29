import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import type { ReviewItem, ReviewKind } from "@/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { Chip, Kpi } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { DecisionDialog } from "@/components/review/DecisionDialog";
import { reviewItemPath } from "@/components/review/reviewLinks";
import { t } from "@/config/terminology";
import { formatDate, useCases } from "@/domain/cases";
import { formatValue, useFields } from "@/domain/extraction";
import { REVIEW_KINDS, useReviewQueue } from "@/domain/review";
import { useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/exceptions")({
  head: () => ({
    meta: [{ title: `${t("page.exceptions.title")} — ${t("tenant.product.name")}` }],
  }),
  component: ExceptionQueue,
});

function ExceptionQueue() {
  const session = useSession();
  const canDecide = session?.user.permissions.includes("review.decide") ?? false;
  const [kind, setKind] = useState<ReviewKind | "all">("all");
  const [caseFilter, setCaseFilter] = useState<string>("all");
  const [showDecided, setShowDecided] = useState(false);
  const [deciding, setDeciding] = useState<ReviewItem | null>(null);
  const queue = useReviewQueue({ includeDecided: showDecided });
  const cases = useCases();
  const borrower = (id: string) => cases.data?.find((c) => c.id === id)?.borrower ?? id;

  const all = queue.data ?? [];
  const open = all.filter((i) => i.status === "open");
  const rows = all
    .filter((i) => kind === "all" || i.kind === kind)
    .filter((i) => caseFilter === "all" || i.case_id === caseFilter)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const caseIds = Array.from(new Set(all.map((i) => i.case_id)));
  const oldest = open.reduce<string | null>(
    (min, i) => (min === null || i.created_at < min ? i.created_at : min),
    null,
  );

  return (
    <div>
      <PageHeader
        eyebrow={t("page.exceptions.eyebrow")}
        title={t("page.exceptions.title")}
        purpose={t("page.exceptions.purpose")}
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        {queue.isError ? (
          <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />
        ) : queue.isLoading || !queue.data ? (
          <LoadingBlock />
        ) : (
          <>
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi
                label={t("exceptions.kpi.open")}
                value={open.length}
                note={t("exceptions.kpi.openNote", { n: new Set(open.map((i) => i.case_id)).size })}
                testId="kpi-open-items"
              />
              <Kpi
                label={t("reviewKind.type")}
                value={open.filter((i) => i.kind === "type").length}
                note={t("exceptions.kpi.typeNote")}
              />
              <Kpi
                label={t("reviewKind.field")}
                value={open.filter((i) => i.kind === "field").length}
                note={t("exceptions.kpi.fieldNote")}
              />
              <Kpi
                label={t("exceptions.kpi.oldest")}
                value={oldest ? formatDate(oldest) : "—"}
                note={t("exceptions.kpi.oldestNote")}
              />
            </section>

            <section className="rounded border border-border bg-surface">
              <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
                <h2 className="text-[14px] font-semibold">{t("term.reviewQueue")}</h2>
                <div className="flex flex-wrap items-center gap-2">
                  <div
                    className="flex flex-wrap items-center gap-1 rounded border border-border p-0.5"
                    role="group"
                    aria-label={t("exceptions.kindFilter")}
                  >
                    {(["all", ...REVIEW_KINDS] as const).map((k) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => setKind(k)}
                        data-testid={`kind-${k}`}
                        className={cn(
                          "rounded px-2 py-1 text-[11.5px] font-medium",
                          kind === k
                            ? "bg-accent text-accent-foreground"
                            : "text-muted-foreground hover:bg-muted",
                        )}
                      >
                        {k === "all" ? t("exceptions.allKinds") : t(`reviewKind.${k}`)}
                      </button>
                    ))}
                  </div>
                  <select
                    value={caseFilter}
                    onChange={(e) => setCaseFilter(e.target.value)}
                    className="h-8 max-w-[14rem] rounded border border-border bg-surface px-2 text-[12px]"
                    aria-label={t("exceptions.caseFilter")}
                  >
                    <option value="all">{t("exceptions.allCases")}</option>
                    {caseIds.map((id) => (
                      <option key={id} value={id}>
                        {borrower(id)} · {id}
                      </option>
                    ))}
                  </select>
                  <label className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={showDecided}
                      onChange={(e) => setShowDecided(e.target.checked)}
                      className="h-3.5 w-3.5 accent-[var(--primary)]"
                    />
                    {t("exceptions.showDecided")}
                  </label>
                </div>
              </header>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[880px] text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border bg-surface-muted text-left">
                      <th className="px-4 py-2 font-medium text-muted-foreground">
                        {t("exceptions.col.kind")}
                      </th>
                      <th className="px-3 py-2 font-medium text-muted-foreground">
                        {t("exceptions.col.item")}
                      </th>
                      <th className="px-3 py-2 font-medium text-muted-foreground">
                        {t("exceptions.col.raised")}
                      </th>
                      <th className="px-3 py-2 font-medium text-muted-foreground">
                        {t("exceptions.col.decision")}
                      </th>
                      <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                        {t("exceptions.col.action")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rows.map((item) => (
                      <tr
                        key={item.id}
                        className="align-top"
                        data-testid="review-row"
                        data-kind={item.kind}
                        data-status={item.status}
                      >
                        <td className="px-4 py-2.5">
                          <Chip
                            tone={
                              item.kind === "quality" || item.kind === "finding"
                                ? "critical"
                                : "info"
                            }
                          >
                            {t(`reviewKind.${item.kind}`)}
                          </Chip>
                        </td>
                        <td className="px-3 py-2.5">
                          <Link
                            to={reviewItemPath(item.kind, item.case_id)}
                            className="text-[13px] font-medium text-foreground hover:text-primary hover:underline"
                          >
                            {item.summary}
                          </Link>
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            {borrower(item.case_id)} · {item.case_id}
                          </p>
                        </td>
                        <td className="px-3 py-2.5 tabular text-muted-foreground">
                          {formatDate(item.created_at)}
                          {item.maker && <span className="block text-[11px]">{item.maker}</span>}
                        </td>
                        <td className="px-3 py-2.5">
                          {item.status === "decided" && item.decision ? (
                            <Decided item={item} />
                          ) : (
                            <span className="text-[11.5px] text-muted-foreground">
                              {t("exceptions.open")}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {item.status === "open" && canDecide ? (
                            <button
                              type="button"
                              onClick={() => setDeciding(item)}
                              data-testid="decide"
                              className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2.5 py-1.5 text-[12px] font-medium hover:bg-muted"
                            >
                              {t("exceptions.decide")} <ArrowUpRight className="h-3 w-3" />
                            </button>
                          ) : (
                            <Link
                              to={reviewItemPath(item.kind, item.case_id)}
                              className="inline-flex items-center gap-1 rounded border border-border bg-surface px-2.5 py-1.5 text-[12px] font-medium hover:bg-muted"
                            >
                              {t("exceptions.view")} <ArrowUpRight className="h-3 w-3" />
                            </Link>
                          )}
                        </td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr>
                        <td
                          colSpan={5}
                          className="px-4 py-8 text-center text-[12.5px] text-muted-foreground"
                        >
                          {t("exceptions.none")}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
      {deciding && (
        <DecisionFor
          item={deciding}
          borrower={borrower(deciding.case_id)}
          onClose={() => setDeciding(null)}
        />
      )}
    </div>
  );
}

function DecisionFor({
  item,
  borrower,
  onClose,
}: {
  item: ReviewItem;
  borrower: string;
  onClose: () => void;
}) {
  const fields = useFields(item.case_id);
  const field = item.kind === "field" ? fields.data?.find((f) => f.id === item.ref) : undefined;
  return <DecisionDialog item={item} borrower={borrower} field={field} onClose={onClose} />;
}

/** A decided item: the decision, its reason, and after a correction both values (F-17.5). */
function Decided({ item }: { item: ReviewItem }) {
  const fields = useFields(item.case_id);
  const field =
    item.kind === "field" && item.decision === "correct"
      ? fields.data?.find((f) => f.id === item.ref)
      : undefined;
  return (
    <div className="space-y-0.5 text-[11.5px]" data-testid="decided">
      <Chip tone="positive">{t(`reviewDecision.${item.decision!}`)}</Chip>
      {field && (
        <p className="text-foreground" data-testid="both-values">
          {t("review.bothValues", {
            system: formatValue(field.value),
            decided: formatValue(field.corrected_value ?? null),
          })}
        </p>
      )}
      {item.reason && <p className="text-muted-foreground">{item.reason}</p>}
      {item.decided_by && <p className="text-muted-foreground">{item.decided_by}</p>}
    </div>
  );
}
