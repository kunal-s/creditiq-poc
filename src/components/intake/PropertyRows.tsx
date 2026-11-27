import type { IntakeSection, Meta } from "@/api/types";
import { filledRows, type Draft } from "@/domain/intake";
import { RepeatingGroup } from "./RepeatingGroup";

/** The properties offered as security, one card each: type, occupancy, address and PIN code, the
 * owners (chosen from the applicants named above), declared value, area and construction. They
 * later decide the property documents, the owners' KYC and the loan-to-value. */
export function PropertyRows({
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
  const names = (from: string | null | undefined) =>
    from
      ? Array.from(
          new Set(
            filledRows(draft, from)
              .map((r) => (r.cells["name"]?.value ?? "").trim())
              .filter(Boolean),
          ),
        )
      : [];
  return (
    <RepeatingGroup
      section={section}
      draft={draft}
      meta={meta}
      onChange={onChange}
      fieldProps={(field) =>
        field.type === "parties" ? { parties: names(field.from_section) } : {}
      }
    />
  );
}
