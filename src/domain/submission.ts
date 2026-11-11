import type { Cam, CrossVerificationView, Readiness } from "@/api/types";
import { readyForCredit } from "@/domain/checklist";

// What must hold before the memo leaves the analyst's desk, read from the case as it stands. The
// Submission step lists these checks; the Overview's case progress reads the same ones, so the two
// never disagree.

export type SubmissionCheckKey = "serious" | "advisory" | "readiness" | "recommendation";

export type SubmissionState = {
  /** Blocking discrepancies nobody has decided. */
  blockingOpen: number;
  /** Discrepancies (checks that failed) that do not block and nobody has decided. */
  advisoryOpen: number;
  /** Checks that could not run, for want of a document. */
  notRun: number;
  readiness: boolean;
  recommendation: boolean;
  /** The checks that block submission and are not met. */
  unmet: SubmissionCheckKey[];
};

export function submissionState(
  board: CrossVerificationView,
  checklist: Readiness,
  cam: Cam,
): SubmissionState {
  // Open means a discrepancy (a check that failed) nobody has decided; a check that passed is not
  // a finding, and one that could not run is said apart.
  const advisoryOpen = board.items.filter(
    (i) => i.finding.outcome === "fail" && !i.adjudicated && !i.finding.blocking,
  ).length;
  const notRun = board.items.filter((i) => i.finding.outcome === "incomplete").length;
  const blockingOpen = board.counts.blocking_open;
  const readiness = readyForCredit(checklist);
  const recommendation =
    cam.recommendation.trim() !== "" ||
    (cam.recommendation_review?.state ?? "machine") !== "machine";
  const unmet: SubmissionCheckKey[] = [];
  if (blockingOpen > 0) unmet.push("serious");
  if (!readiness) unmet.push("readiness");
  if (!recommendation) unmet.push("recommendation");
  return { blockingOpen, advisoryOpen, notRun, readiness, recommendation, unmet };
}

/** The memo's sections as Outputs counts them (the drafted ones, then the risk assessment and the
 * recommendation that close it), and how many are in a person's words. */
export function memoSections(cam: Cam): { total: number; edited: number } {
  const reviews = [
    ...cam.sections.map((s) => s.review),
    cam.summary_review,
    cam.recommendation_review,
  ];
  return {
    total: cam.sections.length + 2,
    edited: reviews.filter((r) => r?.state && r.state !== "machine").length,
  };
}
