import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import type { CrossVerificationView, FindingArea } from "@/api/types";
import { QueryView } from "@/components/common/States";
import { EmptyState } from "@/components/shell/EmptyState";
import { t } from "@/config/terminology";
import {
  areaHeadingId,
  areaItems,
  areaSectionId,
  areasOf,
  cardElementId,
  checkElementId,
  itemById,
  itemByLink,
  scrollBehavior,
  useCrossVerification,
} from "@/domain/crossVerification";
import { AreaOverview } from "./AreaOverview";
import { AreaSection } from "./AreaSection";
import { BlockingBanner } from "./BlockingBanner";
import { BoardHeader } from "./BoardHeader";
import { SeverityTiles } from "./SeverityTiles";

// The Cross-checks tab: the cross-verification board (F-19; docs/cross-verification-logic.md).
// Every source lined up against every other, from GET /api/cases/{id}/cross-verification, by
// area (identity, turnover, bank accounts, existing obligations: the areas the enabled rules
// cover, in the engine's order). An overview card per area says where it stands, with up to
// three key figures the engine picked from its findings (the two PANs, the turnover in crores,
// an account without a statement, a lender's amounts), each opening its finding; a section per
// area holds its discrepancies ranked by credit impact within the area, each with its sources
// side by side, the gap on each leg, the rows and pages behind every figure, and a decision;
// then what could not be checked, what passed, and the facts the checks compared (F-18). The
// engine decides, measures, ranks and counts; the board shows its view as given and never
// recomputes it.
//
// Test ids (data-testid):
//   xv-board                 the board
//   xv-header                the tab's header: xv-summary-line, xv-meta-line (the decisions
//                            made and the run), and the buttons xv-back-spread,
//                            xv-exception-queue and xv-continue (aria-disabled="true", no href,
//                            while submission is blocked)
//   xv-banner                the blocking banner; xv-adjudicate-now (data-target) scrolls to and
//                            expands the engine's first_blocking discrepancy
//   xv-overview              the area cards: xv-area-card-<area> each (data-status
//                            open|decided|incomplete|clear), opening its section from
//                            xv-area-open-section (a button whose surface covers the card), with
//                            xv-area-open (the open discrepancies), xv-area-severity,
//                            xv-area-blocking, xv-area-decided, xv-area-others (could not be
//                            checked, passed, not applicable), xv-area-top, and the engine's key
//                            figures xv-area-highlights: an xv-area-highlight button each
//                            (data-rule, data-outcome, data-finding; opens its finding's card or
//                            row) with xv-highlight-label, xv-highlight-fact (data-differs; its
//                            xv-highlight-value) and xv-highlight-note
//   xv-area-<area>           an area's section (also its element id; data-status), headed by the
//                            area's title (focused when its card is clicked) and xv-area-counts;
//                            then xv-discrepancies (or xv-area-none), xv-incomplete, xv-passed
//                            and xv-facts
//   xv-card-<finding id>     a discrepancy (also its element id, for scrolling), with
//                            data-expanded="true|false", data-rank (within its area), data-rule,
//                            data-severity and data-adjudicated; inside it xv-card-toggle,
//                            xv-rank, xv-rule-line
//   xv-column-<key>          a source column (data-active, data-differs): xv-column-value
//                            (xv-diff marks each character differing from the reference),
//                            xv-open-evidence, xv-trace, xv-awaiting-review
//   xv-gap-row               the gap strip: an xv-gap-leg per leg (data-breached) and
//                            xv-tolerance-line; xv-mismatch instead for a check without amounts
//   xv-evidence-panel        the rows behind the active column (data-column): an
//                            xv-evidence-row per row (data-kind="row|total|excluded"), each
//                            with its page button xv-evidence-page
//   xv-line-by-line          the finding's line-by-line detail (closed): xv-detail-table
//   xv-adjudication          the decision form: radio inputs xv-decision-accept,
//                            xv-decision-dismiss and xv-decision-escalate, xv-comment,
//                            xv-save-decision, xv-decision-error (the server's message),
//                            xv-waiting-manager, xv-read-only
//   xv-recorded-decision     an accepted or dismissed discrepancy (data-decision), with
//                            xv-no-comment when it was recorded without one
//   xv-escalation-note       who escalated it, when and why
//   xv-incomplete            an area's checks that could not run: an xv-incomplete-row each
//                            (data-rule; element id xv-check-<finding id>), with xv-request,
//                            xv-add-query or xv-on-query-list, xv-awaiting-review,
//                            xv-add-documents, xv-query-error
//   xv-passed                an area's passed checks (a closed details element): xv-passed-row
//                            and xv-not-applicable-row (data-rule; element id
//                            xv-check-<finding id>)
//   xv-facts                 the facts behind an area's checks (a closed details element; the
//                            panels facts-identity, facts-people, facts-turnover,
//                            facts-accounts, facts-credits, facts-obligations)
//
// A link from the draft CAM or the PD note (?finding=, a finding id or its XV reference) opens
// the board at that finding once it has loaded: a discrepancy's card open and focused, as
// Adjudicate now leaves it, or any other check's row, as a key figure leaves it.

export function CrossVerificationBoard({
  caseId,
  finding,
}: {
  caseId: string;
  /** The finding a link names, to open the board at. */
  finding?: string | undefined;
}) {
  const board = useCrossVerification(caseId);
  return (
    <div className="min-w-0 pb-10" data-testid="xv-board">
      <BoardHeader caseId={caseId} view={board.data} />
      <div className="min-w-0 space-y-6 px-4 py-5 sm:px-6">
        <QueryView query={board}>
          {(view) => <BoardBody caseId={caseId} view={view} linkedTo={finding} />}
        </QueryView>
      </div>
    </div>
  );
}

/** Scroll a discrepancy's card to the top and focus its toggle. */
function focusCard(id: string) {
  const card = document.getElementById(cardElementId(id));
  card?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
  card
    ?.querySelector<HTMLElement>('[data-testid="xv-card-toggle"]')
    ?.focus({ preventScroll: true });
}

/** Scroll to the row of a check that could not run, passed or did not apply, opening the passed
 * checks if it is among them, and focus it. */
function focusRow(id: string) {
  const row = document.getElementById(checkElementId(id));
  if (!row) return;
  const list = row.closest("details");
  if (list && !list.open) list.open = true;
  row.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
  // Marked as the row opened until the reader moves on.
  row.setAttribute("data-target", "true");
  row.addEventListener("blur", () => row.removeAttribute("data-target"), { once: true });
  row.focus({ preventScroll: true });
}

function BoardBody({
  caseId,
  view,
  linkedTo,
}: {
  caseId: string;
  view: CrossVerificationView;
  linkedTo?: string | undefined;
}) {
  const linked = itemByLink(view, linkedTo);
  const linkedId = linked?.finding.id ?? null;
  const linkedFails = linked?.finding.outcome === "fail";
  // The first card on the board (the engine's top_finding_id) is open when the board loads; a
  // link opens it at the card it names instead, or with every card closed at a check's row.
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => {
    const open = linked ? (linkedFails ? linkedId : null) : view.top_finding_id;
    return new Set(open ? [open] : []);
  });
  const toggle = (id: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const adjudicateNow = (id: string) => {
    flushSync(() => setExpanded((current) => new Set(current).add(id)));
    focusCard(id);
  };
  const openArea = (area: FindingArea) => {
    document
      .getElementById(areaSectionId(area))
      ?.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
    document.getElementById(areaHeadingId(area))?.focus({ preventScroll: true });
  };
  // A key figure opens its finding: a discrepancy's card, as Adjudicate now does; any other
  // finding's row.
  const openFinding = (id: string) => {
    const item = itemById(view, id);
    if (!item) return;
    if (item.finding.outcome === "fail") adjudicateNow(id);
    else focusRow(id);
  };

  // The linked finding is shown once, when its card is open (the card the board opened with, or
  // one opened for a link followed while the board is open), and a frame later: once the router
  // has scrolled the page it rendered to the top.
  const shown = useRef<string | null>(null);
  useEffect(() => {
    if (!linkedId || shown.current === linkedId) return;
    if (linkedFails && !expanded.has(linkedId)) {
      setExpanded((current) => new Set(current).add(linkedId));
      return;
    }
    const frame = requestAnimationFrame(() => {
      shown.current = linkedId;
      if (linkedFails) focusCard(linkedId);
      else focusRow(linkedId);
    });
    return () => cancelAnimationFrame(frame);
  }, [linkedId, linkedFails, expanded]);

  if (view.items.length === 0) {
    return (
      <EmptyState
        title={t("crossVerification.emptyTitle")}
        description={t("crossVerification.emptyDescription")}
      />
    );
  }
  return (
    <>
      <BlockingBanner view={view} onAdjudicate={adjudicateNow} />
      <SeverityTiles view={view} />
      <AreaOverview view={view} onOpen={openArea} onOpenFinding={openFinding} />
      {areasOf(view).map((area) => (
        <AreaSection
          key={area.area}
          caseId={caseId}
          area={area}
          items={areaItems(view, area.area)}
          expanded={expanded}
          onToggle={toggle}
        />
      ))}
    </>
  );
}
