import type { UseQueryResult } from "@tanstack/react-query";
import { useRouterState } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import type { ApprovingAuthority, PolicyAssessment } from "@/api/types";
import { QueryView } from "@/components/common/States";
import { FinancialsSection } from "@/components/case/spread/FinancialsSection";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";
import { useCrossVerification } from "@/domain/crossVerification";
import { useFacts, useSpread } from "@/domain/findings";
import {
  FINANCIALS_HEADING_ID,
  FINANCIALS_SECTION_ID,
  AUTHORITY_HEADING_ID,
  AUTHORITY_SECTION_ID,
  familyNorms,
  groupHeadingId,
  groupSectionId,
  groupsOf,
  openNorm,
  openSection,
  useApprovingAuthority,
  usePolicy,
} from "@/domain/policy";
import { AuthoritySection } from "./AuthoritySection";
import { GroupSection } from "./GroupSection";
import { PolicyHeader } from "./PolicyHeader";
import { PolicyOverview } from "./PolicyOverview";

// The Financials and Policy tab (FRD §6, F-20, F-21, F-22): the spread, turnover by year and the
// working-capital assessment (the Financials section, FinancialsSection); then every norm with
// the required and the actual value, the figures it used with their pages, and whether it passed, deviated or cannot be evaluated;
// and the approving authority those deviations call for. An overview card per family of norms
// (eligibility, financial ratios, documentation, security cover: the engine's groups, in its
// order) says where it stands, with its counts and up to three norms the engine picked; one more
// card says who must approve. A section per family holds its norms; the last holds the authority
// with every step of the matrix that applied. The engine evaluates, counts and groups; the page
// shows its assessment as given and never recounts it. The deviations, by category, are what the
// CAM summarises (F-20.4).
//
// Test ids (data-testid):
//   policy-page                 the tab
//   policy-header               the tab's header: policy-summary-line (the engine's counts, the
//                               period, provisional norms) and policy-interim (the norms are
//                               interim proposals)
//   policy-overview             the cards: policy-group-card-<family> each (data-status
//                               deviation|cannot_evaluate|clear|no_norms), opening its section from
//                               policy-group-open-section (a button whose surface covers the card),
//                               with policy-group-deviations, policy-group-others (cannot be
//                               evaluated, passed, not applicable), policy-group-none and
//                               policy-group-pending (a family with no norm), and the engine's key
//                               norms policy-group-highlights: a policy-highlight button each
//                               (data-norm, data-outcome; opens the norm's row) with
//                               policy-highlight-label, policy-highlight-fact (its
//                               policy-highlight-value and policy-highlight-required) and
//                               policy-highlight-note (what is missing)
//   policy-authority-card       the authority's card (data-status determined|cannot_determine|
//                               not_published|error|loading), opening its section from
//                               policy-authority-open-section, with policy-authority-provisional,
//                               policy-authority-required, policy-authority-level,
//                               policy-authority-at-least, policy-authority-rise (data-rises),
//                               policy-authority-amount, policy-authority-deviations and
//                               policy-authority-unavailable
//   financials                  the Financials section, after the overview (see FinancialsSection)
//   policy-group-<family>       a family's section (also its element id; data-status), headed by
//                               the family's title (focused when its card is clicked) and
//                               policy-group-counts; then policy-norms (or family-pending)
//   norm                        a norm's row (data-norm, data-outcome; element id
//                               policy-norm-<id>): norm-actual, norm-reason, norm-missing,
//                               norm-input (norm-input-checklist, norm-input-basis,
//                               norm-input-awaiting), norm-details (norm-definition, norm-note)
//   policy-authority            the authority's section: approving-authority (authority-required,
//                               authority-provisional, authority-lower-bound, authority-how with an
//                               authority-step each and its authority-norm links,
//                               authority-compare) or authority-not-published
//
// A link from the draft CAM or the PD note (?norm=) opens the page at that norm's row, as a key
// norm does, once the norms and the authority beside them have loaded.

export function PolicyPage({
  caseId,
  norm,
}: {
  caseId: string;
  /** The norm a link names, to open the page at. */
  norm?: string | undefined;
}) {
  const policy = usePolicy(caseId);
  const authority = useApprovingAuthority(caseId);
  return (
    <div className="min-w-0 pb-10" data-testid="policy-page">
      <PolicyHeader caseId={caseId} policy={policy.data} />
      {/* The norms read as a list, so the content keeps a bounded measure: on a wide window
          the required and actual values stay beside the norm they belong to instead of being
          pushed to the far edge. */}
      <div className="min-w-0 max-w-6xl space-y-6 px-4 py-5 sm:px-6">
        <QueryView query={policy}>
          {(p) => <PolicyBody caseId={caseId} policy={p} authority={authority} linkedTo={norm} />}
        </QueryView>
      </div>
    </div>
  );
}

function PolicyBody({
  caseId,
  policy,
  authority,
  linkedTo,
}: {
  caseId: string;
  policy: PolicyAssessment;
  authority: UseQueryResult<ApprovingAuthority>;
  linkedTo?: string | undefined;
}) {
  // The authority's card and the Financials section sit above the rows, so the linked norm is
  // opened once they have loaded (or could not be had), only once, and a frame later: once the
  // router has scrolled the page it rendered to the top.
  const linked = policy.norms.some((n) => n.id === linkedTo) ? (linkedTo ?? null) : null;
  const spread = useSpread(caseId);
  const facts = useFacts(caseId);
  const board = useCrossVerification(caseId);
  const settled = !authority.isLoading && !spread.isLoading && !facts.isLoading && !board.isLoading;
  const shown = useRef<string | null>(null);
  useEffect(() => {
    if (!linked || !settled || shown.current === linked) return;
    const frame = requestAnimationFrame(() => {
      shown.current = linked;
      openNorm(linked);
    });
    return () => cancelAnimationFrame(frame);
  }, [linked, settled]);

  // A link to the Financials section (#financials: the board's Spread button, an earlier spread
  // link) is opened the same way, once the cards above it have settled.
  const hash = useRouterState({ select: (state) => state.location.hash });
  const opened = useRef<string | null>(null);
  useEffect(() => {
    // The browser's own hash: a server-rendered first load does not carry it in the router's
    // location; a later link does, and re-runs this.
    const current = window.location.hash.slice(1);
    if (current !== FINANCIALS_SECTION_ID || !settled || opened.current === `${hash}|${current}`)
      return;
    const frame = requestAnimationFrame(() => {
      opened.current = `${hash}|${current}`;
      openSection(FINANCIALS_SECTION_ID, FINANCIALS_HEADING_ID);
    });
    return () => cancelAnimationFrame(frame);
  }, [hash, settled]);

  if (policy.norms.length === 0) {
    return (
      <>
        <EmptyState title={t("policy.emptyTitle")} description={t("policy.emptyDescription")} />
        <FinancialsSection caseId={caseId} period={policy.period ?? null} />
      </>
    );
  }
  return (
    <>
      <PolicyOverview
        policy={policy}
        authority={authority}
        onOpenGroup={(group) =>
          openSection(groupSectionId(group.family), groupHeadingId(group.family))
        }
        onOpenAuthority={() => openSection(AUTHORITY_SECTION_ID, AUTHORITY_HEADING_ID)}
        onOpenNorm={openNorm}
      />
      {/* The figures first, then the norms that test them. */}
      <FinancialsSection caseId={caseId} period={policy.period ?? null} />
      {groupsOf(policy).map((group) => (
        <GroupSection
          key={group.family}
          caseId={caseId}
          group={group}
          norms={familyNorms(policy, group.family)}
        />
      ))}
      <AuthoritySection caseId={caseId} query={authority} />
    </>
  );
}
