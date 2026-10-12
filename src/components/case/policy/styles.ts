import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  HelpCircle,
  MinusCircle,
  type LucideIcon,
} from "lucide-react";
import type { NormOutcome, PolicyGroupStatus } from "@/api/types";

// The Policy checks tab's colours, as on the Cross-checks board: red for a deviation, amber for a
// norm that cannot be evaluated, green for one that passed, grey for nothing to assess.

/** A family's status: red when a norm deviates, amber when none does but one cannot be
 * evaluated, green when every norm passed or did not apply, neutral when it has no norm. */
export const GROUP_STATUS: Record<
  PolicyGroupStatus,
  { icon: LucideIcon; text: string; bar: string }
> = {
  deviation: { icon: AlertTriangle, text: "text-destructive", bar: "border-t-destructive" },
  cannot_evaluate: { icon: CircleDashed, text: "text-flag", bar: "border-t-flag" },
  clear: { icon: CheckCircle2, text: "text-positive", bar: "border-t-positive" },
  no_norms: {
    icon: MinusCircle,
    text: "text-muted-foreground",
    bar: "border-t-muted-foreground/40",
  },
};

export const OUTCOME_ICON: Record<NormOutcome, LucideIcon> = {
  deviation: AlertTriangle,
  cannot_evaluate: HelpCircle,
  pass: CheckCircle2,
  not_applicable: MinusCircle,
};

/** A norm's outcome in text: its icon and its actual value. */
export const OUTCOME_TEXT: Record<NormOutcome, string> = {
  deviation: "text-destructive",
  cannot_evaluate: "text-flag-foreground",
  pass: "text-positive",
  not_applicable: "text-muted-foreground",
};

/** A key figure's mark on the overview, by its norm's outcome. */
export const OUTCOME_MARK: Record<NormOutcome, string> = {
  deviation: "border-l-destructive",
  cannot_evaluate: "border-l-flag",
  pass: "border-l-positive",
  not_applicable: "border-l-border",
};
