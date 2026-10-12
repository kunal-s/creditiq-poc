import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  ClipboardCheck,
  type LucideIcon,
} from "lucide-react";
import type {
  FindingOutcome,
  FindingSeverity,
  Provenance,
  XvAreaStatus,
  XvDecisionKind,
} from "@/api/types";
import type { Tone } from "@/components/common/Panel";

// The board's colours: severity in red, amber and blue, as on the rest of the case.

export const SEVERITY_TONE: Record<FindingSeverity, Tone> = {
  serious: "critical",
  moderate: "flag",
  mild: "info",
};

export const SEVERITY_BAR: Record<FindingSeverity, string> = {
  serious: "bg-destructive",
  moderate: "bg-flag",
  mild: "bg-info",
};

/** An area's status: red while a discrepancy is open, neutral once every one is decided, amber
 * when nothing differs but a check could not run, green when everything checked agrees. */
export const AREA_STATUS: Record<XvAreaStatus, { icon: LucideIcon; text: string; bar: string }> = {
  open: { icon: AlertTriangle, text: "text-destructive", bar: "border-t-destructive" },
  decided: {
    icon: ClipboardCheck,
    text: "text-muted-foreground",
    bar: "border-t-muted-foreground/60",
  },
  incomplete: { icon: CircleDashed, text: "text-flag", bar: "border-t-flag" },
  clear: { icon: CheckCircle2, text: "text-positive", bar: "border-t-positive" },
};

/** A key figure's mark on the overview, by where its finding stands: red while its discrepancy
 * is open, grey once decided, amber for a check that could not run, green for one that passed. */
export function highlightMark(outcome: FindingOutcome, decided: boolean): string {
  if (outcome === "fail") return decided ? "border-l-muted-foreground/50" : "border-l-destructive";
  if (outcome === "incomplete") return "border-l-flag";
  if (outcome === "pass") return "border-l-positive";
  return "border-l-border";
}

/** Accepted: the finding stands; dismissed: cleared; escalated: open, with the Credit Manager. */
export const DECISION_TONE: Record<XvDecisionKind, Tone> = {
  accept: "flag",
  dismiss: "positive",
  escalate: "info",
};

export const PROVENANCE_TONE: Record<Provenance, Tone> = {
  independent: "positive",
  borrower_supplied: "muted",
  declared: "muted",
};

export const headerButton =
  "inline-flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted";

/** The heading of a part of an area's section: could not be checked, passed, facts. */
export const subsectionTitle = "text-[13px] font-semibold text-foreground";

/** The row of a check that could not run, passed or did not apply: a key figure on the overview
 * scrolls to it and focuses it, and the row stays marked (data-target) until the focus leaves. */
export const checkRow =
  "scroll-mt-4 outline-none transition-colors data-[target]:bg-accent focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring";
