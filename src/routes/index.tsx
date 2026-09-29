import { createFileRoute } from "@tanstack/react-router";
import { useCases } from "@/domain/cases";
import { t } from "@/config/terminology";
import { cn } from "@/lib/utils";
import type { Case, Stage } from "@/api/types";
import { PageHeader } from "@/components/shell/PageHeader";
import { EmptyState } from "@/components/shell/EmptyState";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: t("tenant.product.documentTitleTemplate") },
      { name: "description", content: t("tenant.product.metaDescription") },
    ],
  }),
  component: Workbench,
});

const stageTone: Record<Stage, string> = {
  Intake: "bg-muted text-muted-foreground",
  Readiness: "bg-info-soft text-info",
  Appraisal: "bg-accent text-accent-foreground",
  Outputs: "bg-accent text-accent-foreground",
  Completed: "bg-positive-soft text-positive",
};

function CasesTable({ cases }: { cases: Case[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
            <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
            <th className="px-3 py-2 font-medium">Product and amount</th>
            <th className="px-3 py-2 font-medium">Stage</th>
            <th className="px-3 py-2 font-medium">RM</th>
            <th className="px-3 py-2 font-medium">Created</th>
            <th className="px-4 py-2 font-medium">Review items</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {cases.map((c) => (
            <tr key={c.id} className="align-top">
              <td className="px-4 py-3">
                <div className="font-medium text-foreground">{c.borrower}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">
                  {c.id} · {c.constitution}
                </div>
              </td>
              <td className="px-3 py-3">
                <div className="text-foreground">{c.product}</div>
                <div className="mt-0.5 text-[11px] text-muted-foreground tabular">{c.amount}</div>
              </td>
              <td className="px-3 py-3">
                <span
                  className={cn(
                    "inline-block rounded px-1.5 py-0.5 text-[11.5px] font-medium",
                    stageTone[c.stage],
                  )}
                >
                  {c.stage}
                </span>
              </td>
              <td className="px-3 py-3 text-foreground">{c.rm}</td>
              <td className="px-3 py-3 text-muted-foreground tabular">{c.created}</td>
              <td className="px-4 py-3 tabular">{c.openReviewItems}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Workbench() {
  const { data: cases = [], isLoading, isError } = useCases();

  return (
    <div>
      <PageHeader
        eyebrow={t("tenant.bank.unit")}
        title={t("page.home.title")}
        purpose={t("page.home.purpose")}
      />
      <div className="px-6 py-5">
        {isError ? (
          <EmptyState
            title="The case service is not reachable"
            description="Cases cannot be listed right now. Check that the engine service is running, then reload."
          />
        ) : isLoading ? null : cases.length === 0 ? (
          <EmptyState
            title={`No ${t("term.application.plural")} yet`}
            description={`${t("term.application.pluralTitle")} appear here once they are created.`}
          />
        ) : (
          <section className="rounded border border-border bg-surface">
            <CasesTable cases={cases} />
          </section>
        )}
      </div>
    </div>
  );
}
