import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type {
  ColumnUnit,
  CrossVerificationView,
  Finding,
  FindingArea,
  FindingOutcome,
  FindingSeverity,
  SourceColumn,
  XvArea,
  XvDecisionRequest,
  XvFact,
  XvHighlight,
  XvItem,
} from "@/api/types";
import { t } from "@/config/terminology";
import { formatDate, formatInr } from "@/domain/cases";

// The cross-verification board (F-19; the Cross-checks tab). The engine decides every outcome,
// measures every gap, groups the findings by area, ranks the discrepancies within each area,
// counts each area and picks its key figures (engine/xv.py); the board shows them in the order
// given and never recomputes them. A decision or a query addition changes the banner, the counts,
// the areas, the stage progress, the query list and the review queue, so it refreshes all of
// them; so does a refusal, which means the board no longer matches the engine (a discrepancy
// decided or escalated meanwhile).

export const SEVERITIES: FindingSeverity[] = ["serious", "moderate", "mild"];

const boardKey = (caseId: string) => ["cases", caseId, "cross-verification"];

export function useCrossVerification(caseId: string) {
  return useQuery({
    queryKey: boardKey(caseId),
    queryFn: () => api.caseCrossVerification(caseId),
  });
}

/** Read again everything a decision or a query addition affects, as the engine now has it. */
function refresh(client: QueryClient, caseId: string) {
  for (const queryKey of [
    boardKey(caseId),
    ["cases", caseId, "progress"],
    ["cases", caseId, "queries"],
    ["cases", caseId, "findings"],
    ["review"],
  ]) {
    void client.invalidateQueries({ queryKey });
  }
}

/** Show the returned item at once, then refresh everything the change affects. */
function settle(client: QueryClient, caseId: string, item: XvItem) {
  client.setQueryData<CrossVerificationView>(boardKey(caseId), (view) =>
    view
      ? {
          ...view,
          items: view.items.map((i) =>
            i.finding.id === item.finding.id ? { ...item, rank: item.rank ?? i.rank ?? null } : i,
          ),
        }
      : view,
  );
  refresh(client, caseId);
}

/** Accept, dismiss or escalate a discrepancy, with the comment every decision needs. A refusal
 * (decided or escalated by someone else since the board loaded) reads the board again, so it
 * shows what the engine holds. */
export function useDecideFinding(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, body }: { findingId: string; body: XvDecisionRequest }) =>
      api.decideCrossVerification(caseId, findingId, body),
    onSuccess: (item) => settle(client, caseId, item),
    onError: () => refresh(client, caseId),
  });
}

/** Put what would complete a check that could not run on the pre-login query list (F-14). A
 * refusal (the check completed or changed since) reads the board again. */
export function useAddFindingQuery(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (findingId: string) => api.queryCrossVerification(caseId, findingId),
    onSuccess: (item) => settle(client, caseId, item),
    onError: () => refresh(client, caseId),
  });
}

/** The areas checked, in the engine's order (an older engine sends none). */
export function areasOf(view: CrossVerificationView): XvArea[] {
  return view.areas ?? [];
}

/** An area's key figures, as the engine picked them: up to three lines, from its open
 * discrepancies first. A card stored before the key figures existed has none. */
export function areaHighlights(area: XvArea): XvHighlight[] {
  return area.highlights ?? [];
}

/** One area's items in the engine's order: its discrepancies ranked within the area, then the
 * checks that could not run, those that passed and those that did not apply. */
export function areaItems(view: CrossVerificationView, area: FindingArea): XvItem[] {
  return view.items.filter((i) => i.finding.area === area);
}

/** The element ids of an area's section and of its heading: the area's card on the overview
 * scrolls to the one and focuses the other. */
export const areaSectionId = (area: FindingArea) => `xv-area-${area}`;
export const areaHeadingId = (area: FindingArea) => `xv-area-${area}-title`;

/** The element ids a key figure scrolls to: a discrepancy's card, or the row of a check that
 * could not run, passed or did not apply. */
export const cardElementId = (findingId: string) => `xv-card-${findingId}`;
export const checkElementId = (findingId: string) => `xv-check-${findingId}`;

/** The items with this outcome, in the order given. */
export function withOutcome(items: XvItem[], outcome: FindingOutcome): XvItem[] {
  return items.filter((i) => i.finding.outcome === outcome);
}

/** The item of this finding, if it is on the board. */
export function itemById(view: CrossVerificationView, findingId: string | null | undefined) {
  return findingId ? view.items.find((i) => i.finding.id === findingId) : undefined;
}

/** The item a link to the board names (?finding=, from the draft CAM or the PD note): by its
 * finding id, else by its board reference (XV-…), else the first check of that rule that did not
 * pass (a check that could not be completed has no reference). */
export function itemByLink(view: CrossVerificationView, key: string | null | undefined) {
  if (!key) return undefined;
  const items = view.items;
  return (
    items.find((i) => i.finding.id === key) ??
    items.find((i) => i.finding.ref === key) ??
    items.find(
      (i) =>
        i.finding.rule_id === key &&
        (i.finding.outcome === "fail" || i.finding.outcome === "incomplete"),
    ) ??
    items.find((i) => i.finding.rule_id === key)
  );
}

/** A discrepancy not yet accepted or dismissed; an escalated one stays open. */
export function isOpen(item: XvItem): boolean {
  return item.finding.outcome === "fail" && !item.adjudicated;
}

/** The open discrepancies that block submission. */
export function openBlocking(view: CrossVerificationView): XvItem[] {
  return view.items.filter((i) => isOpen(i) && i.finding.blocking);
}

/** The area's open discrepancies by severity, as the engine counted them: "2 serious · 1 mild". */
export function severityBreakdown(area: XvArea): string {
  return SEVERITIES.filter((s) => area[s] > 0)
    .map((s) => t(`crossVerification.count.${s}`, { n: area[s] }))
    .join(" · ");
}

/** Smooth scrolling, unless the reader asked for less motion. */
export function scrollBehavior(): ScrollBehavior {
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    ? "auto"
    : "smooth";
}

/** What the finding is, in plain words. */
export function findingTitle(f: Finding): string {
  return f.finding_title || f.compares || f.title;
}

/** What the rule compares (the rule's title). */
export function comparesText(f: Finding): string {
  return f.compares || f.title;
}

/** A figure as its unit reads: an amount in INR, a count with Indian grouping, a date as a date,
 * text as given. */
function formatFigure(v: string | number | null | undefined, unit: ColumnUnit | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return unit === "inr" ? formatInr(v) : v.toLocaleString("en-IN");
  if (unit === "date" && /^\d{4}-\d{2}-\d{2}/.test(v)) return formatDate(v);
  return v;
}

/** A source column's headline value as its unit reads: an amount in INR, a date as a date. */
export function columnValue(column: SourceColumn): string {
  return formatFigure(column.value, column.unit);
}

/** A key figure's value as its unit reads. */
export function factValue(fact: XvFact): string {
  return formatFigure(fact.value, fact.unit);
}

/** Whether a figure reads as an identifier (a PAN, GSTIN, CIN or account number: letters and
 * digits, no spaces), shown in monospace so its characters can be compared. */
export function isIdentifier(fact: XvFact): boolean {
  return (
    (fact.unit ?? "text") === "text" &&
    typeof fact.value === "string" &&
    /^(?=.*\d)[A-Za-z0-9]{5,}$/.test(fact.value)
  );
}

/** The columns whose pages the viewer shows side by side (F-16.2): those with a page, at most
 * three (the viewer's limit), the differing ones kept first, in the card's order. */
export function comparedColumns(f: Finding): SourceColumn[] {
  const traced = (f.columns ?? []).filter((c) => (c.evidence?.length ?? 0) > 0);
  const kept = [...traced.filter((c) => c.differs), ...traced.filter((c) => !c.differs)].slice(
    0,
    3,
  );
  return traced.filter((c) => kept.includes(c));
}

/** Whether the check waits for a person to review one of the values it compares. */
export function awaitsReview(f: Finding): boolean {
  return (f.columns ?? []).some((c) => c.awaiting_review) || f.sides.some((s) => s.awaiting_review);
}

/** Who holds the finding: whoever decided it, else whoever escalated it. */
export function ownerName(item: XvItem): string | null {
  return item.decision?.by_name || item.escalation?.by_name || null;
}

/** A record time, e.g. "09 Oct 2026, 14:30". */
export function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}

/** "a", "a and b", "a, b and c". */
export function joinList(items: string[]): string {
  const last = items[items.length - 1];
  if (items.length < 2 || last === undefined) return last ?? "";
  return t("crossVerification.join", { head: items.slice(0, -1).join(", "), last });
}

export type Segment = { text: string; differs: boolean };

/**
 * The parts of `value` that differ from `reference`, for marking an identifier against the value
 * most sources give. Same-length identifiers are compared position by position; anything else
 * is aligned on the longest common subsequence, so an inserted or dropped character marks only
 * itself. Case is ignored: the rules compare identifiers and names without it.
 */
export function diffSegments(value: string, reference: string): Segment[] {
  const chars = Array.from(value);
  const a = chars.map((ch) => ch.toLowerCase());
  const b = Array.from(reference, (ch) => ch.toLowerCase());
  const n = a.length;
  const m = b.length;
  let same: boolean[];
  if (n === m && !/\s/.test(value)) {
    same = a.map((ch, i) => ch === b[i]);
  } else if (n * m > 40_000) {
    same = new Array<boolean>(n).fill(false);
  } else {
    // lcs[i][j]: the longest common subsequence of a[i..] and b[j..].
    const lcs = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    const at = (i: number, j: number) => lcs[i]?.[j] ?? 0;
    for (let i = n - 1; i >= 0; i--) {
      const row = lcs[i]!;
      for (let j = m - 1; j >= 0; j--) {
        row[j] = a[i] === b[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1));
      }
    }
    same = new Array<boolean>(n).fill(false);
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        same[i] = true;
        i++;
        j++;
      } else if (at(i + 1, j) >= at(i, j + 1)) i++;
      else j++;
    }
  }
  const segments: Segment[] = [];
  chars.forEach((ch, i) => {
    const differs = !same[i];
    const tail = segments[segments.length - 1];
    if (tail && tail.differs === differs) tail.text += ch;
    else segments.push({ text: ch, differs });
  });
  return segments;
}
