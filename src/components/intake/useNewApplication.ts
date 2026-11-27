import { useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import type { CaseProposal, CaseSummary, Meta, ProposalRequest } from "@/api/types";
import { t } from "@/config/terminology";
import { useCreateCaseWithFiles, useIntakeReview, useProposeCase } from "@/domain/cases";
import {
  carryOver,
  draftFrom,
  formOf,
  minFiles,
  productOf,
  proposalRequest,
  rowGaps,
  unsettled,
  type Draft,
  type Start,
} from "@/domain/intake";
import { reviewRequest, toIntakeCreate } from "@/domain/intakeCreate";
import { useSession } from "@/domain/session";

const EMPTY_START: Start = {
  product: "",
  productChosen: false,
  channel: "",
  text: "",
  identifiers: {},
  choices: {},
  files: [],
};

/** How long the review waits after the last change before it asks the engine again. */
const REVIEW_DELAY_MS = 400;

/** The value as it was once it stopped changing for `ms` (compared by content, not identity),
 * with its content key. */
function useSettled<T>(value: T | null, ms: number): [T | null, string] {
  const key = value === null ? "" : JSON.stringify(value);
  const [settled, setSettled] = useState(key);
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(key), ms);
    return () => window.clearTimeout(id);
  }, [key, ms]);
  const parsed = useMemo(() => (settled ? (JSON.parse(settled) as T) : null), [settled]);
  return [parsed, settled];
}

/** The duplicates a 409 from case creation carries (F-04.5), if any. */
export function duplicatesIn(error: unknown): CaseSummary[] | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const detail = error.detail as { duplicates?: unknown } | null;
  return Array.isArray(detail?.duplicates) ? (detail.duplicates as CaseSummary[]) : null;
}

function unique(cases: CaseSummary[]): CaseSummary[] {
  const seen = new Set<string>();
  return cases.filter((c) => !seen.has(c.id) && Boolean(seen.add(c.id)));
}

/** Start choices still valid for a product (a case type of one product is not another's). */
function choicesFor(meta: Meta, product: string, choices: Record<string, string>) {
  const p = productOf(meta, product);
  const lists: Record<string, { id: string }[]> = {
    customer_type: p?.customer_types ?? [],
    case_type: p?.case_types ?? [],
  };
  return Object.fromEntries(
    Object.entries(choices).filter(([k, v]) => (lists[k] ?? []).some((o) => o.id === v)),
  );
}

/** The New appraisal screen's state: the start (product, boxes, files), the application being
 * prepared, the engine's review of it, and Create. Nothing is stored on the server until Create,
 * which sends the case and its files together. */
export function useNewApplication(meta: Meta | undefined) {
  const navigate = useNavigate();
  const session = useSession();
  const propose = useProposeCase();
  const create = useCreateCaseWithFiles();
  const [start, setStart] = useState<Start>(EMPTY_START);
  const [proposal, setProposal] = useState<CaseProposal | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [override, setOverride] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  /** Duplicates a 409 named, for the values they were found for. */
  const [conflicts, setConflicts] = useState<{ key: string; cases: CaseSummary[] }>({
    key: "",
    cases: [],
  });
  /** The product being switched to while the message is read again for it. */
  const [switching, setSwitching] = useState<string | null>(null);
  /** The application left by going back to the start, carried into the next one. */
  const [previous, setPrevious] = useState<Draft | null>(null);

  const product = start.product || meta?.product_default || meta?.products[0]?.id || "";
  const current: Start = { ...start, product };
  const form = meta ? formOf(meta, draft?.product ?? product) : undefined;
  const channel = start.channel || meta?.channels[0]?.id || "";

  const reviewNow = meta && draft && form ? reviewRequest(meta, draft, form) : null;
  const nowKey = reviewNow ? JSON.stringify(reviewNow) : "";
  const [reviewBody, reviewKey] = useSettled<ProposalRequest>(reviewNow, REVIEW_DELAY_MS);
  const review = useIntakeReview(draft ? reviewBody : null);
  // The engine's answer counts only for the values on screen now.
  const fresh = Boolean(review.data) && !review.isFetching && reviewKey === nowKey;

  const patchStart = (patch: Partial<Start>) => setStart((s) => ({ ...s, product, ...patch }));

  async function begin(s: Start, from: Draft | null) {
    if (!meta) return;
    const f = formOf(meta, s.product);
    if (!f) return;
    let read: CaseProposal | null = null;
    try {
      read = s.text.trim() ? await propose.mutateAsync(proposalRequest(f, s, channel)) : null;
    } catch {
      // Shown where the RM is (the start boxes or the form) from the mutation's error; the
      // product and the application stay as they were.
      setSwitching(null);
      return;
    }
    setSwitching(null);
    let d = draftFrom(meta, s, read, session?.user.branch);
    if (from) d = carryOver(meta, from, d);
    setStart(s);
    setProposal(read);
    setDraft(d);
    setPrevious(null);
    setSelected(null);
    setOverride(false);
    setReason("");
    setConflicts({ key: "", cases: [] });
    create.reset();
  }

  function chooseProduct(id: string) {
    if (!meta || propose.isPending || id === (draft?.product ?? product)) return setPending(null);
    if (draft) return setPending(id);
    setStart((s) => ({
      ...s,
      product: id,
      productChosen: true,
      choices: choicesFor(meta, id, s.choices),
    }));
  }

  function confirmSwitch() {
    if (!meta || !pending) return;
    const next = {
      ...current,
      product: pending,
      productChosen: true,
      choices: choicesFor(meta, pending, current.choices),
    };
    setPending(null);
    setSwitching(pending);
    void begin(next, draft);
  }

  function backToStart() {
    setPrevious(draft);
    setProposal(null);
    setDraft(null);
    setSelected(null);
    setPending(null);
    propose.reset();
  }

  function discard() {
    backToStart();
    setPrevious(null);
    setStart((s) => ({ ...EMPTY_START, product: s.product, productChosen: s.productChosen }));
    create.reset();
  }

  const found = fresh
    ? (review.data?.duplicates ?? [])
    : review.data
      ? []
      : (proposal?.duplicates ?? []);
  const duplicates = unique([...found, ...(conflicts.key === nowKey ? conflicts.cases : [])]);
  const body =
    meta && draft
      ? toIntakeCreate(meta, draft, {
          proposal,
          messageText: proposal ? start.text : null,
          duplicateReason: override && reason.trim() ? reason.trim() : null,
        })
      : null;

  async function submit() {
    if (!body) return;
    try {
      const created = await create.mutateAsync({ body, files: start.files });
      const id = created.case.id;
      if (created.uploadFailed) {
        toast(t("intake.create.uploadLater"));
        void navigate({ to: "/appraisals/$caseId/documents", params: { caseId: id } });
        return;
      }
      toast.success(t("newApplication.created", { id }));
      // Processing has started with the files: the Overview shows it.
      void navigate({ to: "/appraisals/$caseId", params: { caseId: id } });
    } catch (error) {
      // A duplicate found at creation (409) shows as the duplicate warning; anything else is
      // shown from the mutation's error state. Nothing was created: the files stay on screen.
      const more = duplicatesIn(error);
      if (more) {
        setConflicts((c) => ({ key: nowKey, cases: unique([...c.cases, ...more]) }));
        setOverride(false);
      }
    }
  }

  return {
    start: current,
    patchStart,
    channel,
    form,
    proposal,
    draft,
    setDraft,
    selected,
    setSelected,
    pending,
    chooseProduct,
    confirmSwitch,
    cancelSwitch: () => setPending(null),
    continueFromStart: () => void begin(current, previous),
    backToStart,
    discard,
    submit: () => void submit(),
    propose,
    create,
    review,
    fresh,
    switching,
    body,
    duplicates,
    override,
    setOverride,
    reason,
    setReason,
    checks: {
      checking: Boolean(draft) && !fresh && !review.isError,
      missing: fresh ? (review.data?.missing_minimum ?? []) : [],
      gaps: meta && draft ? rowGaps(meta, draft) : [],
      pending: meta && draft ? unsettled(meta, proposal, draft) : [],
      needFiles: start.files.length < minFiles(form),
      duplicateBlocked: duplicates.length > 0 && (!override || !reason.trim()),
    },
  };
}
