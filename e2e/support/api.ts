/// <reference types="node" />
// The engine API, answered in the browser with page.route (no engine runs
// during screen tests). State is per test: created cases and uploads persist
// for the rest of that test.
import type { Page, Request, Route } from "@playwright/test";
import type {
  CaseCreate,
  CaseDetail,
  CaseFacts,
  Finding,
  PolicyAssessment,
  CaseProgress,
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
  StageProgress,
  UploadResult,
} from "../../src/api/types";
import {
  AUDIT,
  CONFIG_VERSIONS,
  POLICY_CONFIG,
  USERS,
  ANALYST,
  API,
  CAM,
  CASES,
  DOCUMENTS,
  FACTS,
  FINDINGS,
  DOCUMENT_TYPES,
  FIELDS,
  KESTREL,
  KESTREL_CHECKLIST,
  KESTREL_QUERIES,
  LOOSE_FILES,
  META,
  ORIEL,
  PD_NOTE,
  POLICY,
  ORIEL_CHECKLIST,
  PAGE_PNG,
  PARTIES,
  REVIEW,
  SAFFRON,
  SPREAD,
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
  findings = new Map<string, Finding[]>([[KESTREL, FINDINGS]]);
  facts = new Map<string, CaseFacts>([[KESTREL, FACTS]]);
  policy = new Map<string, PolicyAssessment>([[KESTREL, POLICY]]);
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

  /** The stage progress, derived from the mock's documents and checklist as the engine does. */
  progress(caseId: string): CaseProgress {
    const docs = (this.documents.get(caseId) ?? []).filter(
      (d) => d.status !== "duplicate" && d.status !== "superseded",
    );
    const classified = docs.filter((d) =>
      ["classified", "extracted", "accepted", "in_review"].includes(d.status),
    );
    const blocked = docs.filter((d) => d.status === "unclassified" || d.status === "in_exception");
    const busy = docs.some((d) => ["received", "graded", "split"].includes(d.status));
    const items = this.checklists.get(caseId)?.items ?? [];
    const status = (started: boolean, running: boolean, attention: number, done: boolean) =>
      !started
        ? ("not_started" as const)
        : running
          ? ("in_progress" as const)
          : attention > 0 || !done
            ? ("needs_attention" as const)
            : ("done" as const);
    const documents: StageProgress = {
      key: "documents",
      done: classified.length,
      total: docs.length,
      attention: blocked.length,
      status: status(docs.length > 0, busy, blocked.length, true),
    };
    const inReview = classified.filter((d) => d.status === "in_review").length;
    const extraction: StageProgress = {
      key: "extraction",
      done: classified.filter((d) => d.status === "accepted").length,
      total: classified.length,
      attention: inReview,
      status: status(classified.length > 0, false, inReview, true),
    };
    const open = items.filter((i) => i.status === "missing" || i.status === "insufficient");
    const completeness: StageProgress = {
      key: "completeness",
      done: items.filter((i) => i.status === "satisfied" || i.status === "waived").length,
      total: items.length,
      attention: open.length,
      status: status(docs.length > 0, busy, 0, this.checklists.get(caseId)?.gate_met ?? false),
    };
    const later = (key: StageProgress["key"]): StageProgress => ({
      key,
      status: "not_started",
      done: 0,
      total: 0,
      attention: 0,
    });
    const stages = [
      documents,
      extraction,
      completeness,
      later("cross_verification"),
      later("policy"),
      later("outputs"),
    ];
    const names = ["Documents", "Extraction", "Completeness", "CrossVerification"] as const;
    const first = stages.findIndex((s) => s.status !== "done");
    return {
      case_id: caseId,
      stage: docs.length === 0 ? "Intake" : names[Math.min(first, 3)]!,
      stages,
    };
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
      ["GET", /^\/api\/config\/policy$/, () => ({ json: POLICY_CONFIG })],
      ["GET", /^\/api\/config\/versions$/, () => ({ json: CONFIG_VERSIONS })],
      ["GET", /^\/api\/users$/, () => ({ json: USERS })],
      ["GET", /^\/api\/audit$/, () => ({ json: AUDIT })],
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
        new RegExp(`^/api/cases/${id}/progress$`),
        (_req, m) => ({ json: this.progress(decodeURIComponent(m[1]!)) }),
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
      ["GET", new RegExp(`^/api/cases/${id}/findings$`), one(this.findings, [])],
      ["GET", new RegExp(`^/api/cases/${id}/spread$`), () => ({ json: SPREAD })],
      ["GET", new RegExp(`^/api/cases/${id}/cam$`), () => ({ json: CAM })],
      ["GET", new RegExp(`^/api/cases/${id}/pd-note$`), () => ({ json: PD_NOTE })],
      [
        "GET",
        new RegExp(`^/api/cases/${id}/policy$`),
        (_req, m) => {
          const caseId = decodeURIComponent(m[1]!);
          return { json: this.policy.get(caseId) ?? { case_id: caseId, period: null, norms: [] } };
        },
      ],
      [
        "GET",
        new RegExp(`^/api/cases/${id}/facts$`),
        (_req, m) => {
          const caseId = decodeURIComponent(m[1]!);
          return {
            json: this.facts.get(caseId) ?? {
              ...FACTS,
              case_id: caseId,
              turnover: [],
              credits: [],
              obligations: [],
              accounts: [],
            },
          };
        },
      ],
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
