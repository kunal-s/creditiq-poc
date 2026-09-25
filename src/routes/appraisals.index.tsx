import { createFileRoute, Link } from "@tanstack/react-router";
import { AlertTriangle, Plus } from "lucide-react";
import { STAGE_ROUTE } from "@/api/types";
import { useCases } from "@/domain/cases";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/appraisals/")({
  head: () => ({
    meta: [
      { title: `${t("page.appraisals.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content:
          "Every appraisal assigned to you, with stage, proposed facilities, relationship manager and open discrepancies.",
      },
    ],
  }),
  component: MyAppraisals,
});

function MyAppraisals() {
  const { data: cases = [] } = useCases();

  return (
    <div>
      <PageHeader
        eyebrow={t("page.appraisals.eyebrow")}
        title={t("page.appraisals.title")}
        purpose="Every appraisal assigned to you, from identifier intake through committee submission."
        actions={
          <Link
            to="/applications/new"
            className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[13px] font-medium text-primary-foreground hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" /> {t("nav.newApplication")}
          </Link>
        }
      />
      <div className="px-6 py-5">
        {cases.length === 0 ? (
          <EmptyState
            title="No appraisals yet"
            description="Applications you start will appear here once entity resolution begins."
            action={
              <Link
                to="/applications/new"
                className="text-[12.5px] font-medium text-primary hover:underline"
              >
                {t("nav.newApplication")}
              </Link>
            }
          />
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {cases.map((a) => (
              <article key={a.id} className="rounded border border-border bg-surface p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <Link
                      to="/appraisals/$id/identity"
                      params={{ id: a.id }}
                      className="text-[14px] font-semibold text-foreground hover:text-primary hover:underline"
                    >
                      {a.borrower}
                    </Link>
                    <p className="mt-0.5 text-[11.5px] text-muted-foreground tabular">
                      {a.id} · PAN {a.pan} · GSTIN {a.gstin}
                    </p>
                  </div>
                  <Link
                    to={"/appraisals/$id/" + STAGE_ROUTE[a.stage]}
                    params={{ id: a.id }}
                    className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11.5px] font-medium text-foreground hover:bg-accent"
                  >
                    {a.stage}
                  </Link>
                </div>
                <p className="mt-2 text-[12.5px] text-foreground">{a.proposal}</p>
                <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-[11.5px] sm:grid-cols-4">
                  <div>
                    <dt className="field-label">Exposure</dt>
                    <dd className="tabular">{a.exposure}</dd>
                  </div>
                  <div>
                    <dt className="field-label">Rating</dt>
                    <dd className="tabular">{a.rating}</dd>
                  </div>
                  <div>
                    <dt className="field-label">RM</dt>
                    <dd>{a.rm}</dd>
                  </div>
                  <div>
                    <dt className="field-label">Branch</dt>
                    <dd>{a.branch}</dd>
                  </div>
                </dl>
                {a.discrepancies > 0 && (
                  <Link
                    to="/appraisals/$id/cross-verification"
                    params={{ id: a.id }}
                    className="mt-3 inline-flex items-center gap-1 rounded border border-flag/40 bg-flag-soft px-1.5 py-0.5 text-[11.5px] font-medium text-flag-foreground"
                  >
                    <AlertTriangle className="h-3 w-3" /> {a.discrepancies} open discrepanc
                    {a.discrepancies === 1 ? "y" : "ies"}
                  </Link>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
