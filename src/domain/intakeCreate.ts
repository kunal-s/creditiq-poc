/**
 * What the New appraisal sends (plan 2026-11-27): the case for POST /api/cases/intake with every
 * value's provenance, the checklist preview and the review requests, and the counts by source.
 */
import type {
  CaseCreate,
  CaseProposal,
  ChecklistPreviewRequest,
  HeaderField,
  IntakeProduct,
  Meta,
  ProposalRequest,
  Span,
} from "@/api/types";
import { spanOf, spanSource } from "@/domain/proposal";
import {
  formOf,
  productOf,
  singleField,
  repeatSection,
  filledRows,
  linesTotal,
  requestedAmount,
  primaryApplicant,
  cellSource,
  isPrefilled,
  visibleFields,
  visibleSections,
  isRepeat,
  shownSingles,
  rowValue,
  linesFacilities,
  SOURCE_KINDS,
  type Draft,
  type SourceKind,
} from "@/domain/intake";

// --- What is sent ---

function header(meta: Meta, d: Draft, proposal: CaseProposal | null): Record<string, HeaderField> {
  const form = formOf(meta, d.product);
  const out: Record<string, HeaderField> = {};
  const keys = new Set([
    ...(form ? shownSingles(form, d.values).map((f) => f.id) : []),
    ...d.extras,
  ]);
  for (const key of keys) {
    const value = (d.values[key] ?? "").trim() || null;
    if (isPrefilled(d, key)) {
      const p = d.prefilled[key]!;
      out[key] = { value, proposed: p.value, source: p.source };
      continue;
    }
    const proposed = proposal?.fields[key]?.value ?? null;
    if (value === null && proposed === null) continue;
    out[key] = {
      value,
      proposed,
      source: spanSource(d.spans[key]) ?? (value !== null ? "person" : null),
    };
  }
  out["product"] = {
    value: d.product,
    proposed: meta.product_default ?? null,
    source: d.product === meta.product_default ? d.productSource : "person",
  };
  if (form && !singleField(form, "facilities") && repeatSection(form, "facilities")) {
    // A business's request is its facility lines: the header keeps what the message proposed.
    const lines = filledRows(d, "facilities");
    const first = lines[0];
    const onlyFirst = lines.filter((r) => rowValue(r, "amount_inr")).length === 1;
    const total = linesTotal(d);
    const amountProposed = proposal?.fields["amount_inr"]?.value ?? null;
    if (total > 0 || amountProposed !== null)
      out["amount_inr"] = {
        value: total > 0 ? String(total) : null,
        proposed: amountProposed,
        source:
          (onlyFirst && cellSource(first?.cells["amount_inr"])) || (total > 0 ? "person" : null),
      };
    const ids = linesFacilities(d);
    const facilitiesProposed = proposal?.fields["facilities"]?.value ?? null;
    if (ids.length > 0 || facilitiesProposed !== null)
      out["facilities"] = {
        value: ids.length ? ids.join(",") : null,
        proposed: facilitiesProposed,
        source:
          lines.length > 0 &&
          lines.every((r) => cellSource(r.cells["facility"])?.startsWith("message:"))
            ? cellSource(first?.cells["facility"])
            : ids.length
              ? "person"
              : null,
      };
  }
  return out;
}

function groupsOf(meta: Meta, d: Draft): NonNullable<CaseCreate["groups"]> {
  const form = formOf(meta, d.product);
  const out: NonNullable<CaseCreate["groups"]> = {};
  for (const section of form ? visibleSections(form, d.values) : []) {
    if (!isRepeat(section)) continue;
    // Only the fields shown for the values on screen: a hidden field's value is never sent.
    const ids = new Set(visibleFields(section, d.values).map((f) => f.id));
    const rows = filledRows(d, section.id).map((row) => {
      const cells: Record<string, HeaderField> = {};
      for (const [field, cell] of Object.entries(row.cells)) {
        const value = cell.value.trim();
        if (!ids.has(field) || !value) continue;
        cells[field] = { value, proposed: cell.proposed, source: cellSource(cell) };
      }
      return cells;
    });
    if (rows.length > 0) out[section.id] = rows;
  }
  return out;
}

/** The case as POST /api/cases/intake takes it: each value with what was proposed and where it
 * came from (F-01.2), the rows of the repeating sections, and the message unchanged (F-04.8). */
export function toIntakeCreate(
  meta: Meta,
  d: Draft,
  opts: {
    proposal: CaseProposal | null;
    messageText: string | null;
    duplicateReason: string | null;
  },
): CaseCreate {
  const form = formOf(meta, d.product);
  const shown = new Set(form ? shownSingles(form, d.values).map((f) => f.id) : []);
  const v = (key: string) => (shown.has(key) ? (d.values[key] ?? "").trim() || null : null);
  const lap = Boolean(form && repeatSection(form, "applicants"));
  const facilities =
    form && singleField(form, "facilities")
      ? (v("facilities") ?? "").split(",").filter(Boolean)
      : linesFacilities(d);
  const body: CaseCreate = {
    borrower: v("borrower") ?? "",
    constitution: v("constitution") ?? "unknown",
    facilities,
    amount_inr: requestedAmount(meta, d),
    channel: v("channel") ?? d.values["channel"] ?? meta.channels[0]?.id ?? "",
    pan: lap ? rowValue(primaryApplicant(d) ?? { key: "", cells: {} }, "pan") || null : v("pan"),
    gstin: v("gstin"),
    cin: v("cin"),
    udyam: v("udyam"),
    collateral_present: lap
      ? filledRows(d, "properties").length > 0
      : v("collateral_present") === "yes" || filledRows(d, "properties").length > 0,
    product: d.product,
    case_type: v("case_type") ?? "unknown",
    customer_type: v("customer_type"),
    program: v("program"),
    tenure_months: Number(v("tenure_months")) || null,
    application_id: v("application_id"),
    customer_id: v("customer_id"),
    branch: v("branch"),
    bank_stage: v("bank_stage"),
    groups: groupsOf(meta, d),
    header: header(meta, d, opts.proposal),
  };
  if (opts.messageText?.trim()) body.message_text = opts.messageText;
  if (opts.duplicateReason) body.duplicate_override_reason = opts.duplicateReason;
  return body;
}

/** How many filled values come from each kind of source, as the engine logs them. */
export function countsBySource(body: CaseCreate): Record<SourceKind, number> {
  const counts: Record<SourceKind, number> = { message: 0, identifier: 0, default: 0, person: 0 };
  const add = (cell: HeaderField) => {
    if (!(cell.value ?? "").trim()) return;
    const head = (cell.source ?? "").split(":")[0] as SourceKind;
    counts[SOURCE_KINDS.includes(head) ? head : "person"] += 1;
  };
  Object.values(body.header ?? {}).forEach(add);
  for (const rows of Object.values(body.groups ?? {}))
    for (const row of rows) Object.values(row).forEach(add);
  return counts;
}

/** The checklist preview for the values on screen (F-12 at intake), for the chosen product. */
export function previewRequest(meta: Meta, d: Draft): ChecklistPreviewRequest {
  const body = toIntakeCreate(meta, d, {
    proposal: null,
    messageText: null,
    duplicateReason: null,
  });
  const p = productOf(meta, d.product);
  const customerType = body.customer_type ?? null;
  return {
    constitution: body.constitution ?? "unknown",
    facilities: body.facilities ?? [],
    amount_inr: body.amount_inr ?? 0,
    collateral_present: body.collateral_present ?? false,
    product: d.product,
    case_type: body.case_type && body.case_type !== "unknown" ? body.case_type : null,
    customer_type:
      customerType && p?.customer_types.some((c) => c.id === customerType) ? customerType : null,
  };
}

/** Fields the review asks the engine about (duplicates match on these; identifiers are checked). */
const REVIEWED = [
  "borrower",
  "constitution",
  "pan",
  "gstin",
  "cin",
  "udyam",
  "application_id",
  "customer_id",
  "customer_type",
  "amount_inr",
  "tenure_months",
  "facilities",
] as const;

/** The duplicate and identifier check for the values on screen (no message is read again). */
export function reviewRequest(meta: Meta, d: Draft, form: IntakeProduct): ProposalRequest {
  const body = toIntakeCreate(meta, d, {
    proposal: null,
    messageText: null,
    duplicateReason: null,
  });
  const fields: Record<string, string> = {};
  const known: Record<string, unknown> = { ...body, facilities: (body.facilities ?? []).join(",") };
  for (const key of REVIEWED) {
    const value = known[key];
    if (value !== null && value !== undefined && String(value).trim() && String(value) !== "0")
      fields[key] = String(value);
  }
  const co = filledRows(d, "applicants").find((r) => rowValue(r, "role") === "co_applicant");
  if (co && rowValue(co, "pan") && form.start.identifiers.some((i) => i.id === "co_applicant_pan"))
    fields["co_applicant_pan"] = rowValue(co, "pan");
  return { channel: body.channel, product: d.product, fields, groups: body.groups ?? {} };
}

/** The message spans every value on screen was read from, for the message view's marks. */
export function messageSpans(d: Draft): { key: string; span: Span }[] {
  const out: { key: string; span: Span }[] = [];
  for (const [key, span] of Object.entries(d.spans)) if (span) out.push({ key, span });
  for (const [section, rows] of Object.entries(d.groups))
    for (const row of rows)
      for (const [field, cell] of Object.entries(row.cells)) {
        const span = spanOf(cellSource(cell));
        if (span) out.push({ key: `${section}.${row.key}.${field}`, span });
      }
  return out;
}
