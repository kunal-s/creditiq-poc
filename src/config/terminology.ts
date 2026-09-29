import { parse } from "yaml";
// Vite inlines this as a build-time string — the YAML file is the single
// authored source, never fetched or re-read at runtime (CLAUDE.md rule 4).
import raw from "../../terminology/rbl.yaml?raw";

export type TerminologyMap = Record<string, unknown>;

export const TERMINOLOGY: TerminologyMap = parse(raw) as TerminologyMap;

function resolve(path: string): unknown {
  return path.split(".").reduce<unknown>((node, key) => {
    if (node && typeof node === "object" && key in (node as Record<string, unknown>)) {
      return (node as Record<string, unknown>)[key];
    }
    return undefined;
  }, TERMINOLOGY);
}

/** Like t(), for open-ended codes from the engine (reason codes): the
 * configured label when there is one, else the code in plain words. */
export function tOr(path: string, fallback: string): string {
  const value = resolve(path);
  return value === undefined ? fallback.replace(/_/g, " ") : String(value);
}

/**
 * Look up a dot-path terminology key, e.g. `t("tenant.bank.name")`.
 * `params` fills `{placeholder}` tokens in the resolved string.
 */
export function t(path: string, params?: Record<string, string | number>): string {
  const value = resolve(path);
  if (value === undefined) {
    throw new Error(`terminology: no key "${path}" in terminology/rbl.yaml`);
  }
  const text = String(value);
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, token: string) =>
    token in params ? String(params[token]) : match,
  );
}
