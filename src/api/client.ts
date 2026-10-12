import type {
  AdjudicationRequest,
  ApprovalMatrixConfig,
  ApprovingAuthority,
  Cam,
  CaseComparison,
  CaseCreate,
  CaseDetail,
  CaseFacts,
  CaseProgress,
  CaseProposal,
  CaseSummary,
  ChecklistTaxonomy,
  ComparisonArea,
  ComparisonItem,
  ConfigVersion,
  CrossVerificationView,
  DirectoryUser,
  EditableSettings,
  AuditPage,
  PolicyConfig,
  DocumentTypes,
  FieldValue,
  FileRecord,
  Finding,
  LoginResponse,
  LogicalDocument,
  Meta,
  Party,
  PdNote,
  PolicyAssessment,
  ProposalRequest,
  QueryItem,
  Readiness,
  ReferenceRecord,
  ReviewDecisionRequest,
  ReviewItem,
  SessionUser,
  SettingsChanges,
  SettingsPreview,
  SettingsPublished,
  SettingsPublishRequest,
  Spread,
  UploadResult,
  XvDecisionRequest,
  XvItem,
} from "./types";

const BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8010";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** The response's `detail` when it is structured (e.g. a 409 with duplicates). */
    public detail: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// The session token, supplied by domain/session.ts (kept there so this
// module has no React or storage dependency).
let tokenProvider: () => string | null = () => null;
let onUnauthorised: () => void = () => undefined;

export function configureAuth(getToken: () => string | null, unauthorised: () => void) {
  tokenProvider = getToken;
  onUnauthorised = unauthorised;
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  const token = tokenProvider();
  // JSON bodies are strings; multipart bodies (FormData) set their own
  // Content-Type with the boundary, so it must not be overridden.
  const json = typeof init?.body === "string";
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(json ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (response.status === 401 && token) onUnauthorised();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail: unknown = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail && typeof detail === "object" && "message" in detail
          ? String((detail as { message: unknown }).message)
          : response.statusText;
    throw new ApiError(response.status, message, detail);
  }
  return response;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await send(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const q = encodeURIComponent;

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  session: () => request<SessionUser>("/api/auth/session"),
  logout: () => request<undefined>("/api/auth/logout", { method: "POST" }),
  meta: () => request<Meta>("/api/meta"),

  listCases: () => request<CaseSummary[]>("/api/cases"),
  getCase: (id: string) => request<CaseDetail>(`/api/cases/${q(id)}`),
  caseProgress: (id: string) => request<CaseProgress>(`/api/cases/${q(id)}/progress`),
  proposeCase: (body: ProposalRequest) =>
    request<CaseProposal>("/api/cases/proposals", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createCase: (body: CaseCreate) =>
    request<CaseDetail>("/api/cases", { method: "POST", body: JSON.stringify(body) }),
  deleteCase: (id: string, reason: string) =>
    request<undefined>(`/api/cases/${q(id)}`, {
      method: "DELETE",
      body: JSON.stringify({ reason }),
    }),

  caseFiles: (id: string) => request<FileRecord[]>(`/api/cases/${q(id)}/files`),
  uploadFiles: (id: string, files: File[]) => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    return request<UploadResult>(`/api/cases/${q(id)}/files`, { method: "POST", body: form });
  },
  caseDocuments: (id: string) => request<LogicalDocument[]>(`/api/cases/${q(id)}/documents`),
  /** The rendered page image (PNG); `page` is the absolute page in the source file. */
  pageImage: async (id: string, documentId: string, page: number) => {
    const response = await send(`/api/cases/${q(id)}/documents/${q(documentId)}/pages/${page}`);
    return response.blob();
  },
  caseParties: (id: string) => request<Party[]>(`/api/cases/${q(id)}/parties`),
  caseFields: (id: string, documentId?: string) =>
    request<FieldValue[]>(
      `/api/cases/${q(id)}/fields${documentId ? `?document_id=${q(documentId)}` : ""}`,
    ),
  caseChecklist: (id: string) => request<Readiness>(`/api/cases/${q(id)}/checklist`),
  caseQueries: (id: string) => request<QueryItem[]>(`/api/cases/${q(id)}/queries`),
  caseFindings: (id: string) => request<Finding[]>(`/api/cases/${q(id)}/findings`),
  caseCrossVerification: (id: string) =>
    request<CrossVerificationView>(`/api/cases/${q(id)}/cross-verification`),
  /** Accept, dismiss or escalate a discrepancy; every decision needs a comment (F-19). */
  decideCrossVerification: (id: string, findingId: string, body: XvDecisionRequest) =>
    request<XvItem>(`/api/cases/${q(id)}/cross-verification/findings/${q(findingId)}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  /** Put what would complete a check that could not run on the query list (F-14). */
  queryCrossVerification: (id: string, findingId: string) =>
    request<XvItem>(`/api/cases/${q(id)}/cross-verification/findings/${q(findingId)}/query`, {
      method: "POST",
    }),
  caseFacts: (id: string) => request<CaseFacts>(`/api/cases/${q(id)}/facts`),
  casePolicy: (id: string) => request<PolicyAssessment>(`/api/cases/${q(id)}/policy`),
  caseApprovingAuthority: (id: string) =>
    request<ApprovingAuthority>(`/api/cases/${q(id)}/approving-authority`),
  caseComparison: (id: string) => request<CaseComparison>(`/api/cases/${q(id)}/comparison`),
  confirmReference: (id: string) =>
    request<ReferenceRecord>(`/api/cases/${q(id)}/reference/confirm`, { method: "POST" }),
  adjudicate: (id: string, area: ComparisonArea, key: string, body: AdjudicationRequest) =>
    request<ComparisonItem>(`/api/cases/${q(id)}/comparison/${q(area)}/${q(key)}/adjudication`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  caseSpread: (id: string) => request<Spread>(`/api/cases/${q(id)}/spread`),
  caseCam: (id: string) => request<Cam>(`/api/cases/${q(id)}/cam`),
  casePdNote: (id: string) => request<PdNote>(`/api/cases/${q(id)}/pd-note`),
  reviewQueue: (options: { caseId?: string; includeDecided?: boolean } = {}) => {
    const params = new URLSearchParams();
    if (options.caseId) params.set("case_id", options.caseId);
    if (options.includeDecided) params.set("include_decided", "true");
    const qs = params.toString();
    return request<ReviewItem[]>(`/api/review${qs ? `?${qs}` : ""}`);
  },
  decideReview: (itemId: string, body: ReviewDecisionRequest) =>
    request<ReviewItem>(`/api/review/${q(itemId)}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  documentTypes: () => request<DocumentTypes>("/api/config/document-types"),
  checklistTaxonomy: () => request<ChecklistTaxonomy>("/api/config/checklist-taxonomy"),
  policyConfig: () => request<PolicyConfig>("/api/config/policy"),
  approvalMatrixConfig: () => request<ApprovalMatrixConfig>("/api/config/approval-matrix"),
  configVersions: () => request<ConfigVersion[]>("/api/config/versions"),
  /** The settings an Administrator edits, as the version in force has them (F-00.6). */
  adminSettings: () => request<EditableSettings>("/api/admin/settings"),
  /** What the changes would change and why they could not be published; publishes nothing. */
  previewSettings: (changes: SettingsChanges) =>
    request<SettingsPreview>("/api/admin/settings/preview", {
      method: "POST",
      body: JSON.stringify(changes),
    }),
  /** Publish the changes as a new version; 422 with `detail.problems` when they cannot be. */
  publishSettings: (body: SettingsPublishRequest) =>
    request<SettingsPublished>("/api/admin/settings/publish", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  users: () => request<DirectoryUser[]>("/api/users"),
  audit: (params: { caseId?: string; actor?: string; action?: string; before?: number }) => {
    const q = new URLSearchParams();
    if (params.caseId) q.set("case_id", params.caseId);
    if (params.actor) q.set("actor", params.actor);
    if (params.action) q.set("action", params.action);
    if (params.before) q.set("before", String(params.before));
    q.set("limit", "50");
    return request<AuditPage>(`/api/audit?${q.toString()}`);
  },
};
