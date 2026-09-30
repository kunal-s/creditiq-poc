import type { ReviewKind } from "@/api/types";

/** The case screen where a review item's evidence is read. */
export function reviewItemPath(kind: ReviewKind, caseId: string): string {
  const id = encodeURIComponent(caseId);
  switch (kind) {
    case "type":
    case "quality":
    case "split":
      return `/appraisals/${id}/documents`;
    case "party":
      return `/appraisals/${id}/extraction`;
    case "field":
    case "manual_entry":
      return `/appraisals/${id}/extraction`;
    case "finding":
      return `/appraisals/${id}/cross-verification`;
  }
}
