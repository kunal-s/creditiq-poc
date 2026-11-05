import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  FileQuestion,
  Minus,
  MinusCircle,
  OctagonX,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { ChecklistStatus } from "@/api/types";
import type { Tone } from "@/components/common/Panel";
import { t } from "@/config/terminology";
import type { Band, Filter } from "@/domain/checklist";

// One glyph and one colour a status, shared by the verdict, the blocker chips, the tiles, the
// section cells, the band headers and the rows, so a status reads the same wherever it shows.

export const ICON: Record<ChecklistStatus, LucideIcon> = {
  satisfied: CheckCircle2,
  insufficient: AlertTriangle,
  missing: XCircle,
  in_review: Clock,
  waived: MinusCircle,
};

export const ICON_TONE: Record<ChecklistStatus, string> = {
  satisfied: "text-positive",
  insufficient: "text-flag-foreground",
  missing: "text-destructive",
  in_review: "text-info",
  waived: "text-muted-foreground",
};

export const TONE: Record<ChecklistStatus, Tone> = {
  satisfied: "positive",
  insufficient: "flag",
  missing: "critical",
  in_review: "info",
  waived: "muted",
};

export const CELL_ICON: Record<ChecklistStatus, LucideIcon> = {
  satisfied: Check,
  waived: Minus,
  in_review: Clock,
  insufficient: AlertTriangle,
  missing: X,
};

/** A section-map cell: solid when done, soft when on file, hollow when missing. The borders are
 * full strength so each shape stands out from the page. */
export const CELL: Record<ChecklistStatus, string> = {
  satisfied: "bg-positive text-primary-foreground",
  waived: "border border-dashed border-muted-foreground bg-surface text-muted-foreground",
  in_review: "border border-info bg-info-soft text-info",
  insufficient: "border border-flag bg-flag-soft text-flag-foreground",
  missing: "border-[1.5px] border-destructive bg-surface text-destructive",
};

export type BandKey = Band | "unmatched";

export const BAND: Record<
  BandKey,
  { rule: string; glyph: LucideIcon; tone: string; pill: string }
> = {
  blocking: {
    rule: "border-l-destructive",
    glyph: OctagonX,
    tone: "text-destructive",
    pill: "bg-destructive text-destructive-foreground",
  },
  nonblocking: {
    rule: "border-l-flag",
    glyph: AlertTriangle,
    tone: "text-flag-foreground",
    pill: "border border-flag/50 bg-flag-soft text-flag-foreground",
  },
  inreview: {
    rule: "border-l-info",
    glyph: Clock,
    tone: "text-info",
    pill: "bg-info-soft text-info",
  },
  done: {
    rule: "border-l-positive",
    glyph: CheckCircle2,
    tone: "text-positive",
    pill: "bg-positive-soft text-positive",
  },
  unmatched: {
    rule: "border-l-border",
    glyph: FileQuestion,
    tone: "text-muted-foreground",
    pill: "bg-muted text-muted-foreground",
  },
};

/** The name of a filter, as its tile says it. */
export function filterLabel(f: Exclude<Filter, "all">): string {
  switch (f) {
    case "blocking":
      return t("console.kpi.blocking");
    case "todo":
      return t("console.outstanding");
    case "in_review":
      return t("docStatus.in_review");
    case "satisfied":
      return t("docStatus.satisfied");
  }
}
