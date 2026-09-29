import type {
  CaseCreate,
  CaseDetail,
  CaseProposal,
  CaseSummary,
  ChecklistTaxonomy,
  DocumentTypes,
  FieldValue,
  FileRecord,
  Finding,
  LoginResponse,
  LogicalDocument,
  Meta,
  Party,
  ProposalRequest,
  QueryItem,
  Readiness,
  ReviewDecisionRequest,
  ReviewItem,
  SessionUser,
  UploadResult,
} from "./types";

const BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000";

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
};
