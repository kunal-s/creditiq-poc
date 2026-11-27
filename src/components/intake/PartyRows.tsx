import type { IntakeSection, Meta } from "@/api/types";
import { t } from "@/config/terminology";
import type { Draft, Row } from "@/domain/intake";
import { rowLabel } from "./labels";
import { RepeatingGroup } from "./RepeatingGroup";

/** The people of the application, one card each: a loan against property's applicants,
 * co-applicants and guarantors (the first is the primary applicant), or a business's promoters,
 * directors, partners and guarantors. Each becomes a party of the case, whose KYC is checked per
 * person; an Aadhaar number is only ever its last four digits. */
export function PartyRows({
  section,
  draft,
  meta,
  onChange,
}: {
  section: IntakeSection;
  draft: Draft;
  meta: Meta;
  onChange: (draft: Draft) => void;
}) {
  const roles = section.fields.find((f) => f.id === "role")?.options ?? [];
  const lifted =
    (draft.values["customer_type"] ?? "") !== "" &&
    (section.fields.find((f) => f.id === "pan")?.unless?.["customer_type"] ?? []).includes(
      draft.values["customer_type"] ?? "",
    );
  const title = (row: Row, i: number) => {
    const role = row.cells["role"]?.value ?? "";
    if (section.id === "applicants" && i === 0 && role === "applicant")
      return t("intake.row.primary");
    const label = roles.find((o) => o.id === role)?.label;
    return label ? `${label} · ${rowLabel(section.id, i + 1)}` : rowLabel(section.id, i + 1);
  };
  return (
    <RepeatingGroup
      section={section}
      draft={draft}
      meta={meta}
      onChange={onChange}
      rowTitle={title}
      fieldProps={(field) => (field.type === "pan" ? { holderLifted: lifted } : {})}
    />
  );
}
