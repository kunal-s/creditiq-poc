import type { ReviewKind } from "@/api/types";

/** The case screen where a review item's evidence is read. */
export function reviewItemPath(kind: ReviewKind, caseId: string): string {
  const id = encodeURIComponent(caseId);
  switch (kind) {
    case "type":
    case "quality":
    case "split":
      return `/docready/${id}/validation`;
    case "party":
      return `/appraisals/${id}/identity`;
    case "field":
    case "manual_entry":
      return `/appraisals/${id}/data`;
    case "finding":
      return `/appraisals/${id}/cross-verification`;
  }
}
