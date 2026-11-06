import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardCopy,
  Copy,
  CopyCheck,
  Mail,
  ShieldCheck,
  Upload,
} from "lucide-react";
import type { CaseProgress, QueryItem } from "@/api/types";
import { StatusMark } from "@/components/case/StageProgress";
import { caseTabPath, tabForStage } from "@/components/shell/nav";
import { t } from "@/config/terminology";
import { useCase } from "@/domain/cases";
import { useQueryList } from "@/domain/checklist";
import { nextStage, stageDetail } from "@/domain/progress";
import { numbered, QUERY_GROUPS, queryListEmail, queryListText } from "@/domain/queries";
import { cn } from "@/lib/utils";
import { CopyLabel } from "./CopyLabel";
import { CountList } from "./CountList";
import { useCopy } from "./useCopy";

// The rail under the readiness glance on the Overview: what to do next, and what to ask the
// customer, side by side; the requests themselves open under it.

type StageKey = CaseProgress["stages"][number]["key"];
export type CanOpen = (key: StageKey) => boolean;

export function GlanceRail({
  caseId,
  progress,
  canOpen,
}: {
  caseId: string;
  progress: CaseProgress | undefined;
  canOpen: CanOpen | undefined;
}) {
  const [requests, setRequests] = useState(false);
  const queries = useQueryList(caseId);
  const open = (queries.data ?? []).filter((q) => !q.resolved);
  return (
    <>
      {/* One cell above the other while the card is one column (side by side, each would
          wrap to more lines than the two take stacked); beside each other once the card has
          two columns, the divider lined up with the one between them. */}
      <div className="grid divide-y divide-border border-t border-border bg-surface-muted/50 @min-[60rem]/glance:grid-cols-[calc((100%_-_72px)_/_2.08_+_52px)_minmax(0,1fr)] @min-[60rem]/glance:divide-x @min-[60rem]/glance:divide-y-0">
        {progress ? <NextCell progress={progress} canOpen={canOpen ?? (() => false)} /> : <div />}
        <AskCell
          caseId={caseId}
          queries={queries.data}
          open={open}
          expanded={requests}
          onToggle={() => setRequests((v) => !v)}
        />
      </div>
      {requests && open.length > 0 && <RequestList open={open} />}
    </>
  );
}

const ROUND = "grid size-6 shrink-0 place-items-center rounded-full";

/** The one thing to do next on the case, with the way there. */
function NextCell({ progress, canOpen }: { progress: CaseProgress; canOpen: CanOpen }) {
  const caseId = progress.case_id;
  const stages = progress.stages;
  const first = stages[0];
  const next = nextStage(progress);
  const gate = progress.gate;

  let mark: ReactNode;
  let body: ReactNode;
  let link: { to: string; hash?: string; label: string } | undefined;
  let step: string | undefined;

  if (first?.status === "not_started") {
    mark = (
      <span aria-hidden className={cn(ROUND, "bg-accent text-primary")}>
        <Upload className="size-3.5" />
      </span>
    );
    body = t("page.overview.nextUpload");
    link = {
      to: caseTabPath(caseId, tabForStage("documents")),
      label: t("page.overview.open"),
    };
  } else if (gate?.can_open && !gate.open) {
    mark = (
      <span aria-hidden className={cn(ROUND, "bg-positive-soft text-positive")}>
        <ShieldCheck className="size-3.5" />
      </span>
    );
    body = <span className="font-medium">{t("assessment.gateTitle")}</span>;
    link = {
      to: caseTabPath(caseId, tabForStage("completeness")),
      hash: "readiness",
      label: t("assessment.lockedAction"),
    };
  } else if (next) {
    const index = stages.indexOf(next);
    mark = <StatusMark n={index + 1} status={next.status} />;
    step = t("progress.stageOf", { n: index + 1, total: stages.length });
    body = (
      <>
        <span className="font-medium">{t(`progress.stage.${next.key}`)}</span>
        <span className="text-muted-foreground"> · {stageDetail(next)}</span>
      </>
    );
    link = canOpen(next.key)
      ? { to: caseTabPath(caseId, tabForStage(next.key)), label: t("page.overview.open") }
      : undefined;
  } else {
    mark = <CheckCircle2 aria-hidden className="size-6 shrink-0 text-positive" />;
    body = t("page.overview.nextNone");
  }

  // On a phone the way there sits on the label's line, so the step's text has the full width;
  // from 40rem it sits at the right, centred on the cell.
  return (
    <div
      className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 px-4 py-3 @min-[40rem]/glance:px-5"
      data-testid="next-action"
    >
      <span className="row-span-2 grid">{mark}</span>
      <p className="field-label col-start-2 row-start-1 self-center">
        {t("page.overview.next")}
        {step && <span className="@max-[40rem]/glance:hidden"> · {step}</span>}
      </p>
      {link && (
        <Link
          to={link.to}
          {...(link.hash && { hash: link.hash })}
          className="col-start-3 row-start-1 inline-flex items-center gap-1 self-center rounded-sm text-[12.5px] font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring @min-[40rem]/glance:row-end-3"
        >
          {link.label}
          <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      )}
      <p className="col-start-2 col-end-4 row-start-2 mt-0.5 text-[13px] leading-5 text-foreground @min-[40rem]/glance:col-end-3">
        {body}
      </p>
    </div>
  );
}

const COPY_BUTTON =
  "inline-flex h-10 items-center justify-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[12px] font-medium text-foreground hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring @min-[40rem]/glance:h-7";

/** What is asked of the customer, counted by kind, ready to copy. */
function AskCell({
  caseId,
  queries,
  open,
  expanded,
  onToggle,
}: {
  caseId: string;
  queries: QueryItem[] | undefined;
  open: QueryItem[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const { data: c } = useCase(caseId);
  const { copied, copy } = useCopy();
  const resolved = queries ? queries.length - open.length : 0;
  const groups = QUERY_GROUPS.map((g) => ({
    g,
    n: open.filter((q) => q.group === g).length,
  })).filter((x) => x.n > 0);
  const asking = open.length > 0;

  // On a phone: the label with the toggle beside it, the counts, then the copy buttons across
  // the cell. From 40rem the copy buttons sit on the label's line (laid out as that line's
  // height, so it stays one line tall) and the toggle follows the counts, so the counts have a
  // line of their own and the cell keeps to two lines. The source order is the wider screen's.
  return (
    <div
      className="min-w-0 px-4 py-3 @min-[40rem]/glance:px-5 @min-[60rem]/glance:pl-8"
      data-testid="journey-ask"
    >
      <div className="flex flex-wrap items-center gap-x-3">
        <p className="field-label order-1 mr-auto">
          {t("journey.askCustomer")}
          {/* On a phone the resolved count gives way, so the toggle fits beside the label. */}
          <span className="tabular normal-case tracking-normal">
            {" · "}
            {queries ? (
              <>
                {t("journey.askOpen", { n: open.length })}
                <span className="@max-[40rem]/glance:hidden">
                  {" · "}
                  {t("journey.askResolved", { n: resolved })}
                </span>
              </>
            ) : (
              "—"
            )}
          </span>
        </p>
        {asking && (
          <div className="order-5 mt-2 grid w-full grid-cols-2 gap-2 @min-[40rem]/glance:order-2 @min-[40rem]/glance:-my-1 @min-[40rem]/glance:flex @min-[40rem]/glance:w-auto @min-[40rem]/glance:gap-1.5">
            <button
              type="button"
              onClick={() => void copy("list", queryListText(open))}
              className={COPY_BUTTON}
              data-testid="journey-copy-list"
            >
              <CopyLabel
                icon={ClipboardCopy}
                label={t("journey.copyList")}
                copied={copied === "list"}
              />
            </button>
            <button
              type="button"
              onClick={() =>
                void copy("email", queryListEmail(c ?? { borrower: "", id: caseId }, open))
              }
              className={COPY_BUTTON}
              data-testid="journey-copy-email"
            >
              <CopyLabel icon={Mail} label={t("queries.copyEmail")} copied={copied === "email"} />
            </button>
            <span className="sr-only" aria-live="polite">
              {copied ? t("journey.copied") : ""}
            </span>
          </div>
        )}
        <span aria-hidden className="order-3 h-0 basis-full" />
        {queries && !asking ? (
          <p className="order-4 mt-1 flex basis-full items-center gap-1.5 text-[12.5px] text-positive">
            <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
            {t("queries.emptyDescription")}
          </p>
        ) : queries ? (
          // The counts keep at least 14rem: where the toggle does not fit beside them it goes
          // under them, never over them.
          <CountList
            list
            strong
            counts={groups.map(({ g, n }) => ({ key: g, label: t(`queryGroup.${g}`), n }))}
            className="order-4 mt-1.5 min-w-0 flex-[1_1_14rem] text-[12.5px] leading-5 text-foreground @min-[40rem]/glance:mt-2"
            testId="journey-ask-counts"
          />
        ) : (
          <p className="order-4 mt-1.5 min-w-0 flex-[1_1_14rem] text-[12.5px] leading-5 text-foreground">
            —
          </p>
        )}
        {asking && (
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls="journey-requests"
            onClick={onToggle}
            className="group order-2 inline-flex items-center gap-1 rounded-sm text-[12px] font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring @min-[40rem]/glance:order-5 @min-[40rem]/glance:ml-auto @min-[40rem]/glance:mt-2"
            data-testid="journey-requests-toggle"
          >
            {t(expanded ? "journey.hideRequests" : "journey.showRequests")}
            <ChevronDown
              className="size-3.5 transition-transform group-aria-expanded:rotate-180 motion-reduce:transition-none"
              aria-hidden
            />
          </button>
        )}
      </div>
    </div>
  );
}

/** Every open request, by kind and numbered as the list the customer receives. */
function RequestList({ open }: { open: QueryItem[] }) {
  const { copied, copy } = useCopy();
  return (
    <div
      id="journey-requests"
      className="border-t border-border px-4 py-3 @min-[40rem]/glance:px-5"
      data-testid="journey-requests"
    >
      <div className="grid gap-x-8 gap-y-4 @min-[60rem]/glance:grid-cols-3">
        {numbered(open).map(({ group, items }) => (
          <section key={group} className="min-w-0">
            <h4 className="field-label">{t(`queryGroup.${group}`)}</h4>
            <ol className="mt-1.5 space-y-1.5">
              {items.map(({ n, item }) => (
                <li
                  key={item.id}
                  className="flex items-start gap-2 text-[12.5px] leading-5 text-foreground"
                >
                  <span className="tabular w-5 shrink-0 text-right text-[11.5px] leading-5 text-muted-foreground">
                    {n}.
                  </span>
                  <span className="min-w-0 flex-1">{item.text}</span>
                  <button
                    type="button"
                    aria-label={t("journey.copyRequest", { n })}
                    title={t("journey.copyRequest", { n })}
                    onClick={() => void copy(item.id, item.text)}
                    className="-my-1 grid size-7 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                  >
                    {copied === item.id ? (
                      <CopyCheck className="size-3.5 text-positive" aria-hidden />
                    ) : (
                      <Copy className="size-3.5" aria-hidden />
                    )}
                  </button>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      <span className="sr-only" aria-live="polite">
        {copied ? t("journey.copied") : ""}
      </span>
    </div>
  );
}
