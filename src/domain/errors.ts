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
