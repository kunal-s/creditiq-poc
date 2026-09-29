import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import type { CaseDetail } from "@/api/types";
import { useCase } from "@/domain/cases";
import { t } from "@/config/terminology";
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
  const { data, isLoading, isError } = useCase(caseId);
  if (isLoading) return null;
  if (isError || !data) {
    return (
      <div className="px-6 py-5">
        <EmptyState
          title={`No ${t("term.application.singular")} ${caseId}`}
          description="It does not exist, or it is not assigned to you."
          action={
            <Link
              to="/appraisals"
              className="text-[12.5px] font-medium text-primary hover:underline"
            >
              {t("nav.myAppraisals")}
            </Link>
          }
        />
      </div>
    );
  }
  return <>{children(data)}</>;
}
