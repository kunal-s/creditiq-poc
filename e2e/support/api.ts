/// <reference types="node" />
// The engine API, answered in the browser with page.route (no engine runs
// during screen tests). State is per test: created cases and uploads persist
// for the rest of that test.
import type { Page, Request, Route } from "@playwright/test";
import type {
  CaseCreate,
  CaseDetail,
  CaseProposal,
  CaseSummary,
  FieldValue,
  FileRecord,
  LogicalDocument,
  Party,
  QueryItem,
  Readiness,
  ReviewDecisionRequest,
  ReviewItem,
  SessionUser,
  UploadResult,
} from "../../src/api/types";
import {
  ANALYST,
  API,
  CASES,
  DOCUMENTS,
  DOCUMENT_TYPES,
  FIELDS,
  KESTREL,
  KESTREL_CHECKLIST,
  KESTREL_QUERIES,
  LOOSE_FILES,
  META,
  ORIEL,
  ORIEL_CHECKLIST,
  PAGE_PNG,
  PARTIES,
  REVIEW,
  SAFFRON,
  SAFFRON_CHECKLIST,
  TAXONOMY,
  ZIP_FILES,
  detail,
  proposal,
} from "../fixtures/data";

type Reply = { status?: number; json?: unknown; body?: Buffer; contentType?: string };
type Handler = (req: Request, match: RegExpMatchArray) => Reply | Promise<Reply>;

export const NOT_YET: Reply = { status: 501, json: { detail: "not implemented yet" } };

export class MockApi {
  user: SessionUser = ANALYST;
  cases: CaseSummary[] = structuredClone(CASES);
  details = new Map<string, CaseDetail>(this.cases.map((c) => [c.id, detail(c)]));
  checklists = new Map<string, Readiness>([
    [KESTREL, KESTREL_CHECKLIST],
    [SAFFRON, SAFFRON_CHECKLIST],
    [ORIEL, ORIEL_CHECKLIST],
  ]);
  queries = new Map<string, QueryItem[]>([[KESTREL, KESTREL_QUERIES]]);
  files = new Map<string, FileRecord[]>([[KESTREL, [...ZIP_FILES, ...LOOSE_FILES]]]);
  documents = new Map<string, LogicalDocument[]>([[KESTREL, DOCUMENTS]]);
  fields = new Map<string, FieldValue[]>([[KESTREL, FIELDS]]);
  parties = new Map<string, Party[]>([[KESTREL, PARTIES]]);
  review: ReviewItem[] = structuredClone(REVIEW);
  /** Document reads still to answer as "received" before the final state. */
  pendingReads = new Map<string, number>();
  proposal: CaseProposal = proposal();
  /** Requests received, as "METHOD /path" with the parsed JSON body if any. */
  calls: { key: string; body: unknown }[] = [];
  overrides: [string, RegExp, Handler][] = [];

  /** Replace one endpoint's answer, e.g. on("POST", /^\/api\/cases\/proposals$/, () => NOT_YET). */
  on(method: string, path: RegExp, handler: Handler) {
    this.overrides.unshift([method, path, handler]);
    return this;
  }

  called(method: string, path: string) {
    return this.calls.filter((c) => c.key === `${method} ${path}`);
  }

  private routes(): [string, RegExp, Handler][] {
    const id = "([^/]+)";
    const one =
      <T>(map: Map<string, T>, fallback: T): Handler =>
      (_req, m) => ({ json: map.get(decodeURIComponent(m[1]!)) ?? fallback });
    return [
      ...this.overrides,
      ["GET", /^\/api\/auth\/session$/, () => ({ json: this.user })],
      [
        "POST",
        /^\/api\/auth\/login$/,
        () => ({ json: { token: "session-token", user: this.user } }),
      ],
      ["POST", /^\/api\/auth\/logout$/, () => ({ status: 204 })],
      ["GET", /^\/api\/meta$/, () => ({ json: META })],
      ["GET", /^\/api\/config\/document-types$/, () => ({ json: DOCUMENT_TYPES })],
      ["GET", /^\/api\/config\/checklist-taxonomy$/, () => ({ json: TAXONOMY })],
      ["GET", /^\/api\/cases$/, () => ({ json: this.cases })],
      ["POST", /^\/api\/cases\/proposals$/, () => ({ json: this.proposal })],
      ["POST", /^\/api\/cases$/, (req) => this.create(req.postDataJSON() as CaseCreate)],
      [
        "GET",
        new RegExp(`^/api/cases/${id}$`),
        (_req, m) => {
          const c = this.details.get(decodeURIComponent(m[1]!));
          return c ? { json: c } : { status: 404, json: { detail: "no case" } };
        },
      ],
      [
        "DELETE",
        new RegExp(`^/api/cases/${id}$`),
        (_req, m) => {
          const caseId = decodeURIComponent(m[1]!);
          if (!this.details.has(caseId)) return { status: 404, json: { detail: "no case" } };
          this.details.delete(caseId);
          this.cases = this.cases.filter((c) => c.id !== caseId);
          return { status: 204 };
        },
      ],
      [
        "GET",
        new RegExp(`^/api/cases/${id}/checklist$`),
        one(this.checklists, {
          score_pct: 0,
          gate_pct: 85,
          gate_met: false,
          blocking_open: 0,
          provisional: true,
          ready_for_credit: false,
          items: [],
        } satisfies Readiness),
      ],
      ["GET", new RegExp(`^/api/cases/${id}/queries$`), one(this.queries, [])],
      ["GET", new RegExp(`^/api/cases/${id}/files$`), one(this.files, [])],
      ["POST", new RegExp(`^/api/cases/${id}/files$`), (req, m) => this.upload(req, m[1]!)],
      [
        "GET",
        new RegExp(`^/api/cases/${id}/documents$`),
        (_req, m) => {
          const caseId = decodeURIComponent(m[1]!);
          const docs = this.documents.get(caseId) ?? [];
          const pending = this.pendingReads.get(caseId) ?? 0;
          if (pending > 0) {
            this.pendingReads.set(caseId, pending - 1);
            return { json: docs.map((d) => ({ ...d, status: "received" })) };
          }
          return { json: docs };
        },
      ],
      [
        "GET",
        new RegExp(`^/api/cases/${id}/documents/${id}/pages/(\\d+)$`),
        () => ({ body: PAGE_PNG, contentType: "image/png" }),
      ],
      ["GET", new RegExp(`^/api/cases/${id}/fields$`), one(this.fields, [])],
      ["GET", new RegExp(`^/api/cases/${id}/parties$`), one(this.parties, [])],
      ["GET", new RegExp(`^/api/cases/${id}/findings$`), () => ({ json: [] })],
      [
        "GET",
        /^\/api\/review$/,
        (req) => {
          const all = new URL(req.url()).searchParams.get("include_decided") === "true";
          return { json: all ? this.review : this.review.filter((r) => r.status === "open") };
        },
      ],
      [
        "POST",
        new RegExp(`^/api/review/${id}/decision$`),
        (req, m) => this.decide(m[1]!, req.postDataJSON() as ReviewDecisionRequest),
      ],
    ];
  }

  private create(body: CaseCreate): Reply {
    const n = 31 + this.cases.length - CASES.length;
    const s: CaseSummary = {
      id: `BBG-2026-0000${n}`,
      borrower: body.borrower,
      constitution: body.constitution,
      facilities: body.facilities,
      amount_inr: body.amount_inr,
      stage: "Intake",
      rm: this.user.name,
      created_at: "2026-09-29T09:00:00Z",
      open_review_items: 0,
    };
    this.cases.unshift(s);
    const d = detail(s, {
      pan: body.pan ?? null,
      gstin: body.gstin ?? null,
      header: body.header ?? {},
    });
    this.details.set(s.id, d);
    return { status: 201, json: d };
  }

  private upload(req: Request, rawId: string): Reply {
    const caseId = decodeURIComponent(rawId);
    const text = req.postDataBuffer()?.toString("latin1") ?? "";
    const names = Array.from(text.matchAll(/filename="([^"]+)"/g), (m) => m[1]!);
    const existing = this.files.get(caseId) ?? [];
    const added: FileRecord[] = names.flatMap((name, i) => {
      if (name.endsWith(".zip")) {
        // The archive's members, each read in turn: documents appear first
        // as received, then final after a few polls (F-02.2).
        this.documents.set(
          caseId,
          DOCUMENTS.map((d) => ({ ...d, case_id: caseId })),
        );
        this.pendingReads.set(caseId, 2);
        return ZIP_FILES.map((f) => ({ ...f, case_id: caseId }));
      }
      const loose = LOOSE_FILES.find((f) => f.original_name === name);
      if (loose?.status === "rejected") return [{ ...loose, case_id: caseId }];
      const same = existing.find((f) => f.original_name === name);
      return [
        {
          ...(loose ?? ZIP_FILES[0]!),
          id: `up-${existing.length + i}`,
          case_id: caseId,
          original_name: name,
          archive_path: null,
          status: same ? "duplicate" : "registered",
          duplicate_of: same ? same.id : null,
          reason: null,
        } satisfies FileRecord,
      ];
    });
    this.files.set(caseId, [...existing, ...added]);
    const result: UploadResult = { files: added, job_id: "job-1" };
    return { status: 202, json: result };
  }

  private decide(rawId: string, body: ReviewDecisionRequest): Reply {
    const item = this.review.find((r) => r.id === decodeURIComponent(rawId));
    if (!item) return { status: 404, json: { detail: "no item" } };
    Object.assign(item, {
      status: "decided",
      decision: body.decision,
      reason: body.reason ?? null,
      decided_by: this.user.name,
      decided_at: "2026-09-29T10:00:00Z",
    });
    return { json: item };
  }

  async install(page: Page) {
    await page.route(`${API}/api/**`, (route) => this.handle(route));
  }

  private async handle(route: Route) {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: cors() });
    let body: unknown = null;
    try {
      body = req.postDataJSON();
    } catch {
      body = null;
    }
    this.calls.push({ key: `${method} ${url.pathname}`, body });
    for (const [m, path, handler] of this.routes()) {
      const match = url.pathname.match(path);
      if (m === method && match) {
        const reply = await handler(req, match);
        return route.fulfill({
          status: reply.status ?? 200,
          headers: cors(),
          contentType: reply.contentType ?? "application/json",
          body: reply.body ?? (reply.json === undefined ? "" : JSON.stringify(reply.json)),
        });
      }
    }
    return route.fulfill({
      status: 404,
      headers: cors(),
      contentType: "application/json",
      body: JSON.stringify({ detail: `no mock for ${method} ${url.pathname}` }),
    });
  }
}

function cors() {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "*",
    "access-control-allow-methods": "*",
  };
}

/** Start signed in: the stored session the screens read on load. */
export async function signedIn(page: Page, api: MockApi, user: SessionUser = api.user) {
  api.user = user;
  await api.install(page);
  await page.addInitScript(
    (session) => window.localStorage.setItem("creditiq.session", JSON.stringify(session)),
    { token: "session-token", user },
  );
}

/** True when the page scrolls sideways (F-06.1 forbids it at phone width). */
export async function scrollsSideways(page: Page): Promise<boolean> {
  return page.evaluate(() =>
    [document.documentElement, document.querySelector("main")]
      .filter((el): el is HTMLElement => el !== null)
      .some((el) => el.scrollWidth > el.clientWidth + 1),
  );
}
