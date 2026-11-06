import { createFileRoute, Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell/PageHeader";
import { FilesFlag, ReviewFlag, StageLink } from "@/components/cases/CasesTable";
import { QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { formatDate, formatInr, useCases, useLabels } from "@/domain/cases";
import { useCan, useSession } from "@/domain/session";

// My appraisals, as the original design: a card for each appraisal the user can see, with its
// stage, identifiers, what is asked and what needs a person.

export const Route = createFileRoute("/appraisals/")({
  head: () => ({
    meta: [{ title: `${t("page.myAppraisals.title")} — ${t("tenant.product.name")}` }],
  }),
  component: MyAppraisals,
});

function MyAppraisals() {
  const cases = useCases();
  const labels = useLabels();
  const session = useSession();
  const canCreate = useCan("case.create");
  const open = (cases.data ?? []).filter((c) => c.stage !== "Completed");
  return (
    <div>
      <PageHeader
        eyebrow={t("nav.group.workbench")}
        title={t("page.myAppraisals.title")}
        purpose={t("page.myAppraisals.purpose", { name: session?.user.name ?? "" })}
        actions={
          canCreate && (
            <Link
              to="/appraisals/new"
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> {t("nav.newCase")}
            </Link>
          )
        }
      />
      <div className="px-4 py-5 sm:px-6">
        <QueryView
          query={cases}
          isEmpty={() => open.length === 0}
          empty={{ title: t("state.noCases.title"), description: t("state.noCases.description") }}
        >
          {() => (
            <ul
              className="grid gap-3 @min-[42rem]/main:grid-cols-2 @min-[80rem]/main:grid-cols-3"
              data-testid="appraisal-cards"
            >
              {open.map((c) => (
                <li
                  key={c.id}
                  className="flex min-w-0 flex-col rounded border border-border bg-surface px-4 py-3.5"
                  data-testid="appraisal-card"
                >
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      to="/appraisals/$caseId"
                      params={{ caseId: c.id }}
                      className="min-w-0 break-words text-[14px] font-semibold text-foreground hover:text-primary hover:underline"
                    >
                      {c.borrower}
                    </Link>
                    <StageLink c={c} />
                  </div>
                  <p className="tabular mt-0.5 text-[11px] text-muted-foreground">
                    {c.id} · {labels.constitution(c.constitution)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground" data-testid="case-kind">
                    {labels.caseKind(c)}
                  </p>
                  <p className="mt-2 text-[12.5px] text-foreground">
                    {labels.facilities(c.facilities)} ·{" "}
                    <span className="tabular">{formatInr(c.amount_inr)}</span>
                  </p>
                  <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1">
                    <Fact label={t("cases.col.rm")} value={c.rm} />
                    <Fact label={t("cases.col.created")} value={formatDate(c.created_at)} />
                    <Fact
                      label={t("caseHeader.bankStage")}
                      value={labels.bankStage(c.bank_stage)}
                    />
                  </dl>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    <FilesFlag c={c} />
                    <ReviewFlag count={c.open_review_items} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </QueryView>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="field-label">{label}</dt>
      <dd className="tabular break-words text-[12px] text-foreground">{value}</dd>
    </div>
  );
}
