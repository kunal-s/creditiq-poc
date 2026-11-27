// Test ids: proposed-case (the form), group-<section>, rows-<section>, needs-confirmation.
import { AlertTriangle } from "lucide-react";
import type { CaseProposal, IntakeProduct, IntakeSection, Meta } from "@/api/types";
import { t } from "@/config/terminology";
import { unsettled, visibleFields, visibleSections, type Draft } from "@/domain/intake";
import { FacilityLines } from "./FacilityLines";
import { PartyRows } from "./PartyRows";
import { PropertyRows } from "./PropertyRows";
import { extraFields } from "./labels";
import { ValuesSection } from "./ProposedCase";
import { RepeatingGroup } from "./RepeatingGroup";

/** Step 3, the application form of the chosen product, as config/intake.yaml lays it out: its
 * sections in order, single values as fields and repeating sections as rows, a section shown only
 * for the customer or case type it applies to. What the message proposed and the form has no
 * field for is kept at the end, as read. */
export function IntakeForm({
  form,
  draft,
  proposal,
  meta,
  selected,
  onSelect,
  onChange,
}: {
  form: IntakeProduct;
  draft: Draft;
  proposal: CaseProposal | null;
  meta: Meta;
  selected: string | null;
  onSelect: (key: string) => void;
  onChange: (draft: Draft) => void;
}) {
  const pending = unsettled(meta, proposal, draft);
  const rows = (section: IntakeSection) => {
    const props = { section, draft, meta, onChange };
    if (section.id === "applicants" || section.id === "people") return <PartyRows {...props} />;
    if (section.id === "properties") return <PropertyRows {...props} />;
    if (section.id === "facilities") return <FacilityLines {...props} proposal={proposal} />;
    return <RepeatingGroup {...props} />;
  };
  return (
    <div className="min-w-0 space-y-3" data-testid="proposed-case">
      <h2 className="text-[13px] font-semibold text-foreground">{t("intake.form.title")}</h2>
      {visibleSections(form, draft.values).map((section) =>
        section.repeat ? (
          <div key={section.id} className="min-w-0">
            {rows(section)}
          </div>
        ) : (
          <ValuesSection
            key={section.id}
            sectionId={section.id}
            fields={visibleFields(section, draft.values)}
            draft={draft}
            proposal={proposal}
            meta={meta}
            selected={selected}
            onSelect={onSelect}
            onChange={onChange}
          />
        ),
      )}
      {draft.extras.length > 0 && (
        <ValuesSection
          sectionId="extras"
          fields={extraFields(draft.extras)}
          draft={draft}
          proposal={proposal}
          meta={meta}
          selected={selected}
          onSelect={onSelect}
          onChange={onChange}
        />
      )}
      {pending.length > 0 && (
        <p
          className="flex items-center gap-1.5 rounded border border-flag/40 bg-flag-soft px-4 py-2 text-[12px] text-flag-foreground"
          data-testid="needs-confirmation"
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
          {t("newApplication.needConfirmation", { n: pending.length })}
        </p>
      )}
    </div>
  );
}
