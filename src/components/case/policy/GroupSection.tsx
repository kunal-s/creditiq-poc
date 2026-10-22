import { useState } from "react";
import type { NormResult, PolicyGroup } from "@/api/types";
import { t } from "@/config/terminology";
import { countParts, groupHeadingId, groupSectionId } from "@/domain/policy";
import { cn } from "@/lib/utils";
import { NormDetail, NormTile } from "./NormTile";
import { RatioTable } from "./RatioTable";
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

/** The tiles in a row where the window is wide: every norm on one row up to four, three a row for
 * five or six, four beyond. */
function columns(n: number): number {
  return n <= 4 ? n : n <= 6 ? 3 : 4;
}

const XL_COLS: Record<number, string> = {
  1: "xl:grid-cols-1",
  2: "xl:grid-cols-2",
  3: "xl:grid-cols-3",
  4: "xl:grid-cols-4",
};

/** One family of norms as tiles: each with its actual value in the colour of where it stands and
 * the norm it is held to. The selected tile's figures, with their pages, and how it was decided
 * open under the tiles. */
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
  const [selected, setSelected] = useState<string | null>(null);
  const open = norms.find((n) => n.id === selected);
  const detailId = `${groupSectionId(group.family)}-detail`;
  const cols = columns(norms.length);
  const fillXl = (cols - (norms.length % cols)) % cols;
  const fillSm = norms.length > 1 ? norms.length % 2 : 0;
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
      ) : group.family === "ratios" ? (
        <RatioTable
          caseId={caseId}
          norms={norms}
          selected={selected}
          detailId={detailId}
          onSelect={(id, force) => setSelected((now) => (force || now !== id ? id : null))}
        />
      ) : (
        <div className="overflow-hidden rounded border border-border bg-surface">
          <ul
            className={cn(
              "grid grid-cols-1 gap-px bg-border",
              norms.length > 1 && "sm:grid-cols-2",
              XL_COLS[cols],
            )}
            data-testid="policy-norms"
          >
            {norms.map((norm) => (
              <NormTile
                key={norm.id}
                norm={norm}
                selected={norm.id === selected}
                detailId={detailId}
                onSelect={(force) =>
                  setSelected((now) => (force || now !== norm.id ? norm.id : null))
                }
              />
            ))}
            {/* The rest of a short last row, so the grid's lines close around the tiles. */}
            {Array.from({ length: fillSm }, (_, i) => (
              <li key={`sm-${i}`} aria-hidden className="hidden bg-surface sm:block xl:hidden" />
            ))}
            {Array.from({ length: fillXl }, (_, i) => (
              <li key={`xl-${i}`} aria-hidden className="hidden bg-surface xl:block" />
            ))}
          </ul>
          {open && (
            <NormDetail
              caseId={caseId}
              norm={open}
              id={detailId}
              onClose={() => setSelected(null)}
            />
          )}
        </div>
      )}
    </section>
  );
}
