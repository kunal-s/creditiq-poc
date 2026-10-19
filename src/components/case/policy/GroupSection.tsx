import type { NormResult, PolicyGroup } from "@/api/types";
import { t } from "@/config/terminology";
import { countParts, groupHeadingId, groupSectionId } from "@/domain/policy";
import { cn } from "@/lib/utils";
import { NormRow, VALUES } from "./NormRow";
import { GROUP_STATUS } from "./styles";

/** "5 norms · 1 deviation · 1 cannot be evaluated · 3 passed", as the engine counted them; the
 * parts with nothing in them are left out. */
function countsLine(group: PolicyGroup): string {
  if (group.norms === 0) return t("policy.card.noNorms");
  return [
    group.norms === 1 ? t("policy.count.normOne") : t("policy.count.normMany", { n: group.norms }),
    ...countParts(group.counts),
  ].join(" · ");
}

/** One family of norms: each with its required and actual value, the figures it used with their
 * pages, why it could not be evaluated, and how it is calculated. */
export function GroupSection({
  caseId,
  group,
  norms,
}: {
  caseId: string;
  group: PolicyGroup;
  /** The family's norms, in the engine's order. */
  norms: NormResult[];
}) {
  const status = GROUP_STATUS[group.status];
  const Icon = status.icon;
  return (
    <section
      id={groupSectionId(group.family)}
      aria-labelledby={groupHeadingId(group.family)}
      className="min-w-0 scroll-mt-4 space-y-2"
      data-testid={groupSectionId(group.family)}
      data-status={group.status}
    >
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-1 border-b border-border pb-2">
        <div className="min-w-0">
          {/* Focused when the family's card on the overview is clicked. */}
          <h2
            id={groupHeadingId(group.family)}
            tabIndex={-1}
            className="flex items-center gap-2 rounded-sm text-[16px] font-semibold tracking-tight text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon className={cn("h-4 w-4 shrink-0", status.text)} aria-hidden />
            <span className="min-w-0 break-words">{t(`policy.family.${group.family}`)}</span>
          </h2>
          <p className="mt-0.5 break-words text-[12px] text-muted-foreground">
            {t(`policy.familyPurpose.${group.family}`)}
          </p>
        </div>
        <p
          className="tabular break-words text-[11.5px] text-muted-foreground"
          data-testid="policy-group-counts"
        >
          {countsLine(group)}
        </p>
      </header>

      {norms.length === 0 ? (
        <p
          className="rounded border border-border bg-surface px-4 py-2.5 text-[12.5px] text-muted-foreground"
          data-testid="family-pending"
        >
          {t(`policy.familyPending.${group.family}`)}
        </p>
      ) : (
        <ul
          className="divide-y divide-border rounded border border-border bg-surface"
          data-testid="policy-norms"
        >
          {/* The column heads, once; on a phone each row labels its own values. */}
          <li
            aria-hidden
            className="hidden justify-end bg-surface-muted/50 px-4 py-1 text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground sm:flex"
          >
            <span className={cn("grid text-right", VALUES)}>
              <span>{t("policy.required")}</span>
              <span>{t("policy.actual")}</span>
            </span>
          </li>
          {norms.map((norm) => (
            <NormRow key={norm.id} caseId={caseId} norm={norm} />
          ))}
        </ul>
      )}
    </section>
  );
}
