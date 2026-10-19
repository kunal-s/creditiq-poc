import { useId } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { Scale } from "lucide-react";
import type { ApprovingAuthority, NormResult, PolicyAssessment, PolicyGroup } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/config/terminology";
import { useLabels } from "@/domain/cases";
import { joinList } from "@/domain/crossVerification";
import {
  AUTHORITY_SECTION_ID,
  actualText,
  amountAuthorities,
  authorityName,
  authorityRises,
  cannotEvaluateNote,
  countParts,
  deviationStepShort,
  deviationSteps,
  groupHighlights,
  groupSectionId,
  groupsOf,
  matrixNotPublished,
  normElementId,
} from "@/domain/policy";
import { cn } from "@/lib/utils";
import { GROUP_STATUS, OUTCOME_MARK } from "./styles";

/** The button that opens a card's section: its surface covers the whole card, all but the key
 * norms, which open their own rows. */
const openSectionButton =
  "min-w-0 break-words text-left text-[13.5px] font-semibold leading-snug text-foreground after:absolute after:inset-0 after:rounded-sm after:transition-colors hover:after:bg-foreground/[0.03] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-ring";

const card =
  "relative row-span-3 grid min-w-0 grid-rows-subgrid gap-y-0 rounded border border-t-[3px] border-border bg-surface";

/** One card per family of norms, in the engine's order, then one for the approving authority.
 * A family's card says where it stands, its deviations, the norms that cannot be evaluated,
 * passed or did not apply, and the norms the engine picked for it, each opening its row; the
 * authority's card says who must approve and why. A card opens its section. */
export function PolicyOverview({
  policy,
  authority,
  onOpenGroup,
  onOpenAuthority,
  onOpenNorm,
}: {
  policy: PolicyAssessment;
  authority: UseQueryResult<ApprovingAuthority>;
  onOpenGroup: (group: PolicyGroup) => void;
  onOpenAuthority: () => void;
  onOpenNorm: (normId: string) => void;
}) {
  return (
    // Five in a row where the page is wide (at 1280 px and over, beside the side menus); three
    // in a row below that, the authority's card spanning two; two by two on a tablet, the
    // authority's card under them; one column on a phone. Each card spans three rows of the grid
    // (its title, its counts, its key norms) and lays its parts on them, so a row of cards keeps
    // each part level and every card the same height.
    <section className="@container" aria-label={t("policy.overview.label")}>
      <div
        className="grid gap-3 @min-[30rem]:grid-cols-2 @min-[40rem]:grid-cols-3 @min-[62rem]:grid-cols-[repeat(4,minmax(0,1fr))_minmax(0,1.4fr)]"
        data-testid="policy-overview"
      >
        {groupsOf(policy).map((group) => (
          <GroupCard
            key={group.family}
            group={group}
            highlights={groupHighlights(policy, group)}
            onOpen={() => onOpenGroup(group)}
            onOpenNorm={onOpenNorm}
          />
        ))}
        <AuthorityCard query={authority} onOpen={onOpenAuthority} />
      </div>
    </section>
  );
}

function GroupCard({
  group,
  highlights,
  onOpen,
  onOpenNorm,
}: {
  group: PolicyGroup;
  highlights: NormResult[];
  onOpen: () => void;
  onOpenNorm: (normId: string) => void;
}) {
  const id = useId();
  const status = GROUP_STATUS[group.status];
  const Icon = status.icon;
  const { counts } = group;
  const empty = group.status === "no_norms";
  return (
    <div
      className={cn(card, status.bar)}
      data-testid={`policy-group-card-${group.family}`}
      data-status={group.status}
    >
      <div className="min-w-0 px-3 pt-3">
        <div className="flex min-w-0 items-start gap-1.5">
          <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", status.text)} aria-hidden />
          <button
            type="button"
            onClick={onOpen}
            aria-controls={groupSectionId(group.family)}
            aria-describedby={`${id}-counts`}
            className={openSectionButton}
            data-testid="policy-group-open-section"
          >
            {t(`policy.family.${group.family}`)}{" "}
            <span className="sr-only">({t(`policy.status.${group.status}`)})</span>
          </button>
        </div>
        <p className="mt-0.5 break-words text-[11.5px] leading-snug text-muted-foreground">
          {t(`policy.familyPurpose.${group.family}`)}
        </p>
      </div>

      <div id={`${id}-counts`} className="min-w-0 px-3 pt-3">
        {empty ? (
          <p
            className="text-[13px] font-medium leading-snug text-muted-foreground"
            data-testid="policy-group-none"
          >
            {t("policy.card.noNorms")}
          </p>
        ) : (
          <>
            <p className="flex flex-wrap items-baseline gap-x-1.5">
              <span
                className={cn(
                  "tabular text-[26px] font-semibold leading-none",
                  counts.deviations > 0 ? "text-foreground" : "text-muted-foreground",
                )}
                data-testid="policy-group-deviations"
              >
                {counts.deviations}
              </span>{" "}
              <span className="text-[12px] text-muted-foreground">
                {counts.deviations === 1
                  ? t("policy.card.deviationOne")
                  : t("policy.card.deviationMany")}
              </span>
            </p>
            <p
              className="tabular mt-1 break-words text-[11.5px] text-muted-foreground"
              data-testid="policy-group-others"
            >
              {countParts(counts, { deviations: false, passed: true }).join(" · ")}
            </p>
          </>
        )}
      </div>

      <div className="min-w-0 px-3 pb-2.5 pt-2">
        {empty ? (
          <p
            className="break-words border-t border-border pt-2 text-[12px] leading-snug text-muted-foreground"
            data-testid="policy-group-pending"
          >
            {t(`policy.noNorms.${group.family}`)}
          </p>
        ) : (
          highlights.length > 0 && (
            <ul
              className="relative z-10 space-y-0.5 border-t border-border pt-1.5"
              aria-label={t("policy.card.keyFigures")}
              data-testid="policy-group-highlights"
            >
              {/* Each line's mark sits in the card's margin, its text in line with the counts. */}
              {highlights.map((norm) => (
                <li key={norm.id} className="-ml-2 -mr-1">
                  <KeyNorm norm={norm} onOpen={() => onOpenNorm(norm.id)} />
                </li>
              ))}
            </ul>
          )
        )}
      </div>
    </div>
  );
}

/** A key norm: its label, the actual value against the required one (red where it deviates),
 * and, for a norm that cannot be evaluated, what is missing. It opens the norm's row. */
function KeyNorm({ norm, onOpen }: { norm: NormResult; onOpen: () => void }) {
  const note = norm.outcome === "cannot_evaluate" ? cannotEvaluateNote(norm) : null;
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-controls={normElementId(norm.id)}
      className={cn(
        "block w-full min-w-0 rounded-sm border-l-2 py-1 pl-1.5 pr-1 text-left transition-colors hover:bg-foreground/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        OUTCOME_MARK[norm.outcome],
      )}
      data-testid="policy-highlight"
      data-norm={norm.id}
      data-outcome={norm.outcome}
    >
      <span
        className="block break-words text-[10.5px] font-semibold uppercase leading-snug tracking-wide text-muted-foreground"
        data-testid="policy-highlight-label"
      >
        {norm.label}
      </span>
      <span
        className="mt-0.5 block min-w-0 break-words leading-snug"
        data-testid="policy-highlight-fact"
      >
        <span
          className={cn(
            "tabular text-[12.5px] font-semibold",
            norm.outcome === "deviation"
              ? "text-destructive"
              : norm.outcome === "cannot_evaluate"
                ? "text-flag-foreground"
                : norm.outcome === "pass"
                  ? "text-foreground"
                  : "text-muted-foreground",
          )}
          data-testid="policy-highlight-value"
        >
          {actualText(norm)}
        </span>
        {/* The required value wraps as a whole, to the next line where the card is narrow. */}{" "}
        <span className="inline-block max-w-full text-[11px] text-muted-foreground">
          {"· "}
          <span className="tabular" data-testid="policy-highlight-required">
            {norm.required}
          </span>
        </span>
      </span>
      {note && (
        <span
          className="mt-0.5 block break-words text-[11.5px] leading-snug text-muted-foreground"
          data-testid="policy-highlight-note"
        >
          {note}
        </span>
      )}
      <span className="sr-only"> ({t(`policy.outcome.${norm.outcome}`)})</span>
    </button>
  );
}

type AuthorityState = "determined" | "cannot_determine" | "not_published" | "error" | "loading";

function authorityState(query: UseQueryResult<ApprovingAuthority>): AuthorityState {
  const a = query.data;
  if (a) return a.outcome === "determined" && a.required ? "determined" : "cannot_determine";
  if (matrixNotPublished(query.error)) return "not_published";
  return query.isError ? "error" : "loading";
}

const AUTHORITY_BAR: Record<AuthorityState, string> = {
  determined: "border-t-primary",
  cannot_determine: "border-t-flag",
  not_published: "border-t-muted-foreground/40",
  error: "border-t-muted-foreground/40",
  loading: "border-t-muted-foreground/40",
};

/** The approving authority in brief: who must approve and at what level, "at least" while norms
 * remain to be assessed (and whether they could raise it), the authority the amount calls for and
 * the deviation steps; or why there is none to show. */
function AuthorityCard({
  query,
  onOpen,
}: {
  query: UseQueryResult<ApprovingAuthority>;
  onOpen: () => void;
}) {
  const id = useId();
  const labels = useLabels();
  const state = authorityState(query);
  const a = query.data;
  return (
    <div
      className={cn(card, AUTHORITY_BAR[state], "@min-[30rem]:col-span-2 @min-[62rem]:col-span-1")}
      data-testid="policy-authority-card"
      data-status={state}
    >
      <div className="min-w-0 px-3 pt-3">
        <div className="flex min-w-0 items-start gap-1.5">
          <Scale className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
          <button
            type="button"
            onClick={onOpen}
            aria-controls={AUTHORITY_SECTION_ID}
            aria-describedby={`${id}-required`}
            className={openSectionButton}
            data-testid="policy-authority-open-section"
          >
            {t("approvingAuthority.title")}
          </button>
        </div>
        <p className="mt-0.5 break-words text-[11.5px] leading-snug text-muted-foreground">
          {t("policy.authorityCard.purpose")}
        </p>
      </div>

      <div id={`${id}-required`} className="min-w-0 px-3 pt-3">
        {state === "determined" && a?.required ? (
          <>
            <p
              className="break-words text-[15px] font-semibold leading-snug text-foreground"
              data-testid="policy-authority-required"
            >
              {a.required.label}
            </p>
            <p className="mt-1 flex flex-wrap items-center gap-1.5">
              <Chip tone="info">
                <span data-testid="policy-authority-level">
                  {t("approvingAuthority.level", { n: a.required.level })}
                </span>
              </Chip>
              {a.lower_bound && (
                <Chip tone="flag">
                  <span data-testid="policy-authority-at-least">
                    {t("policy.authorityCard.atLeast")}
                  </span>
                </Chip>
              )}
              {a.provisional && <ProvisionalChip />}
            </p>
            {a.lower_bound && a.unevaluated.length > 0 && (
              <p
                className="mt-1 break-words text-[11.5px] leading-snug text-muted-foreground"
                data-testid="policy-authority-rise"
                data-rises={authorityRises(a) ? "true" : "false"}
              >
                {authorityRises(a) && a.could_rise_to
                  ? t("policy.authorityCard.couldRise", {
                      authority: a.could_rise_to.label,
                      level: a.could_rise_to.level,
                      norms: joinList(a.unevaluated_labels ?? a.unevaluated),
                    })
                  : t("policy.authorityCard.wouldNotRise", {
                      norms: joinList(a.unevaluated_labels ?? a.unevaluated),
                    })}
              </p>
            )}
          </>
        ) : state === "cannot_determine" && a ? (
          <>
            <p
              className="text-[13px] font-medium leading-snug text-flag-foreground"
              data-testid="policy-authority-unavailable"
            >
              {t("policy.authorityCard.cannotDetermine")}
            </p>
            <p className="mt-1 break-words text-[11.5px] leading-snug text-muted-foreground">
              {t("approvingAuthority.cannotDetermine.no_product", {
                facilities: labels.facilities(a.unmapped_facilities ?? []),
              })}
            </p>
            {a.provisional && (
              <p className="mt-1">
                <ProvisionalChip />
              </p>
            )}
          </>
        ) : state === "loading" ? (
          <div className="space-y-2" role="status" aria-label={t("state.loading")}>
            <Skeleton className="h-4 w-40 max-w-full" />
            <Skeleton className="h-4 w-24" />
          </div>
        ) : (
          <p
            className="break-words text-[13px] font-medium leading-snug text-muted-foreground"
            data-testid="policy-authority-unavailable"
          >
            {state === "not_published"
              ? t("policy.authorityCard.notPublished")
              : t("policy.authorityCard.failed")}
          </p>
        )}
      </div>

      <div className="min-w-0 px-3 pb-2.5 pt-2">
        {state === "determined" && a && <AuthorityBasis authority={a} />}
      </div>
    </div>
  );
}

function ProvisionalChip() {
  return (
    <Chip tone="muted">
      <span data-testid="policy-authority-provisional">{t("approvingAuthority.provisional")}</span>
    </Chip>
  );
}

const STEPS_SLOT = "\u0000";

/** The authority the amount bands call for, and each deviation step in a few words, the one that
 * decides in bold. */
function AuthorityBasis({ authority }: { authority: ApprovingAuthority }) {
  const amounts = amountAuthorities(authority);
  const steps = deviationSteps(authority);
  const [before, after] = t("policy.authorityCard.deviations", { steps: STEPS_SLOT }).split(
    STEPS_SLOT,
  );
  return (
    <div className="space-y-1 border-t border-border pt-1.5 text-[11.5px] leading-snug text-muted-foreground">
      {amounts.length > 0 && (
        <p className="break-words" data-testid="policy-authority-amount">
          {t("policy.authorityCard.amount", {
            authorities: amounts.map(authorityName).join(", "),
          })}
        </p>
      )}
      <p className="break-words" data-testid="policy-authority-deviations">
        {steps.length === 0 ? (
          t("policy.authorityCard.noDeviation")
        ) : (
          <>
            {before}
            {steps.map((step, i) => (
              <span key={step.rule}>
                {i > 0 && " · "}
                <span
                  className={cn(step.governs && "font-medium text-foreground")}
                  data-governs={step.governs ? "true" : "false"}
                >
                  {deviationStepShort(step)}
                </span>
              </span>
            ))}
            {after}
          </>
        )}
      </p>
    </div>
  );
}
