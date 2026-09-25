import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/memos")({
  head: () => ({
    meta: [
      { title: `${t("page.memos.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content: `Every borrower's ${t("term.memo.full")} and versions, with status, internal rating, last update and next review date.`,
      },
    ],
  }),
  component: MemoLibrary,
});

function MemoLibrary() {
  return (
    <div>
      <PageHeader
        eyebrow={t("page.memos.eyebrow")}
        title={t("page.memos.title")}
        purpose={`Every borrower's ${t("term.memo.full")} and versions, with status, internal rating, last update and next review date.`}
      />
      <div className="px-6 py-5">
        <EmptyState
          title="No memos yet"
          description="Memos appear here once an application has been drafted and submitted."
          action={
            <Link
              to="/applications/new"
              className="text-[12.5px] font-medium text-primary hover:underline"
            >
              {t("nav.newApplication")}
            </Link>
          }
        />
      </div>
    </div>
  );
}
