import { createFileRoute, Link } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { formatDate, formatInr, useCases, useLabels } from "@/domain/cases";
import { useSession } from "@/domain/session";
import { t } from "@/config/terminology";
import { PageHeader } from "@/components/shell/PageHeader";
import { QueryView } from "@/components/common/States";
import { ReviewFlag, StageLink } from "@/components/cases/CasesTable";

export const Route = createFileRoute("/appraisals/")({
  head: () => ({
    meta: [{ title: `${t("page.appraisals.title")} — ${t("tenant.product.name")}` }],
  }),
  component: MyAppraisals,
});

function MyAppraisals() {
  const cases = useCases();
  const labels = useLabels();
  const session = useSession();
  const canCreate = session?.user.permissions.includes("case.create") ?? false;

  return (
    <div>
      <PageHeader
        eyebrow={t("page.appraisals.eyebrow")}
        title={t("page.appraisals.title")}
        purpose={t("page.appraisals.purpose")}
        actions={
          canCreate ? (
            <Link
              to="/appraisals/new"
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" /> {t("nav.newApplication")}
            </Link>
          ) : undefined
        }
      />
      <div className="px-4 py-5 sm:px-6">
        <QueryView
          query={cases}
          isEmpty={(d) => d.length === 0}
          empty={{
            title: t("state.noCases.title"),
            description: t("state.noCases.description"),
          }}
        >
          {(list) => (
            <div className="grid gap-3 lg:grid-cols-2" data-testid="appraisal-cards">
              {list.map((a) => (
                <article key={a.id} className="min-w-0 rounded border border-border bg-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        to="/docready/$caseId/checklist"
                        params={{ caseId: a.id }}
                        className="break-words text-[14px] font-semibold text-foreground hover:text-primary hover:underline"
                      >
                        {a.borrower}
                      </Link>
                      <p className="mt-0.5 text-[11.5px] text-muted-foreground tabular">
                        {a.id} · {labels.constitution(a.constitution)}
                      </p>
                    </div>
                    <StageLink c={a} />
                  </div>
                  <p className="mt-2 text-[12.5px] text-foreground">
                    {labels.facilities(a.facilities)}
                  </p>
                  <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-[11.5px] sm:grid-cols-3">
                    <div>
                      <dt className="field-label">{t("cases.col.amount")}</dt>
                      <dd className="tabular">{formatInr(a.amount_inr)}</dd>
                    </div>
                    <div>
                      <dt className="field-label">{t("cases.col.rm")}</dt>
                      <dd>{a.rm}</dd>
                    </div>
                    <div>
                      <dt className="field-label">{t("cases.col.created")}</dt>
                      <dd className="tabular">{formatDate(a.created_at)}</dd>
                    </div>
                  </dl>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <ReviewFlag count={a.open_review_items} />
                    <Link
                      to="/appraisals/$id/upload"
                      params={{ id: a.id }}
                      className="text-[12px] font-medium text-primary hover:underline"
                    >
                      {t("step.documents")}
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </QueryView>
      </div>
    </div>
  );
}
