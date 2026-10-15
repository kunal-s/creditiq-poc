import type { EditableSettings, SettingChange, SettingsChanges } from "@/api/types";
import { t, tOr } from "@/config/terminology";
import { formatInr } from "@/domain/cases";

// The settings an Administrator edits (F-00.6): tolerances, norm thresholds, cross-check rules and
// the approval matrix. Edits are kept as a draft of the fields changed, as typed; only what differs
// from the version in force is sent, and the engine checks it, says what it would change and
// publishes it as a new version. Band amounts are entered in INR crore and sent in rupees.

/** A field's value as its control holds it: text for an amount, a key for a choice, a flag. */
export type DraftValue = string | boolean;
/** The fields edited, by field key. */
export type Draft = Record<string, DraftValue>;

export type FieldSpec =
  | { kind: "number"; published: number }
  | { kind: "whole"; published: number }
  /** An amount in rupees, entered in crore. */
  | { kind: "crore"; published: number }
  /** A key; "" for none. */
  | { kind: "choice"; published: string }
  | { kind: "flag"; published: boolean };

export type FieldState = { value: DraftValue; changed: boolean; invalid: boolean };

export const fieldKey = {
  tolerance: (key: string) => `tolerances:${key}`,
  ratio: (key: string, field: "acceptable" | "marginal") => `ratios:${key}:${field}`,
  norm: (id: string) => `norms:${id}`,
  rule: (id: string, field: "enabled" | "severity" | "blocking") => `rules:${id}:${field}`,
  band: (product: string, index: number, field: "up_to_inr" | "authority") =>
    `bands:${product}:${index}:${field}`,
  deviation: (category: string, field: "levels_above" | "at_least") =>
    `deviations:${category}:${field}`,
};

const CRORE = 1e7;

/** Every field the screen edits, with its published value. */
export function fieldsOf(s: EditableSettings): Map<string, FieldSpec> {
  const fields = new Map<string, FieldSpec>();
  for (const x of s.tolerances) {
    fields.set(fieldKey.tolerance(x.key), { kind: "number", published: x.value });
  }
  for (const r of s.ratios) {
    fields.set(fieldKey.ratio(r.key, "acceptable"), { kind: "number", published: r.acceptable });
    fields.set(fieldKey.ratio(r.key, "marginal"), { kind: "number", published: r.marginal });
  }
  for (const n of s.norms) {
    fields.set(fieldKey.norm(n.id), { kind: "number", published: n.threshold });
  }
  for (const r of s.rules) {
    fields.set(fieldKey.rule(r.id, "enabled"), { kind: "flag", published: r.enabled });
    fields.set(fieldKey.rule(r.id, "severity"), { kind: "choice", published: r.severity });
    fields.set(fieldKey.rule(r.id, "blocking"), { kind: "flag", published: r.blocking });
  }
  for (const p of s.matrix.products) {
    p.bands.forEach((b, i) => {
      if (typeof b.up_to_inr === "number") {
        fields.set(fieldKey.band(p.key, i, "up_to_inr"), { kind: "crore", published: b.up_to_inr });
      }
      fields.set(fieldKey.band(p.key, i, "authority"), { kind: "choice", published: b.authority });
    });
  }
  for (const d of s.matrix.deviations) {
    fields.set(fieldKey.deviation(d.category, "levels_above"), {
      kind: "whole",
      published: d.levels_above,
    });
    fields.set(fieldKey.deviation(d.category, "at_least"), {
      kind: "choice",
      published: d.at_least ?? "",
    });
  }
  return fields;
}

/** A typed amount as a number; null when it is not one. */
export function parseNumber(text: string): number | null {
  const s = text.trim().replace(/,/g, "");
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/** Rupees as crore for an input: 20000000 is "2". */
export function croreText(rupees: number): string {
  return String(Number((rupees / CRORE).toFixed(7)));
}

/** The published value as its control holds it. */
function inputOf(spec: FieldSpec): DraftValue {
  if (spec.kind === "crore") return croreText(spec.published);
  if (spec.kind === "number" || spec.kind === "whole") return String(spec.published);
  return spec.published;
}

/** A control's value as the engine takes it; null when it is not a valid value. */
function valueOf(spec: FieldSpec, value: DraftValue): number | string | boolean | null {
  if (spec.kind === "flag" || spec.kind === "choice") return value;
  const n = parseNumber(String(value));
  if (n === null) return null;
  if (spec.kind === "crore") return n > 0 ? Math.round(n * CRORE) : null;
  if (spec.kind === "whole") return Number.isInteger(n) && n >= 0 ? n : null;
  return n;
}

export function fieldState(spec: FieldSpec, draft: Draft, key: string): FieldState {
  if (!(key in draft)) return { value: inputOf(spec), changed: false, invalid: false };
  const value = draft[key]!;
  const parsed = valueOf(spec, value);
  return { value, invalid: parsed === null, changed: parsed === null || parsed !== spec.published };
}

/** A field's value as the engine would take it: the draft's when it is valid, else the
 * published one. */
export function currentValue(spec: FieldSpec, draft: Draft, key: string) {
  const parsed = key in draft ? valueOf(spec, draft[key]!) : null;
  return parsed ?? spec.published;
}

/** Whether a draft value is the published one, so the field holds nothing to keep. */
export function isPublished(spec: FieldSpec, value: DraftValue): boolean {
  return valueOf(spec, value) === spec.published && value === inputOf(spec);
}

/** The fields the draft changes, and those whose value is not one the engine can take. */
export function draftCounts(fields: Map<string, FieldSpec>, draft: Draft) {
  let changed = 0;
  let invalid = 0;
  for (const key of Object.keys(draft)) {
    const spec = fields.get(key);
    if (!spec) continue;
    const state = fieldState(spec, draft, key);
    if (state.changed) changed += 1;
    if (state.invalid) invalid += 1;
  }
  return { changed, invalid };
}

/** Only what the draft changes, as the engine takes it: a product's bands go as a whole. */
export function changesOf(s: EditableSettings, draft: Draft): SettingsChanges {
  const fields = fieldsOf(s);
  const edited = (key: string) => {
    const spec = fields.get(key);
    if (!spec || !(key in draft)) return undefined;
    const value = valueOf(spec, draft[key]!);
    return value === null || value === spec.published ? undefined : value;
  };
  const num = (key: string) => edited(key) as number | undefined;
  const flag = (key: string) => edited(key) as boolean | undefined;
  const choice = (key: string) => edited(key) as string | undefined;
  const out: Required<SettingsChanges> = {
    tolerances: {},
    ratios: {},
    norms: {},
    rules: {},
    bands: {},
    deviations: {},
  };
  for (const x of s.tolerances) {
    const value = num(fieldKey.tolerance(x.key));
    if (value !== undefined) out.tolerances[x.key] = value;
  }
  for (const r of s.ratios) {
    const acceptable = num(fieldKey.ratio(r.key, "acceptable"));
    const marginal = num(fieldKey.ratio(r.key, "marginal"));
    if (acceptable === undefined && marginal === undefined) continue;
    out.ratios[r.key] = {
      ...(acceptable !== undefined && { acceptable }),
      ...(marginal !== undefined && { marginal }),
    };
  }
  for (const n of s.norms) {
    const threshold = num(fieldKey.norm(n.id));
    if (threshold !== undefined) out.norms[n.id] = threshold;
  }
  for (const r of s.rules) {
    const enabled = flag(fieldKey.rule(r.id, "enabled"));
    const severity = choice(fieldKey.rule(r.id, "severity")) as typeof r.severity | undefined;
    const blocking = flag(fieldKey.rule(r.id, "blocking"));
    if (enabled === undefined && severity === undefined && blocking === undefined) continue;
    out.rules[r.id] = {
      ...(enabled !== undefined && { enabled }),
      ...(severity !== undefined && { severity }),
      ...(blocking !== undefined && { blocking }),
    };
  }
  for (const p of s.matrix.products) {
    const bands = p.bands.map((b, i) => ({
      up_to: num(fieldKey.band(p.key, i, "up_to_inr")),
      authority: choice(fieldKey.band(p.key, i, "authority")),
    }));
    if (bands.every((b) => b.up_to === undefined && b.authority === undefined)) continue;
    out.bands[p.key] = p.bands.map((b, i) => ({
      up_to_inr: typeof b.up_to_inr === "number" ? (bands[i]!.up_to ?? b.up_to_inr) : null,
      authority: bands[i]!.authority ?? b.authority,
    }));
  }
  for (const d of s.matrix.deviations) {
    const levels = num(fieldKey.deviation(d.category, "levels_above"));
    const atLeast = choice(fieldKey.deviation(d.category, "at_least"));
    if (levels === undefined && atLeast === undefined) continue;
    out.deviations[d.category] = {
      ...(levels !== undefined && { levels_above: levels }),
      ...(atLeast !== undefined && { at_least: atLeast }),
    };
  }
  return out;
}

const NUMBER = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 4 });

/** The unit beside an input, if it needs one. */
export function unitLabel(unit: string | null | undefined): string {
  if (!unit || unit === "ratio" || unit === "count" || unit === "rank") return "";
  if (unit === "inr") return t("admin.settings.unit.inr");
  return tOr(`admin.unit.${unit}`, unit);
}

/** An amount with its unit, as the screens write it: 1%, 1.2 times, 214 days, INR 2.00 cr. */
export function formatAmount(value: number, unit: string | null | undefined): string {
  if (unit === "inr") return formatInr(value);
  if (unit === "rank") return t("policy.rank", { n: NUMBER.format(value) });
  if (unit === "%") return `${NUMBER.format(value)}%`;
  const label = unitLabel(unit);
  return label ? `${NUMBER.format(value)} ${label}` : NUMBER.format(value);
}

/** Whether a rule runs, as a person reads it. */
export function enabledText(enabled: boolean): string {
  return t(enabled ? "admin.settings.value.flagOn" : "admin.settings.value.flagOff");
}

export function yesNoText(value: boolean): string {
  return t(value ? "admin.settings.value.flagYes" : "admin.settings.value.flagNo");
}

/** What changes in a field, as a person names it. */
export function changeFieldLabel(field: string): string {
  return tOr(`admin.settings.field.${field}`, field);
}

/** A value before or after a change: with its unit, a flag as on/off or yes/no, a severity in
 * words; the engine sends authorities by name. */
export function formatChangeValue(change: SettingChange, value: SettingChange["before"]): string {
  if (value === null) {
    return t(
      change.field === "up_to_inr" ? "admin.settings.value.open" : "admin.settings.value.none",
    );
  }
  if (typeof value === "boolean") {
    return change.field === "enabled" ? enabledText(value) : yesNoText(value);
  }
  if (change.field === "severity") return tOr(`severity.${value}`, String(value));
  if (typeof value === "number") return formatAmount(value, change.unit);
  return value;
}

/** The draft as the screen's controls use it. */
export type Editor = {
  /** Without config.publish the values are shown, not edited. */
  readOnly: boolean;
  state: (key: string) => FieldState;
  /** The value the engine would take: the draft's when valid, else the published one. */
  current: (key: string) => number | string | boolean | undefined;
  set: (key: string, value: DraftValue) => void;
  undo: (key: string) => void;
};

/** A note of at least this many characters is published with the version (engine/admin_config.py). */
export const NOTE_MIN = 3;
