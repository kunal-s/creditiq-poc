import { ApiError } from "@/api/client";

/** How a failed request should be presented. */
export type ErrorKind =
  | "notAvailable" // 501: the engine declares the endpoint, its feature is not live yet
  | "forbidden" // 403: the user's role does not include this
  | "notFound" // 404
  | "noConfig" // 503: no published configuration
  | "invalid" // 422
  | "conflict" // 409
  | "unreachable" // network failure
  | "failed"; // anything else

export function errorKind(error: unknown): ErrorKind {
  if (error instanceof ApiError) {
    if (error.status === 501) return "notAvailable";
    if (error.status === 403) return "forbidden";
    if (error.status === 404) return "notFound";
    if (error.status === 503) return "noConfig";
    if (error.status === 422) return "invalid";
    if (error.status === 409) return "conflict";
    return "failed";
  }
  if (error instanceof TypeError) return "unreachable";
  return "failed";
}

export function isNotAvailable(error: unknown): boolean {
  return errorKind(error) === "notAvailable";
}

/** The engine's answer to a role without the permission (engine/deps.py), written for the log:
 * the person is shown the designed state instead. */
const MISSING_PERMISSION = /^role '[^']*' lacks '[^']*'$/;

/** The engine's own words for a failed request (its `detail`, or the detail's message), if it
 * gave any: not the browser's or the HTTP status text, nor a validation report. */
export function engineWords(error: unknown): string | null {
  if (!(error instanceof ApiError) || !error.message) return null;
  const detail = error.detail;
  const worded =
    typeof detail === "string" ||
    (detail !== null && typeof detail === "object" && "message" in detail);
  return worded ? error.message : null;
}

/**
 * The engine's refusal, word for word, when it is written for the person who made the request: a
 * comment too short (422), an item decided or changed meanwhile (409), a decision that is someone
 * else's to make (403). Null for anything else (the service unreachable or failing, a role
 * without the permission, a refusal the engine did not word), which is shown as the designed
 * state (ErrorState).
 */
export function refusal(error: unknown): string | null {
  const words = engineWords(error);
  if (words === null) return null;
  const kind = errorKind(error);
  if (kind === "invalid" || kind === "conflict") return words;
  if (kind === "forbidden" && !MISSING_PERMISSION.test(words)) return words;
  return null;
}
