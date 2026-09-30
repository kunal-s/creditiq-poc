import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { CaseDetail } from "@/api/types";
import { useCase } from "@/domain/cases";
import { errorKind } from "@/domain/errors";
import { t } from "@/config/terminology";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { EmptyState } from "./EmptyState";

/** Loads the case for a case route; renders a designed not-found state
 * when the case does not exist or the user may not see it. */
export function CaseScreen({
  caseId,
  children,
}: {
  caseId: string;
  children: (c: CaseDetail) => ReactNode;
}) {
  const { data, isLoading, isError, error, refetch } = useCase(caseId);
  if (isLoading) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <LoadingBlock rows={3} />
      </div>
    );
  }
  if (isError && errorKind(error) !== "notFound") {
    return (
      <div className="px-4 py-5 sm:px-6">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <EmptyState
          title={t("state.caseNotFound.title", { id: caseId })}
          description={t("state.caseNotFound.description")}
          action={
            <Link to="/" className="text-[12.5px] font-medium text-primary hover:underline">
              {t("nav.cases")}
            </Link>
          }
        />
      </div>
    );
  }
  return <>{children(data)}</>;
}
