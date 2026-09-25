import { Link } from "@tanstack/react-router";
import { PageHeader } from "./PlaceholderPage";
import { EmptyState } from "./EmptyState";
import { useCase } from "@/domain/cases";
import { t } from "@/config/terminology";

/**
 * Stage A's data-access seam for the appraisal wing: real case lookup,
 * designed empty states (plan.md conflict C9). Per-step content is wired in
 * as its stage lands (Stage C onward).
 */
export function CaseStepPage({
  id,
  eyebrow,
  title,
  purpose,
  notBuiltDescription,
}: {
  id: string;
  eyebrow: string;
  title: string;
  purpose: string;
  notBuiltDescription: string;
}) {
  const { data: appraisal, isLoading } = useCase(id);

  return (
    <div>
      <PageHeader eyebrow={eyebrow} title={title} purpose={purpose} />
      {!isLoading && (
        <div className="px-6 py-5">
          <EmptyState
            title={appraisal ? "Not wired up yet" : "No case found"}
            description={
              appraisal
                ? notBuiltDescription
                : `No case with id "${id}". It may not have been created yet.`
            }
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
      )}
    </div>
  );
}
