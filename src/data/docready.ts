import { useSyncExternalStore } from "react";
import { t } from "@/config/terminology";

/* ------------------------------------------------------------------ types */

export type DocStatus =
  "not-requested" | "requested" | "received" | "rejected" | "accepted" | "waived";

export type Insufficiency = "stale" | "incomplete" | "inconsistent";

export type CheckOutcome = "pass" | "warn" | "fail";

export type ValidationCheck = {
  key: string;
  label: string;
  outcome: CheckOutcome;
  detail: string;
};

export type Section =
  "Constitution and KYC" | "Financials" | "Banking and operations" | "Collateral and security";

export const SECTION_WEIGHT: Record<Section, number> = {
  "Constitution and KYC": 20,
  Financials: 30,
  "Banking and operations": 30,
  "Collateral and security": 20,
};

export const SECTIONS: Section[] = [
  "Constitution and KYC",
  "Financials",
  "Banking and operations",
  "Collateral and security",
];

export type ChecklistItem = {
  id: string;
  name: string;
  category: Section;
  why: string;
  basis: string;
  blocking: boolean;
  status: DocStatus;
  weight: number;
  insufficiency?: Insufficiency | undefined;
  confidence?: number | undefined;
  ageDays?: number | undefined;
  remindersSent?: number | undefined;
  escalate?: boolean | undefined;
  fileName?: string | undefined;
  receivedAt?: string | undefined;
  receivedFrom?: string | undefined;
  pages?: string | undefined;
  checks?: ValidationCheck[] | undefined;
  rejection?: string | undefined;
  waiverReason?: string | undefined;
};

export type ChaseEvent = {
  id: string;
  at: string;
  actor: string;
  kind:
    | "request"
    | "reminder"
    | "upload"
    | "rejection"
    | "acceptance"
    | "call"
    | "waiver"
    | "handoff"
    | "escalation";
  title: string;
  detail: string;
  items?: string[] | undefined;
};

export type DocReadyCase = {
  id: string;
  borrower: string;
  slug: string;
  constitution: string;
  sector: string;
  segment: "Micro" | "Small" | "Medium";
  employees?: number | undefined;
  cin?: string | undefined;
  pan: string;
  gstin: string;
  udyam: string;
  product: string;
  facilities: string;
  requested: string;
  purpose?: string | undefined;
  branch: string;
  rm: string;
  owner: string;
  opened: string;
  lastContact: string;
  daysInCollection: number;
  targetSanction: string;
  existingRelationship?: string | undefined;
  contact: { name: string; role: string; phone: string; email: string };
  link?:
    | {
        sentAt: string;
        channels: string;
        opens: number;
        lastOpened: string;
        uploadsThroughLink: number;
      }
    | undefined;
  clearedBy?: string | undefined;
  clearedAt?: string | undefined;
  scoreOverride?: number | undefined;
  nextActions?: string[] | undefined;
  items: ChecklistItem[];
  chase: ChaseEvent[];
  handedOffTo?: string | undefined;
};

export const STAGE_GATES = [
  { label: t("readinessGates.creditReview"), threshold: 85 },
  { label: t("readinessGates.disbursement"), threshold: 100 },
];

export const REMINDER_CADENCE = {
  first: 3,
  second: 7,
  escalation: 12,
  channels: t("reminderCadence.channel"),
};

/* --------------------------------------------------------------- readiness */

export const STATUS_LABEL: Record<DocStatus, string> = {
  "not-requested": t("docStatus.notRequested"),
  requested: t("docStatus.missing"),
  received: t("docStatus.inReview"),
  rejected: t("docStatus.insufficient"),
  accepted: t("docStatus.satisfied"),
  waived: t("docStatus.waived"),
};

export const INSUFFICIENCY_LABEL: Record<Insufficiency, string> = {
  stale: t("docDefect.stale"),
  incomplete: t("docDefect.incomplete"),
  inconsistent: t("docDefect.inconsistent"),
};

export function readiness(c: DocReadyCase) {
  const settled = (s: DocStatus) => s === "accepted" || s === "waived";
  const weightTotal = c.items.reduce((n, i) => n + i.weight, 0);
  const weightDone = c.items.reduce(
    (n, i) => n + (settled(i.status) ? i.weight : i.status === "rejected" ? i.weight * 0.5 : 0),
    0,
  );
  const computed = weightTotal ? Math.round((weightDone / weightTotal) * 100) : 0;
  return {
    score: c.scoreOverride ?? computed,
    total: c.items.length,
    accepted: c.items.filter((i) => settled(i.status)).length,
    insufficient: c.items.filter((i) => i.status === "rejected").length,
    missing: c.items.filter((i) => i.status === "requested" || i.status === "not-requested").length,
    outstanding: c.items.filter((i) => !settled(i.status)).length,
    blockingOpen: c.items.filter((i) => i.blocking && !settled(i.status)).length,
    inReview: c.items.filter((i) => i.status === "received").length,
    reviewGate: (c.scoreOverride ?? computed) >= 85,
  };
}

/* ------------------------------------------------------------------- store */
// No cases exist yet in this deployment (Stage B's generator and, later, real
// intake create them) — the empty array here is the correct Stage A state,
// not a placeholder to fill in.

type State = { cases: DocReadyCase[] };

let state: State = { cases: [] };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const setCase = (id: string, fn: (c: DocReadyCase) => DocReadyCase) => {
  state = { cases: state.cases.map((c) => (c.id === id ? fn(c) : c)) };
  emit();
};
const log = (c: DocReadyCase, ev: Omit<ChaseEvent, "id">): DocReadyCase => ({
  ...c,
  chase: [...c.chase, { ...ev, id: `ev-${c.chase.length + 1}-${Date.now()}` }],
});

const nowIso = () => new Date().toISOString();

export const docReadyActions = {
  request(caseId: string, itemId: string, actor: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId ? { ...i, status: "requested" as DocStatus } : i,
        ),
      };
      return log(next, {
        at: nowIso(),
        actor,
        kind: "request",
        title: `Requested: ${item?.name ?? itemId}`,
        detail: `Added to the open ask on the collection link for ${c.contact.name}, sent by ${REMINDER_CADENCE.channels.toLowerCase()}.`,
        items: item ? [item.name] : undefined,
      });
    });
  },
  accept(caseId: string, itemId: string, actor: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId
            ? {
                ...i,
                status: "accepted" as DocStatus,
                rejection: undefined,
                insufficiency: undefined,
              }
            : i,
        ),
      };
      return log(next, {
        at: nowIso(),
        actor,
        kind: "acceptance",
        title: `Satisfied: ${item?.name ?? itemId}`,
        detail: "Cleared into the evidence set.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  reject(
    caseId: string,
    itemId: string,
    reason: string,
    actor: string,
    insufficiency: Insufficiency = "incomplete",
  ) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId
            ? { ...i, status: "rejected" as DocStatus, rejection: reason, insufficiency }
            : i,
        ),
      };
      return log(next, {
        at: nowIso(),
        actor,
        kind: "rejection",
        title: `Marked ${INSUFFICIENCY_LABEL[insufficiency].toLowerCase()}: ${item?.name ?? itemId}`,
        detail: reason,
        items: item ? [item.name] : undefined,
      });
    });
  },
  waive(caseId: string, itemId: string, reason: string, actor: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId ? { ...i, status: "waived" as DocStatus, waiverReason: reason } : i,
        ),
      };
      return log(next, {
        at: nowIso(),
        actor,
        kind: "waiver",
        title: `Waived: ${item?.name ?? itemId}`,
        detail: reason,
        items: item ? [item.name] : undefined,
      });
    });
  },
  simulateUpload(caseId: string, itemId: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      const next = {
        ...c,
        scoreOverride: undefined,
        items: c.items.map((i) =>
          i.id === itemId
            ? {
                ...i,
                status: "received" as DocStatus,
                rejection: undefined,
                insufficiency: undefined,
                confidence: 92,
                fileName: `${c.slug.replace(/-/g, "_")}_${i.id}.pdf`,
                receivedAt: nowIso(),
                receivedFrom: `Collection link — ${c.contact.name}`,
                pages: "machine checks queued",
                checks: [
                  {
                    key: "legible",
                    label: "Legibility",
                    outcome: "pass" as CheckOutcome,
                    detail: "Text layer detected on every page.",
                  },
                  {
                    key: "identifier",
                    label: "Identifier match",
                    outcome: "pass" as CheckOutcome,
                    detail: `PAN and GSTIN match ${c.borrower}.`,
                  },
                  {
                    key: "period",
                    label: "Period coverage",
                    outcome: "warn" as CheckOutcome,
                    detail: "Coverage to be confirmed.",
                  },
                ],
              }
            : i,
        ),
      };
      return log(next, {
        at: nowIso(),
        actor: `${c.contact.name}, ${c.borrower}`,
        kind: "upload",
        title: `Upload received: ${item?.name ?? itemId}`,
        detail: "Uploaded through the collection link; automated checks run on receipt.",
        items: item ? [item.name] : undefined,
      });
    });
  },
  sendReminder(caseId: string, actor: string) {
    setCase(caseId, (c) => {
      const open = c.items.filter((i) => i.status === "requested" || i.status === "rejected");
      return log(c, {
        at: nowIso(),
        actor,
        kind: "reminder",
        title: `Reminder sent — ${open.length} item${open.length === 1 ? "" : "s"} outstanding`,
        detail: `One consolidated message to ${c.contact.name} by ${REMINDER_CADENCE.channels.toLowerCase()}, listing only what is missing or insufficient.`,
        items: open.map((i) => i.name),
      });
    });
  },
  escalate(caseId: string, itemId: string, actor: string) {
    setCase(caseId, (c) => {
      const item = c.items.find((i) => i.id === itemId);
      return log(c, {
        at: nowIso(),
        actor,
        kind: "escalation",
        title: `Escalated: ${item?.name ?? itemId}`,
        detail: `Past the ${REMINDER_CADENCE.escalation}-day threshold with ${item?.remindersSent ?? 2} reminders sent.`,
        items: item ? [item.name] : undefined,
      });
    });
  },
};

export function useDocReady() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
  );
}

export function useDocReadyCase(id: string) {
  return useDocReady().cases.find((c) => c.id === id);
}
