import type { ChecklistStatus } from "@/api/types";
import type { Tone } from "@/components/common/Panel";

// One chip tone a status, shared by the document status list, the missing files and the
// requirement rows, so a status reads the same wherever it shows.

export const TONE: Record<ChecklistStatus, Tone> = {
  satisfied: "positive",
  insufficient: "flag",
  missing: "critical",
  in_review: "info",
  waived: "muted",
};
