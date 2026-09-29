import type {
  ChecklistStatus,
  DocumentStatus,
  FieldStatus,
  FileStatus,
  Grade,
  ProposedStatus,
} from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { t } from "@/config/terminology";

const GRADE_TONE: Record<Grade, Tone> = { A: "positive", B: "info", C: "flag", U: "critical" };

export function GradeChip({ grade }: { grade: Grade }) {
  return (
    <Chip tone={GRADE_TONE[grade]} title={t(`qualityGrade.${grade}`)}>
      <span className="tabular font-semibold">{grade}</span>
      <span className="hidden sm:inline">{t(`qualityGrade.${grade}`)}</span>
    </Chip>
  );
}

const FILE_TONE: Record<FileStatus, Tone> = {
  registered: "positive",
  duplicate: "muted",
  ignored: "muted",
  rejected: "critical",
  exception: "flag",
};

export function FileStatusChip({ status }: { status: FileStatus }) {
  return <Chip tone={FILE_TONE[status]}>{t(`fileStatus.${status}`)}</Chip>;
}

const DOC_TONE: Record<DocumentStatus, Tone> = {
  received: "muted",
  graded: "info",
  split: "info",
  classified: "info",
  unclassified: "flag",
  extracted: "primary",
  accepted: "positive",
  in_review: "flag",
  in_exception: "critical",
  superseded: "muted",
  duplicate: "muted",
};

export function DocStatusChip({ status }: { status: DocumentStatus }) {
  return <Chip tone={DOC_TONE[status]}>{t(`documentStatus.${status}`)}</Chip>;
}

const CHECKLIST_TONE: Record<ChecklistStatus, Tone> = {
  satisfied: "positive",
  insufficient: "flag",
  missing: "critical",
  in_review: "primary",
  waived: "muted",
};

export function ChecklistStatusChip({ status }: { status: ChecklistStatus }) {
  return (
    <Chip tone={CHECKLIST_TONE[status]} className="shrink-0">
      <span data-testid="checklist-status">{t(`docStatus.${status}`)}</span>
    </Chip>
  );
}

const FIELD_TONE: Record<FieldStatus, Tone> = {
  accepted: "positive",
  in_review: "flag",
  corrected: "primary",
  missing: "muted",
  rejected: "critical",
};

export function FieldStatusChip({ status }: { status: FieldStatus }) {
  return <Chip tone={FIELD_TONE[status]}>{t(`fieldStatus.${status}`)}</Chip>;
}

const PROPOSED_TONE: Record<ProposedStatus, Tone> = {
  found: "positive",
  unclear: "flag",
  not_found: "muted",
  invalid: "critical",
};

export function ProposedStatusChip({ status }: { status: ProposedStatus }) {
  return (
    <Chip tone={PROPOSED_TONE[status]}>
      <span data-testid="proposed-status">{t(`proposedStatus.${status}`)}</span>
    </Chip>
  );
}
