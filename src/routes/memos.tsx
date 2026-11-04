import { useQueries } from "@tanstack/react-query";
import { createFileRoute, Link } from "@tanstack/react-router";
import { api } from "@/api/client";
import type { Cam } from "@/api/types";
import { StageLink } from "@/components/cases/CasesTable";
import { Chip, Kpi, Panel } from "@/components/common/Panel";
import { QueryView } from "@/components/common/States";
import { PageHeader } from "@/components/shell/PageHeader";
import { t } from "@/config/terminology";
import { formatInr, useCases, useLabels } from "@/domain/cases";

// The memo library, as the original design: every appraisal on the book with where its credit
// memo stands. Each memo is read from the appraisal; one not drafted yet says so.

export const Route = createFileRoute("/memos")({
  head: () => ({
    meta: [{ title: `${t("nav.memoLibrary")} — ${t("tenant.product.name")}` }],
  }),
  component: MemoLibrary,
});

function edited(m: Cam): number {
  return m.sections.filter((s) => (s.review?.state ?? "machine") !== "machine").length;
}

function written(m: Cam): boolean {
  return (
    m.recommendation.trim() !== "" || (m.recommendation_review?.state ?? "machine") !== "machine"
  );
}

function MemoLibrary() {
  const cases = useCases();
  const labels = useLabels();
  const list = cases.data ?? [];
  const memos = useQueries({
    queries: list.map((c) => ({
      queryKey: ["cases", c.id, "cam"],
      queryFn: () => api.caseCam(c.id),
      retry: false,
    })),
  });
  const drafted = memos.filter((q) => q.data).length;
  const recommended = memos.filter((q) => q.data && written(q.data)).length;
  const borrowers = new Set(list.map((c) => c.borrower)).size;

  return (
    <div>
      <PageHeader
        eyebrow={t("nav.group.portfolio")}
        title={t("nav.memoLibrary")}
        purpose={t("page.memos.purpose")}
      />
      <div className="space-y-4 px-4 py-5 sm:px-6">
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Kpi
            label={t("page.memos.kpi.book")}
            value={borrowers}
            note={t("page.memos.kpi.bookNote", { n: list.length })}
          />
          <Kpi
            label={t("page.memos.kpi.drafted")}
            value={drafted}
            note={t("page.memos.kpi.draftedNote", { n: list.length })}
          />
          <Kpi
            label={t("page.memos.kpi.recommended")}
            value={recommended}
            note={t("page.memos.kpi.recommendedNote")}
          />
        </section>
        <Panel
          title={t("page.memos.table")}
          subtitle={t("page.memos.tableSub", { n: list.length })}
          testId="memo-library"
        >
          <QueryView
            query={cases}
            isEmpty={() => list.length === 0}
            empty={{ title: t("state.noCases.title"), description: t("state.noCases.description") }}
          >
            {() => (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border bg-surface-muted text-left text-[10.5px] uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-2 font-medium">{t("term.borrower.title")}</th>
                      <th className="px-3 py-2 font-medium">{t("page.memos.col.memo")}</th>
                      <th className="px-3 py-2 font-medium">{t("page.memos.col.status")}</th>
                      <th className="px-3 py-2 font-medium">{t("page.memos.col.exposure")}</th>
                      <th className="px-3 py-2 font-medium">{t("term.stage")}</th>
                      <th className="px-4 py-2 font-medium">{t("page.memos.col.asOf")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {list.map((c, i) => {
                      const m = memos[i]?.data;
                      return (
                        <tr key={c.id} className="align-top" data-testid="memo-row">
                          <td className="px-4 py-2.5">
                            <Link
                              to="/appraisals/$caseId/outputs"
                              params={{ caseId: c.id }}
                              search={{ view: "cam" }}
                              className="font-medium text-foreground hover:text-primary hover:underline"
                            >
                              {c.borrower}
                            </Link>
                            <p className="tabular text-[11px] text-muted-foreground">
                              {c.id} · {labels.constitution(c.constitution)}
                            </p>
                          </td>
                          <td className="px-3 py-2.5">
                            {m ? (
                              <>
                                <p>{m.template_name || m.title}</p>
                                <p className="text-[11px] text-muted-foreground">
                                  {t("page.memos.sections", {
                                    n: m.sections.length,
                                    edited: edited(m),
                                  })}
                                </p>
                              </>
                            ) : (
                              <span className="text-muted-foreground">
                                {t("page.memos.notDrafted")}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {m ? (
                              written(m) ? (
                                <Chip tone="positive">{t("page.memos.status.recommended")}</Chip>
                              ) : (
                                <Chip tone="info">{t("page.memos.status.drafting")}</Chip>
                              )
                            ) : (
                              <Chip tone="muted">{t("page.memos.status.none")}</Chip>
                            )}
                          </td>
                          <td className="tabular px-3 py-2.5">
                            {labels.facilities(c.facilities)}
                            <p className="text-[11px] text-muted-foreground">
                              {formatInr(c.amount_inr)}
                            </p>
                          </td>
                          <td className="px-3 py-2.5">
                            <StageLink c={c} />
                          </td>
                          <td className="tabular px-4 py-2.5 text-muted-foreground">
                            {m ? m.as_of : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </QueryView>
        </Panel>
      </div>
    </div>
  );
}
