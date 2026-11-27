import type { CaseProposal, IntakeSection, Meta } from "@/api/types";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { linesTotal, type Draft } from "@/domain/intake";
import { RepeatingGroup } from "./RepeatingGroup";

/** A business's facility lines, one card each (facility, amount, nature, purpose, tenure, existing
 * limit). Their total is the amount requested; when the message stated a different figure in all,
 * it is named under the total so the RM can see the difference. */
export function FacilityLines({
  section,
  draft,
  meta,
  proposal,
  onChange,
}: {
  section: IntakeSection;
  draft: Draft;
  meta: Meta;
  proposal: CaseProposal | null;
  onChange: (draft: Draft) => void;
}) {
  const total = linesTotal(draft);
  const stated = Number((proposal?.fields["amount_inr"]?.value ?? "").replace(/\D/g, "")) || 0;
  return (
    <RepeatingGroup
      section={section}
      draft={draft}
      meta={meta}
      onChange={onChange}
      footer={
        <div className="rounded bg-surface-muted px-3 py-2 text-[12px]" data-testid="lines-total">
          <p className="font-medium text-foreground tabular">
            {total > 0 ? t("intake.total", { amount: formatInr(total) }) : t("intake.totalNone")}
          </p>
          {stated > 0 && stated !== total && (
            <p className="mt-0.5 text-muted-foreground tabular" data-testid="message-states">
              {t("intake.messageStates", { amount: formatInr(stated) })}
            </p>
          )}
        </div>
      }
    />
  );
}
