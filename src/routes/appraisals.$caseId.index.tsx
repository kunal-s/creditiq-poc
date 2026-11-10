import { createFileRoute, Link } from "@tanstack/react-router";
import type { CaseProgress } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { reviewItemPath } from "@/components/review/reviewLinks";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { DocumentChecklist } from "@/components/case/DocumentChecklist";
import { useCaseProgress } from "@/domain/progress";
import { useReviewQueue } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";

// The case Overview (FRD §6): where the case is, what needs a person next,
// and the counts behind each stage. It updates while processing runs.

export const Route = createFileRoute("/appraisals/$caseId/")({
  head: () => ({
    meta: [{ title: `${t("caseTab.overview")} — ${t("tenant.product.name")}` }],
  }),
  component: OverviewTab,
});

function OverviewTab() {
  const { caseId } = Route.useParams();
  const progress = useCaseProgress(caseId);
  // The case header names the case; the Overview needs no title of its own.
  return (
    <>
      <h1 className="sr-only">{t("page.overview.title")}</h1>
      <div className="px-4 py-5 sm:px-6">
        <QueryView query={progress}>
          {(p) => <CaseScreen caseId={caseId}>{() => <Overview progress={p} />}</CaseScreen>}
        </QueryView>
      </div>
    </>
  );
}

function Overview({ progress }: { progress: CaseProgress }) {
  const permissions = useSession()?.user.permissions ?? [];
  const canOpen = (key: CaseProgress["stages"][number]["key"]) =>
    permissions.includes(tabForStage(key).permission);

  return (
    <div className="space-y-4">
      {/* The readiness glance (verdict, score against the gate, what blocks it, the counts, what
          to do next and what to ask the customer), then what this appraisal needs, row by row. */}
      <DocumentChecklist
        caseId={progress.case_id}
        variant="overview"
        progress={progress}
        canOpen={canOpen}
      />

      <WaitingForDecision caseId={progress.case_id} />
    </div>
  );
}

const MAX_LIST = 6;

/** This appraisal's open review items, each linked to where it is decided. */
function WaitingForDecision({ caseId }: { caseId: string }) {
  const canReview = useCan("review.read");
  const review = useReviewQueue({ caseId });
  if (!canReview) return null;
  const items = (review.data ?? []).filter((i) => i.status === "open");
  return (
    <Panel
      title={t("page.overview.waiting")}
      subtitle={review.data ? t("page.overview.waitingCount", { n: items.length }) : undefined}
      testId="waiting-decision"
    >
      {items.length === 0 ? (
        <p className="px-4 py-4 text-[12.5px] text-muted-foreground">
          {review.data ? t("page.home.attentionEmpty") : t("state.loading")}
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {items.slice(0, MAX_LIST).map((item) => (
            <li key={item.id}>
              <Link
                to={reviewItemPath(item.kind, caseId)}
                className="block px-4 py-2 hover:bg-surface-muted"
              >
                <span className="block text-[12.5px] font-medium">
                  {t(`reviewKind.${item.kind}`)}
                </span>
                <span className="block break-words text-[11.5px] text-muted-foreground">
                  {item.summary}
                </span>
              </Link>
            </li>
          ))}
          {items.length > MAX_LIST && (
            <li className="px-4 py-2 text-[11.5px]">
              <Link to="/review" className="font-medium text-primary hover:underline">
                {t("page.overview.more", { n: items.length - MAX_LIST })}
              </Link>
            </li>
          )}
        </ul>
      )}
    </Panel>
  );
}
