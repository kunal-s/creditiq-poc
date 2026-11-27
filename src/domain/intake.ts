/**
 * The product-first New appraisal (plan 2026-11-27, sections 3, 5 and 6): what the screen holds
 * before a case exists, and how it becomes the one-request create (POST /api/cases/intake).
 *
 * The form itself is the engine's (`Meta.intake`, from config/intake.yaml): its sections, fields,
 * option lists, start rules and each product's minimum. These are pure functions over it; the engine
 * judges every value again when the case is created, so nothing here decides a rule.
 */
import type {
  CaseCreate,
  CaseProposal,
  ChecklistPreviewRequest,
  HeaderField,
  IntakeField,
  IntakeFieldType,
  IntakeIdentifier,
  IntakeProduct,
  IntakeSection,
  Meta,
  ProductMeta,
  ProposalRequest,
  ProposedField,
  Span,
} from "@/api/types";
import { branchFor, spanOf, spanSource } from "@/domain/proposal";

/** A value the system pre-filled, and where it came from: "default:config" (the configured
 * default), "default:rm" (the RM's own branch) or "identifier" (an identifier box at the start). */
export type Prefill = { value: string; source: string };

/** One field of a repeating row: what it holds now, what was proposed for it and where that came
 * from ("message:<s>-<e>", "identifier", "default:config"); none for a value a person typed. */
export type Cell = { value: string; proposed: string | null; origin: string | null };
export type Row = { key: string; cells: Record<string, Cell> };

/** What the New appraisal screen holds before Create. Single values are by field id; the rows of
 * the repeating sections (applicants, properties, facility lines…) by section id. */
export type Draft = {
  product: string;
  /** "default:config" while the product is the configured default, "person" once chosen. */
  productSource: string;
  values: Record<string, string>;
  /** The message span each single value came from, if any. */
  spans: Record<string, Span | null>;
  /** Unclear or invalid values the RM has explicitly settled. */
  settled: Record<string, boolean>;
  prefilled: Record<string, Prefill>;
  groups: Record<string, Row[]>;
  /** Values the message proposed that the product's form has no field for: shown and kept as read. */
  extras: string[];
  /** Message fields placed into rows (facility lines, people, the primary applicant). */
  placed: string[];
  nextRow: number;
};

/** The start screen (step 2): the three boxes, the channel and the product chosen above them. */
export type Start = {
  product: string;
  productChosen: boolean;
  /** "" while the configured default channel stands. */
  channel: string;
  text: string;
  /** Identifier boxes by id; a value typed for one product is kept when the product changes. */
  identifiers: Record<string, string>;
  /** Choices that decide which identifier boxes show (customer type, case type). */
  choices: Record<string, string>;
  files: File[];
};

/** Kinds of source a filled value can have, in the order the review counts them. */
export const SOURCE_KINDS = ["message", "identifier", "default", "person"] as const;
export type SourceKind = (typeof SOURCE_KINDS)[number];

// --- The form ---

export function productOf(meta: Meta, id: string): ProductMeta | undefined {
  return meta.products.find((p) => p.id === id);
}

export function formOf(meta: Meta, id: string): IntakeProduct | undefined {
  return meta.intake?.[id];
}

type ShowWhen = IntakeSection["show_when"];

/** Whether a section, field or identifier box shows for the values so far: each key's value is one
 * of the listed ids (a key with no value yet hides it). */
export function isShown(when: ShowWhen, values: Record<string, string>): boolean {
  if (!when) return true;
  return Object.entries(when).every(([key, ids]) => ids.includes(values[key] ?? ""));
}

export function isRepeat(section: IntakeSection): boolean {
  return Boolean(section.repeat);
}

export function visibleSections(form: IntakeProduct, values: Record<string, string>) {
  return form.sections.filter((s) => isShown(s.show_when, values));
}

export function visibleFields(section: IntakeSection, values: Record<string, string>) {
  return section.fields.filter((f) => isShown(f.show_when, values));
}

/** The form's single-value field with this id, wherever it sits (shown or not). */
export function singleField(form: IntakeProduct, id: string): IntakeField | undefined {
  for (const s of form.sections) {
    if (isRepeat(s)) continue;
    const f = s.fields.find((x) => x.id === id);
    if (f) return f;
  }
  return undefined;
}

export function repeatSection(form: IntakeProduct, id: string): IntakeSection | undefined {
  return form.sections.find((s) => s.id === id && isRepeat(s));
}

/** The single fields on screen now, by id. */
export function shownSingles(form: IntakeProduct, values: Record<string, string>): IntakeField[] {
  return visibleSections(form, values)
    .filter((s) => !isRepeat(s))
    .flatMap((s) => visibleFields(s, values));
}

// --- The start screen ---

/** The identifier boxes the product offers now (some show only for a customer or case type). */
export function startIdentifiers(form: IntakeProduct, choices: Record<string, string>) {
  return form.start.identifiers.filter((i) => isShown(i.show_when, choices));
}

/** The choices a product's identifier boxes depend on (customer_type, case_type), in order. */
export function startChoiceKeys(form: IntakeProduct): string[] {
  const keys = form.start.identifiers.flatMap((i) => Object.keys(i.show_when ?? {}));
  return Array.from(new Set(keys));
}

/** Files the product needs before the application can continue or be created. */
export function minFiles(form: IntakeProduct | undefined): number {
  const docs = form?.start.documents;
  return docs?.required ? Math.max(1, docs.min_files) : 0;
}

/** Step 2's button: enabled once the product's documents are in (the message stays optional). */
export function canContinue(start: Start, form: IntakeProduct | undefined): boolean {
  return Boolean(form) && start.files.length >= minFiles(form);
}

/** The identifiers typed in the boxes shown now, as the engine takes them (codes in capitals). */
export function typedIdentifiers(
  form: IntakeProduct,
  start: Pick<Start, "identifiers" | "choices">,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const box of startIdentifiers(form, start.choices)) {
    const value = (start.identifiers[box.id] ?? "").trim();
    if (value) out[box.id] = box.type === "text" ? value : value.toUpperCase();
  }
  return out;
}

/** What the start button sends to read the message: the text, the product, and what the RM typed
 * (identifiers and the start choices), which win over what the message says. */
export function proposalRequest(form: IntakeProduct, start: Start, channel: string) {
  const fields: Record<string, string> = { ...typedIdentifiers(form, start) };
  for (const [key, value] of Object.entries(start.choices)) if (value) fields[key] = value;
  const text = start.text.trim() ? start.text : null;
  return { channel, product: start.product, text, fields } satisfies ProposalRequest;
}

// --- Format hints (the engine stays the judge) ---

const PAN = /^[A-Z]{5}\d{4}[A-Z]$/;
const FORMATS: Partial<Record<IntakeFieldType, RegExp>> = {
  pan: PAN,
  gstin: /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/,
  cin_or_llpin: /^(?:[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}|[A-Z]{3}-\d{4})$/,
  udyam: /^UDYAM-[A-Z]{2}-\d{2}-\d{7}$/,
  pincode: /^[1-9]\d{5}$/,
  number: /^\d{1,12}(?:\.\d{1,4})?$/,
};

/** The length at which a code is complete, so its format is judged while typing; other values
 * are judged once the field is left. */
export const FULL_LENGTH: Partial<Record<IntakeFieldType, number>> = {
  pan: 10,
  gstin: 15,
  udyam: 19,
  pincode: 6,
};

/** The terminology key of a field's format hint, or null for a field without one. */
export function formatHintKey(
  type: IntakeFieldType,
  holder?: IntakeIdentifier["holder"],
): string | null {
  if (type === "pan")
    return holder === "individual" ? "intake.hint.panIndividual" : "intake.hint.pan";
  return type in FORMATS || type === "digits" ? `intake.hint.${type}` : null;
}

/** Whether a typed value looks right for its type: a hint beside the field, never a refusal. */
export function looksValid(
  type: IntakeFieldType,
  value: string,
  opts: {
    length?: number | null | undefined;
    holder?: IntakeIdentifier["holder"] | undefined;
    lifted?: boolean;
  } = {},
): boolean {
  const v = value.trim().toUpperCase();
  if (!v) return true;
  if (type === "digits") return opts.length ? v.length === opts.length && /^\d+$/.test(v) : true;
  if (type === "months") return /^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 600;
  const pattern = FORMATS[type];
  if (!pattern) return true;
  if (!pattern.test(v)) return false;
  return !(type === "pan" && opts.holder === "individual" && !opts.lifted && v[3] !== "P");
}

/** What a keystroke may put in a field of this type: digits for figures, capitals for codes. */
export function cleanInput(type: IntakeFieldType, raw: string, length?: number | null): string {
  switch (type) {
    case "amount":
    case "months":
    case "pincode":
      return raw.replace(/\D/g, "");
    case "digits":
      return raw.replace(/\D/g, "").slice(0, length ?? undefined);
    case "number": {
      const [whole = "", ...rest] = raw.replace(/[^\d.]/g, "").split(".");
      return rest.length ? `${whole}.${rest.join("")}` : whole;
    }
    case "pan":
    case "gstin":
    case "udyam":
    case "cin_or_llpin":
      return raw.toUpperCase().replace(/\s/g, "");
    default:
      return raw;
  }
}

// --- Building the draft ---

function matchOption(options: { id: string; label: string }[], raw: string): string | undefined {
  const needle = raw.trim().toLowerCase();
  if (!needle) return undefined;
  return options.find((o) => o.id.toLowerCase() === needle || o.label.toLowerCase() === needle)?.id;
}

/** A proposed value in the form its field holds: a choice's id, a figure's digits. */
export function normaliseFor(field: IntakeField | undefined, raw: string | null): string {
  if (raw === null) return "";
  if (!field) return raw;
  if (field.type === "choice") {
    const id = matchOption(field.options ?? [], raw) ?? "";
    // "unknown" is how a case stores "not yet confirmed"; the editor holds it as empty.
    return id === "unknown" ? "" : id;
  }
  if (["amount", "months", "digits", "pincode"].includes(field.type)) return raw.replace(/\D/g, "");
  if (["pan", "gstin", "udyam", "cin_or_llpin"].includes(field.type)) return raw.toUpperCase();
  return raw;
}

function cellOf(value: string, origin: string | null): Cell {
  return { value, proposed: origin ? value : null, origin };
}

function newRow(d: Draft, cells: Record<string, Cell> = {}): [Row, number] {
  return [{ key: `r${d.nextRow}`, cells }, d.nextRow + 1];
}

/** The role a new row of a section takes: the first choice for the first row (the primary
 * applicant), the next one for any other (a co-applicant), none where the field has no choices. */
function presetRole(section: IntakeSection, first: boolean): Record<string, Cell> {
  const role = section.fields.find((f) => f.id === "role" && f.type === "choice");
  const options = (role?.options ?? []).filter((o) => o.id !== "unknown");
  if (!role?.required || options.length === 0) return {};
  if (first) return { role: cellOf(options[0]!.id, "default:config") };
  return options[1] ? { role: { value: options[1].id, proposed: null, origin: null } } : {};
}

/** An empty application for the product: its configured defaults (stage, the RM's branch, the
 * channel) and the rows each repeating section starts with. */
export function blankDraft(
  meta: Meta,
  product: string,
  opts: {
    productSource: string;
    rmBranch?: string | null | undefined;
    channel: string;
    channelDefault: boolean;
  },
): Draft {
  const p = productOf(meta, product);
  const form = formOf(meta, product);
  const values: Record<string, string> = {};
  const prefilled: Record<string, Prefill> = {};
  const prefill = (key: string, value: string | null | undefined, source: string) => {
    if (!value || !form || !singleField(form, key)) return;
    values[key] = value;
    prefilled[key] = { value, source };
  };
  const stage = meta.bank_stage_default;
  if (stage && (p?.stages ?? []).some((s) => s.id === stage))
    prefill("bank_stage", stage, "default:config");
  prefill("branch", branchFor(opts.rmBranch, meta), "default:rm");
  if (opts.channelDefault) prefill("channel", opts.channel, "default:config");
  else if (opts.channel && form && singleField(form, "channel")) values["channel"] = opts.channel;
  const groups: Record<string, Row[]> = {};
  let nextRow = 1;
  for (const section of form?.sections ?? []) {
    if (!section.repeat) continue;
    const rows: Row[] = [];
    for (let i = 0; i < (section.repeat["min"] ?? 0); i++) {
      rows.push({ key: `r${nextRow}`, cells: presetRole(section, i === 0) });
      nextRow += 1;
    }
    groups[section.id] = rows;
  }
  return {
    product,
    productSource: opts.productSource,
    values,
    spans: {},
    settled: {},
    prefilled,
    groups,
    extras: [],
    placed: [],
    nextRow,
  };
}

/** The message candidates of a multi-valued field, each with its span. */
function pieces(f: ProposedField): { value: string; span: Span | null }[] {
  if ((f.candidates ?? []).length > 0) return f.candidates!.map((c) => ({ ...c }));
  return f.value ? [{ value: f.value, span: f.span ?? null }] : [];
}

/** Facilities and the amount the message names, as facility lines: one per facility, the amount
 * on the first (it is the line the message states it for, or the only one). */
function placeFacilities(
  meta: Meta,
  d: Draft,
  proposal: CaseProposal,
  lines: IntakeSection,
): Draft {
  const facilities = proposal.fields["facilities"];
  const amount = proposal.fields["amount_inr"];
  const facilityField = lines.fields.find((f) => f.id === "facility");
  const seen = new Set<string>();
  const ids: { id: string; span: Span | null }[] = [];
  for (const piece of facilities ? pieces(facilities) : []) {
    for (const part of piece.value.split(/[,;|+/]|\band\b/i)) {
      const id = matchOption(facilityField?.options ?? meta.facilities, part);
      if (id && !seen.has(id)) {
        seen.add(id);
        ids.push({ id, span: piece.span });
      }
    }
  }
  const amountValue =
    amount && amount.status !== "not_found" ? (amount.value ?? "").replace(/\D/g, "") : "";
  if (ids.length === 0 && !amountValue) return d;
  let next = d;
  const rows: Row[] = [];
  const count = Math.max(ids.length, 1);
  for (let i = 0; i < count; i++) {
    const cells: Record<string, Cell> = {};
    const item = ids[i];
    if (item) cells["facility"] = cellOf(item.id, spanSource(item.span) ?? "message");
    if (i === 0 && amountValue && amount?.status === "found")
      cells["amount_inr"] = cellOf(amountValue, spanSource(amount.span) ?? "message");
    const [row, n] = newRow(next, cells);
    rows.push(row);
    next = { ...next, nextRow: n };
  }
  return {
    ...next,
    groups: { ...next.groups, [lines.id]: rows },
    placed: [...next.placed, "facilities", "amount_inr"],
  };
}

/** Names the message proposes (promoters) as rows of the people section. */
function placePeople(d: Draft, f: ProposedField, section: IntakeSection): Draft {
  let next = d;
  const rows: Row[] = [];
  for (const piece of pieces(f)) {
    for (const name of piece.value.split(/;|,|\band\b/).map((s) => s.trim())) {
      if (!name) continue;
      const [row, n] = newRow(next, { name: cellOf(name, spanSource(piece.span) ?? "message") });
      rows.push(row);
      next = { ...next, nextRow: n };
    }
  }
  if (rows.length === 0) return d;
  return {
    ...next,
    groups: { ...next.groups, [section.id]: rows },
    placed: [...next.placed, "promoters"],
  };
}

/** Put a value in the row of a section whose role is `role` (the first row when none is), adding
 * that row when the section has none for the role. */
function putInRoleRow(
  d: Draft,
  section: string,
  role: string | null,
  field: string,
  cell: Cell,
): Draft {
  const rows = d.groups[section] ?? [];
  let index = role ? rows.findIndex((r) => r.cells["role"]?.value === role) : 0;
  if (index < 0 && role === "applicant" && rows.length > 0 && !rows[0]!.cells["role"]?.value)
    index = 0;
  if (index >= 0 && rows[index]) {
    const updated = rows.map((r, i) =>
      i === index ? { ...r, cells: { ...r.cells, [field]: cell } } : r,
    );
    return { ...d, groups: { ...d.groups, [section]: updated } };
  }
  const cells: Record<string, Cell> = { [field]: cell };
  if (role) cells["role"] = { value: role, proposed: null, origin: null };
  const [row, n] = newRow(d, cells);
  return { ...d, nextRow: n, groups: { ...d.groups, [section]: [...rows, row] } };
}

/** Identifier boxes whose value belongs in a row rather than a single field: a loan against
 * property's applicant and co-applicant PAN. */
const IDENTIFIER_ROWS: Record<string, { section: string; role: string; field: string }> = {
  pan: { section: "applicants", role: "applicant", field: "pan" },
  co_applicant_pan: { section: "applicants", role: "co_applicant", field: "pan" },
};

/** The values typed in the identifier boxes, each in its form field with source "identifier"
 * (they win over what a message says). */
export function applyIdentifiers(meta: Meta, d: Draft, typed: Record<string, string>): Draft {
  const form = formOf(meta, d.product);
  if (!form) return d;
  let next = d;
  for (const [id, value] of Object.entries(typed)) {
    if (singleField(form, id)) {
      next = {
        ...next,
        values: { ...next.values, [id]: value },
        spans: { ...next.spans, [id]: null },
        prefilled: { ...next.prefilled, [id]: { value, source: "identifier" } },
        settled: { ...next.settled, [id]: true },
      };
      continue;
    }
    const target = IDENTIFIER_ROWS[id];
    if (target && repeatSection(form, target.section))
      next = putInRoleRow(
        next,
        target.section,
        target.role,
        target.field,
        cellOf(value, "identifier"),
      );
  }
  return next;
}

/** Place one field the message proposed: in its form field, in rows (facility lines, people, the
 * primary applicant), or kept aside as read when the form has no place for it. */
function placeProposed(meta: Meta, form: IntakeProduct, d: Draft, key: string, f: ProposedField) {
  if (f.source === "identifier" || f.source === "person") return d; // typed: applied separately
  const field = singleField(form, key);
  if (field) {
    const value = f.status === "not_found" ? "" : normaliseFor(field, f.value);
    const values = { ...d.values };
    const prefilled = { ...d.prefilled };
    if (value || !prefilled[key]) {
      values[key] = value;
      delete prefilled[key];
    }
    return { ...d, values, prefilled, spans: { ...d.spans, [key]: f.span ?? null } };
  }
  const people = repeatSection(form, "people");
  if (key === "promoters" && people) return placePeople(d, f, people);
  const applicants = repeatSection(form, "applicants");
  if (applicants && f.status === "found" && f.value && (key === "borrower" || key === "pan")) {
    const name = key === "borrower" ? "name" : "pan";
    const cell = cellOf(
      key === "pan" ? f.value.toUpperCase() : f.value,
      spanSource(f.span) ?? "message",
    );
    return {
      ...putInRoleRow(d, "applicants", "applicant", name, cell),
      placed: [...d.placed, key],
    };
  }
  if (f.status === "not_found" || f.value === null) return d;
  return {
    ...d,
    values: { ...d.values, [key]: f.value },
    spans: { ...d.spans, [key]: f.span ?? null },
    extras: [...d.extras, key],
  };
}

/** The application to continue with (step 3): blank, or what a read message proposes, with the
 * start choices and the identifiers typed at the start in their fields. */
export function draftFrom(
  meta: Meta,
  start: Start,
  proposal: CaseProposal | null,
  rmBranch?: string | null,
): Draft {
  const form = formOf(meta, start.product);
  const channelDefault = !start.channel;
  const channel = start.channel || meta.channels[0]?.id || "";
  let d = blankDraft(meta, start.product, {
    productSource: start.productChosen ? "person" : "default:config",
    rmBranch,
    channel,
    channelDefault,
  });
  if (!form) return d;
  if (proposal) {
    const lines = repeatSection(form, "facilities");
    if (lines && !singleField(form, "facilities")) d = placeFacilities(meta, d, proposal, lines);
    for (const [key, f] of Object.entries(proposal.fields)) {
      if (d.placed.includes(key)) continue;
      d = placeProposed(meta, form, d, key, f);
    }
  }
  for (const [key, value] of Object.entries(start.choices)) {
    if (value && singleField(form, key)) {
      d = { ...d, values: { ...d.values, [key]: value }, settled: { ...d.settled, [key]: true } };
    }
  }
  return applyIdentifiers(meta, d, typedIdentifiers(form, start));
}

/** Values of the fields both products' forms share, carried into a draft of the other product or
 * of the same product read again (switching product, or going back to the start, keeps them).
 * What the RM settled, typed or changed wins over what the new reading pre-fills; what was only
 * read or pre-filled before gives way to the new reading. */
export function carryOver(meta: Meta, from: Draft, to: Draft): Draft {
  const form = formOf(meta, to.product);
  if (!form) return to;
  const values = { ...to.values };
  const spans = { ...to.spans };
  const prefilled = { ...to.prefilled };
  const settled = { ...to.settled };
  for (const [key, value] of Object.entries(from.values)) {
    const field = singleField(form, key);
    if (!field || !value) continue;
    if (field.type === "choice" && !(field.options ?? []).some((o) => o.id === value)) continue;
    const edited = Boolean(from.settled[key]) || (!from.spans[key] && !isPrefilled(from, key));
    const open = !values[key] || isPrefilled(to, key);
    if (!edited && !open) continue;
    values[key] = value;
    spans[key] = from.spans[key] ?? null;
    if (from.prefilled[key]?.value === value) prefilled[key] = from.prefilled[key]!;
    else delete prefilled[key];
    if (from.settled[key]) settled[key] = true;
  }
  return { ...to, values, spans, prefilled, settled };
}

// --- Editing ---

export function setValue(d: Draft, key: string, value: string, span?: Span | null): Draft {
  return {
    ...d,
    values: { ...d.values, [key]: value },
    spans: span !== undefined ? { ...d.spans, [key]: span } : d.spans,
    settled: { ...d.settled, [key]: true },
  };
}

export function settle(d: Draft, key: string): Draft {
  return { ...d, settled: { ...d.settled, [key]: true } };
}

export function setCell(d: Draft, section: string, rowKey: string, field: string, value: string) {
  const rows = (d.groups[section] ?? []).map((r) => {
    if (r.key !== rowKey) return r;
    const was = r.cells[field] ?? { value: "", proposed: null, origin: null };
    return { ...r, cells: { ...r.cells, [field]: { ...was, value } } };
  });
  return { ...d, groups: { ...d.groups, [section]: rows } };
}

/** A new row at the end of a section, up to its maximum. */
export function addRow(meta: Meta, d: Draft, sectionId: string): Draft {
  const section = formOf(meta, d.product)?.sections.find((s) => s.id === sectionId);
  const rows = d.groups[sectionId] ?? [];
  if (!section?.repeat || rows.length >= (section.repeat["max"] ?? 0)) return d;
  const [row, next] = newRow(d, presetRole(section, rows.length === 0));
  return { ...d, nextRow: next, groups: { ...d.groups, [sectionId]: [...rows, row] } };
}

export function removeRow(d: Draft, section: string, rowKey: string): Draft {
  const rows = (d.groups[section] ?? []).filter((r) => r.key !== rowKey);
  return { ...d, groups: { ...d.groups, [section]: rows } };
}

// --- Reading the draft ---

/** The value is still the one the system pre-filled. */
export function isPrefilled(d: Draft, key: string): boolean {
  const p = d.prefilled[key];
  return p !== undefined && (d.values[key] ?? "") === p.value;
}

/** A row field's source as the header records it (F-01.2): where its proposed value came from
 * (the person's own when nothing was proposed); a changed value keeps it beside the proposal. */
export function cellSource(cell: Cell | undefined): string | null {
  if (!cell || !cell.value.trim()) return null;
  return cell.origin ?? "person";
}

function hasValue(row: Row): boolean {
  return Object.values(row.cells).some((c) => c.value.trim() !== "");
}

/** The rows of a section with something in them, in order. */
export function filledRows(d: Draft, section: string): Row[] {
  return (d.groups[section] ?? []).filter(hasValue);
}

export const rowValue = (row: Row, field: string) => (row.cells[field]?.value ?? "").trim();

/** The primary applicant of a loan against property: the applicant row, else the first named. */
export function primaryApplicant(d: Draft): Row | undefined {
  const rows = filledRows(d, "applicants").filter((r) => rowValue(r, "name"));
  return rows.find((r) => rowValue(r, "role") === "applicant") ?? rows[0];
}

/** The facility lines' total, which is the requested amount of a business banking case. */
export function linesTotal(d: Draft): number {
  return filledRows(d, "facilities").reduce(
    (sum, r) => sum + (Number(rowValue(r, "amount_inr")) || 0),
    0,
  );
}

export function linesFacilities(d: Draft): string[] {
  const ids = filledRows(d, "facilities").map((r) => rowValue(r, "facility"));
  return Array.from(new Set(ids.filter(Boolean)));
}

/** The requested amount: the form's own field, or the facility lines' total. */
export function requestedAmount(meta: Meta, d: Draft): number {
  const form = formOf(meta, d.product);
  if (form && singleField(form, "amount_inr")) return Number(d.values["amount_inr"] ?? 0) || 0;
  return linesTotal(d);
}

/** Unclear or invalid values on screen still waiting for the RM (F-04.3, F-04.4). */
export function unsettled(meta: Meta, proposal: CaseProposal | null, d: Draft): string[] {
  const form = formOf(meta, d.product);
  if (!proposal || !form) return [];
  const shown = new Set([...shownSingles(form, d.values).map((f) => f.id), ...d.extras]);
  return Object.entries(proposal.fields)
    .filter(([, f]) => f.status === "unclear" || f.status === "invalid")
    .filter(([key]) => shown.has(key) && !d.settled[key] && !d.placed.includes(key))
    .map(([key]) => key);
}

/** Rows with something in them that lack a required field: the engine refuses those. */
export function rowGaps(meta: Meta, d: Draft): { section: string; row: number; field: string }[] {
  const form = formOf(meta, d.product);
  if (!form) return [];
  const out: { section: string; row: number; field: string }[] = [];
  for (const section of visibleSections(form, d.values)) {
    if (!isRepeat(section)) continue;
    const fields = visibleFields(section, d.values);
    const rows = filledRows(d, section.id);
    rows.forEach((row, i) => {
      for (const f of fields)
        if (f.required && !rowValue(row, f.id))
          out.push({ section: section.id, row: i + 1, field: f.id });
    });
    // Fewer rows than the section's minimum: the next row's first required field is needed.
    const first = fields.find((f) => f.required) ?? fields[0];
    for (let n = rows.length; n < (section.repeat?.["min"] ?? 0) && first; n++)
      out.push({ section: section.id, row: n + 1, field: first.id });
  }
  return out;
}
