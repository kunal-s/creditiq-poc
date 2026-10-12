import type { UseQueryResult } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import type { ApprovingAuthority } from "@/api/types";
import { AuthorityView } from "@/components/case/ApprovingAuthority";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { t } from "@/config/terminology";
import { AUTHORITY_HEADING_ID, AUTHORITY_SECTION_ID, matrixNotPublished } from "@/domain/policy";

/** The approving authority: the amount band for each product requested, the deviation steps that
 * raised it, the one that decides, and what the norms not yet assessed could do. Without a
 * published matrix the norms above still stand. */
export function AuthoritySection({
  caseId,
  query,
}: {
  caseId: string;
  query: UseQueryResult<ApprovingAuthority>;
}) {
  return (
    <section
      id={AUTHORITY_SECTION_ID}
      aria-labelledby={AUTHORITY_HEADING_ID}
      className="min-w-0 scroll-mt-4 space-y-3"
      data-testid={AUTHORITY_SECTION_ID}
    >
      <header className="border-b border-border pb-2">
        {/* Focused when the authority's card on the overview is clicked. */}
        <h2
          id={AUTHORITY_HEADING_ID}
          tabIndex={-1}
          className="flex items-center gap-2 rounded-sm text-[16px] font-semibold tracking-tight text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Scale className="h-4 w-4 shrink-0 text-primary" aria-hidden />
          <span className="min-w-0 break-words">{t("approvingAuthority.title")}</span>
        </h2>
        <p className="mt-0.5 break-words text-[12px] text-muted-foreground">
          {t("policy.authorityPurpose")}
        </p>
      </header>
      {query.data ? (
        <AuthorityView caseId={caseId} authority={query.data} />
      ) : matrixNotPublished(query.error) ? (
        <p
          className="rounded border border-border bg-surface px-4 py-2.5 text-[12.5px] text-muted-foreground"
          data-testid="authority-not-published"
        >
          {t("approvingAuthority.notPublished")}
        </p>
      ) : query.isError ? (
        <ErrorState error={query.error} compact onRetry={() => void query.refetch()} />
      ) : (
        <LoadingBlock rows={2} />
      )}
    </section>
  );
}
