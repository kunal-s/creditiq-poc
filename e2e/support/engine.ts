/// <reference types="node" />
// Helpers for the integration specs, which drive the REAL engine (no page.route
// mocking). The engine runs with CREDITIQ_INGEST=stub, so document processing
// replays the recorded results in tests/fixtures/ingest/ keyed by file hash:
// deterministic plumbing, NOT a test of extraction accuracy.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { basename, resolve } from "node:path";

import type { APIRequestContext, Page } from "@playwright/test";
import { request as pwRequest } from "@playwright/test";

export const REPO_ROOT = resolve(import.meta.dirname, "..", "..");
/** The engine the integration specs talk to (see playwright.config.ts). */
export const ENGINE = process.env["E2E_ENGINE_URL"] ?? "http://localhost:8011";
/** The isolated, disposable data root that engine runs on. */
export const DATA_ROOT = process.env["E2E_DATA_ROOT"] ?? resolve(REPO_ROOT, "workflow", "data-e2e");
/** The fixed as_of the functional pass pins, as tests/conftest.py does. */
export const TEST_AS_OF = "2026-09-29";

export const PASSWORD = "CreditIQ-2026!";
export const RM = "arjun.deshpande@rblbank.com";
export const ANALYST = "ananya.krishnan@rblbank.com";
export const MANAGER = "meenal.kulkarni@rblbank.com";

export type Role = "rm" | "analyst" | "manager";
const EMAIL: Record<Role, string> = { rm: RM, analyst: ANALYST, manager: MANAGER };

export type Session = { token: string; user: Record<string, unknown> };

/** A bare API context against the engine, with no stored credentials. */
export async function engineApi(): Promise<APIRequestContext> {
  return pwRequest.newContext({ baseURL: ENGINE });
}

/** Sign in through the real API and return the session the screens store. */
export async function signIn(role: Role): Promise<Session> {
  const api = await engineApi();
  try {
    const res = await api.post("/api/auth/login", {
      data: { email: EMAIL[role], password: PASSWORD },
    });
    if (!res.ok())
      throw new Error(`sign-in as ${role} failed: ${res.status()} ${await res.text()}`);
    return (await res.json()) as Session;
  } finally {
    await api.dispose();
  }
}

/** An API context that carries `role`'s bearer token. */
export async function asRole(role: Role): Promise<APIRequestContext> {
  const { token } = await signIn(role);
  return pwRequest.newContext({
    baseURL: ENGINE,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
}

/** Put a session in localStorage so the screens load signed in, as the app does. */
export async function signedInAs(page: Page, role: Role): Promise<Session> {
  const session = await signIn(role);
  await page.addInitScript(
    (s) => window.localStorage.setItem("creditiq.session", JSON.stringify(s)),
    session,
  );
  return session;
}

/** Put an arbitrary (e.g. tampered or expired) session in localStorage. */
export async function withStoredSession(page: Page, session: unknown): Promise<void> {
  await page.addInitScript(
    (s) => window.localStorage.setItem("creditiq.session", JSON.stringify(s)),
    session,
  );
}

/**
 * Pin a case's `as_of`, the way tests/conftest.py `set_as_of` does: there is no
 * API for it, and every age and window rule reads it (FRD principle 8, no wall
 * clock). Call it straight after creating the case and BEFORE uploading, so all
 * processing sees the pinned date.
 */
export function setAsOf(caseId: string, asOf: string = TEST_AS_OF): void {
  execFileSync(
    resolve(REPO_ROOT, ".venv", "bin", "python"),
    [
      "-c",
      [
        "import sys",
        "from pathlib import Path",
        "from engine import db",
        "conn = db.connect(Path(sys.argv[1]))",
        "try:",
        "    cur = conn.execute('UPDATE cases SET as_of = ? WHERE id = ?', (sys.argv[3], sys.argv[2]))",
        "    assert cur.rowcount == 1, f'no case {sys.argv[2]!r} to pin'",
        "finally:",
        "    conn.close()",
      ].join("\n"),
      DATA_ROOT,
      caseId,
      asOf,
    ],
    { cwd: REPO_ROOT, env: { ...process.env, CREDITIQ_DATA_ROOT: DATA_ROOT }, stdio: "pipe" },
  );
}

export type NewCase = {
  borrower?: string;
  constitution?: string;
  facilities?: string[];
  amount_inr?: number;
  channel?: string;
  pan?: string | null;
  gstin?: string | null;
  duplicate_override_reason?: string;
};

/** Create a case over the API. Borrower defaults to a unique name so specs stay independent. */
export async function createCase(
  api: APIRequestContext,
  overrides: NewCase = {},
): Promise<{ id: string; body: Record<string, unknown> }> {
  const body = {
    borrower: `Probe Works ${Date.now()}-${Math.random().toString(36).slice(2, 7)} Pvt Ltd`,
    constitution: "private_limited",
    facilities: ["cash_credit", "term_loan"],
    amount_inr: 75_000_000,
    channel: "email",
    ...overrides,
  };
  const res = await api.post("/api/cases", { data: body });
  if (res.status() !== 201) {
    throw new Error(`createCase failed: ${res.status()} ${await res.text()}`);
  }
  const created = (await res.json()) as Record<string, unknown>;
  return { id: created["id"] as string, body: created };
}

/** Create a case and pin its as_of in one step: the functional pass's starting point. */
export async function createPinnedCase(
  api: APIRequestContext,
  overrides: NewCase = {},
  asOf: string = TEST_AS_OF,
): Promise<string> {
  const { id } = await createCase(api, overrides);
  setAsOf(id, asOf);
  return id;
}

/** The file names of a fixture case set ("complete" = Kestrel, "partial" = Heronbay). */
export function fixtureSet(name: "complete" | "partial"): string[] {
  const path = resolve(REPO_ROOT, "tests", "fixtures", "cases.json");
  return (JSON.parse(readFileSync(path, "utf-8")) as Record<string, string[]>)[name]!;
}

export function fixtureFile(name: string): { name: string; mimeType: string; buffer: Buffer } {
  return {
    name: basename(name),
    mimeType: "application/octet-stream",
    buffer: readFileSync(resolve(REPO_ROOT, "tests", "fixtures", "files", name)),
  };
}

/** Upload files to a case over the API. Returns the UploadResult. */
export async function uploadFiles(
  api: APIRequestContext,
  caseId: string,
  names: string[],
): Promise<{ status: number; body: Record<string, unknown> }> {
  const res = await api.post(`/api/cases/${encodeURIComponent(caseId)}/files`, {
    multipart: { files: names.map(fixtureFile) } as never,
  });
  const text = await res.text();
  let body: Record<string, unknown> = {};
  try {
    body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    body = { raw: text };
  }
  return { status: res.status(), body };
}

type Stage = { key: string; status: string };

/**
 * Wait until the background worker (a 2 s poll, F-02.3) has carried the case's
 * stages out of `in_progress`. Polls the API; never a fixed sleep.
 */
export async function waitForProcessing(
  api: APIRequestContext,
  caseId: string,
  timeoutMs = 180_000,
): Promise<Record<string, string>> {
  const deadline = Date.now() + timeoutMs;
  let last = "(never read)";
  while (Date.now() < deadline) {
    const res = await api.get(`/api/cases/${encodeURIComponent(caseId)}/progress`);
    if (res.ok()) {
      const page = (await res.json()) as { stage: string; stages: Stage[] };
      const byKey = Object.fromEntries(page.stages.map((s) => [s.key, s.status]));
      last = `stage=${page.stage} ${JSON.stringify(byKey)}`;
      if (!page.stages.some((s) => s.status === "in_progress")) return byKey;
    } else {
      last = `progress ${res.status()}: ${await res.text()}`;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`case ${caseId} still processing after ${timeoutMs} ms; last progress: ${last}`);
}

/** Upload a fixture set and wait for the pipeline to settle. */
export async function loadCase(
  api: APIRequestContext,
  caseId: string,
  set: "complete" | "partial",
): Promise<Record<string, string>> {
  const upload = await uploadFiles(api, caseId, fixtureSet(set));
  if (upload.status !== 202) {
    throw new Error(`upload failed: ${upload.status} ${JSON.stringify(upload.body)}`);
  }
  return waitForProcessing(api, caseId);
}

/** Delete a case so each spec cleans up after itself. Never throws. */
export async function deleteCase(api: APIRequestContext, caseId: string): Promise<void> {
  try {
    await api.delete(`/api/cases/${encodeURIComponent(caseId)}`, {
      data: { reason: "automated test cleanup" },
    });
  } catch {
    // Cleanup is best-effort: a failure here must not mask the spec's result.
  }
}

/** The published configuration version, for the "nothing learns at runtime" check. */
export async function configVersion(api: APIRequestContext): Promise<string> {
  const res = await api.get("/api/config/version");
  if (!res.ok()) throw new Error(`config version: ${res.status()} ${await res.text()}`);
  return JSON.stringify(await res.json());
}
