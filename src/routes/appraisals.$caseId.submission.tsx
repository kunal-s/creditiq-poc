import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, ArrowLeft, CheckCircle2, CircleDashed } from "lucide-react";
import type { ReactNode } from "react";
import { AssessmentStage } from "@/components/case/gate/AssessmentStage";
import { StepHeader } from "@/components/case/TabSection";
import { stepKicker } from "@/domain/steps";
import { Panel } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import { readyForCredit, useChecklist } from "@/domain/checklist";
import { useCrossVerification } from "@/domain/crossVerification";
import { useCam } from "@/domain/findings";
import { useApprovingAuthority } from "@/domain/policy";
import { cn } from "@/lib/utils";

// Submission, as the original design: what must hold before the memo leaves the analyst's desk,
// each read from the appraisal as it stands, and who it goes to. Nothing here submits: the memo
// goes on from the approving authority's own process.

export const Route = createFileRoute("/appraisals/$caseId/submission")({
  head: () => ({
    meta: [{ title: `${t("caseTab.submission")} — ${t("tenant.product.name")}` }],
  }),
  component: SubmissionTab,
});

const button =
  "inline-flex items-center gap-1.5 rounded border border-border bg-surface px-3 py-1.5 text-[12.5px] font-medium hover:bg-muted";

type Check = { key: string; met: boolean; advisory?: boolean; detail: string; link?: ReactNode };

function SubmissionTab() {
  const { caseId } = Route.useParams();
  return (
    <div className="pb-10">
      <StepHeader
        kicker={stepKicker(caseId, "submission")}
        title={t("page.submission.title")}
        purpose={t("page.submission.purpose")}
        actions={
          <>
            <Link to="/appraisals/$caseId/rating" params={{ caseId }} className={button}>
              <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> {t("caseTab.rating")}
            </Link>
            <Link to="/memos" className={button}>
              {t("nav.memoLibrary")}
            </Link>
          </>
        }
      />
      <AssessmentStage caseId={caseId}>
        <SubmissionBody caseId={caseId} />
      </AssessmentStage>
    </div>
  );
}

function SubmissionBody({ caseId }: { caseId: string }) {
  const board = useCrossVerification(caseId).data;
  const checklist = useChecklist(caseId).data;
  const cam = useCam(caseId).data;
  const authority = useApprovingAuthority(caseId).data;
  if (!board || !checklist || !cam) return null;

  const c = board.counts;
  const advisoryOpen = board.items.filter((i) => !i.adjudicated && !i.finding.blocking).length;
  const written =
    cam.recommendation.trim() !== "" ||
    (cam.recommendation_review?.state ?? "machine") !== "machine";
  const toBoard = (
    <Link
      to="/appraisals/$caseId/cross-verification"
      params={{ caseId }}
      className="text-[12px] font-medium text-primary hover:underline"
    >
      {t("page.submission.openBoard")} →
    </Link>
  );
  const checks: Check[] = [
    {
      key: "serious",
      met: c.blocking_open === 0,
      detail:
        c.blocking_open === 0
          ? t("page.submission.seriousDone")
          : t("page.submission.seriousOpen", { n: c.blocking_open }),
      link: c.blocking_open > 0 ? toBoard : undefined,
    },
    {
      key: "advisory",
      met: advisoryOpen === 0,
      advisory: true,
      detail:
        advisoryOpen === 0
          ? t("page.submission.advisoryDone")
          : t("page.submission.advisoryOpen", { n: advisoryOpen }),
      link: advisoryOpen > 0 ? toBoard : undefined,
    },
    {
      key: "readiness",
      met: readyForCredit(checklist),
      detail: readyForCredit(checklist)
        ? t("page.submission.readinessDone")
        : t("page.submission.readinessOpen", {
            score: Math.round(checklist.score_pct),
            gate: Math.round(checklist.gate_pct),
            n: checklist.blocking_open,
          }),
      link: (
        <Link
          to="/appraisals/$caseId/completeness"
          params={{ caseId }}
          hash="readiness"
          className="text-[12px] font-medium text-primary hover:underline"
        >
          {t("page.submission.openReadiness")} →
        </Link>
      ),
    },
    {
      key: "recommendation",
      met: written,
      detail: written
        ? t("page.submission.recommendationDone")
        : t("page.submission.recommendationOpen"),
      link: (
        <Link
          to="/appraisals/$caseId/rating"
          params={{ caseId }}
          className="text-[12px] font-medium text-primary hover:underline"
        >
          {t("page.submission.openRecommendation")} →
        </Link>
      ),
    },
  ];
  const blocking = checks.filter((k) => !k.met && !k.advisory);
  const edited = cam.sections.filter((s) => s.review?.state && s.review.state !== "machine").length;

  return (
    <div className="grid items-start gap-4 px-4 py-5 sm:px-6 @min-[60rem]/main:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <div className="min-w-0 space-y-4">
        <p
          className={cn(
            "flex items-start gap-2 rounded border px-4 py-3 text-[13px]",
            blocking.length > 0
              ? "border-destructive/30 bg-destructive/10 text-destructive"
              : "border-positive/30 bg-positive-soft text-positive",
          )}
          data-testid="submission-state"
          data-open={blocking.length === 0}
        >
          {blocking.length > 0 ? (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          )}
          {blocking.length > 0
            ? t("page.submission.closed", {
                n: blocking.length,
                items: blocking.map((k) => t(`page.submission.check.${k.key}`)).join("; "),
              })
            : t("page.submission.open")}
        </p>
        <Panel
          title={t("page.submission.checklist")}
          subtitle={t("page.submission.checklistSub")}
          testId="submission-checklist"
        >
          <ul className="divide-y divide-border">
            {checks.map((k) => (
              <li
                key={k.key}
                className="flex gap-3 px-4 py-3"
                data-testid="submission-check"
                data-met={k.met}
              >
                {k.met ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" aria-hidden />
                ) : k.advisory ? (
                  <CircleDashed
                    className="mt-0.5 h-4 w-4 shrink-0 text-flag-foreground"
                    aria-hidden
                  />
                ) : (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
                )}
                <div className="min-w-0 space-y-1">
                  <p
                    className={cn(
                      "text-[13px] font-medium",
                      k.met
                        ? "text-foreground"
                        : k.advisory
                          ? "text-flag-foreground"
                          : "text-destructive",
                    )}
                  >
                    {t(`page.submission.check.${k.key}`)}
                    {k.advisory && (
                      <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">
                        {t("page.submission.advisory")}
                      </span>
                    )}
                  </p>
                  <p className="text-[12px] text-muted-foreground">{k.detail}</p>
                  {k.link}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
      <div className="min-w-0 space-y-4">
        <Panel title={t("page.submission.routing")} testId="submission-routing">
          <div className="px-4 py-3 text-[12.5px]">
            {authority?.required ? (
              <>
                <p className="font-semibold text-foreground">{authority.required.label}</p>
                <p className="mt-0.5 text-muted-foreground">{t("page.submission.routingNote")}</p>
              </>
            ) : (
              <p className="text-muted-foreground">{t("page.submission.routingUnknown")}</p>
            )}
          </div>
        </Panel>
        <Panel title={t("page.submission.travels")} testId="submission-travels">
          <dl className="divide-y divide-border text-[12.5px]">
            <Row label={t("page.submission.memo")}>
              {t("page.submission.memoValue", {
                n: cam.sections.length,
                template: cam.template_name,
                edited,
              })}
            </Row>
            <Row label={t("page.submission.findings")}>
              {t("page.submission.findingsValue", { n: c.total, decided: c.adjudicated })}
            </Row>
            <Row label={t("page.submission.asOf")}>{cam.as_of}</Row>
          </dl>
        </Panel>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 px-4 py-2.5">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right text-foreground">{children}</dd>
    </div>
  );
}
