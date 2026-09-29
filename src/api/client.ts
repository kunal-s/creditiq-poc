import type {
  CaseCreate,
  CaseDetail,
  CaseSummary,
  FieldValue,
  FileRecord,
  Finding,
  LoginResponse,
  LogicalDocument,
  Meta,
  QueryItem,
  Readiness,
  ReviewItem,
  SessionUser,
} from "./types";

const BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = tokenProvider();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (response.status === 401 && token) onUnauthorised();
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
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
  createCase: (body: CaseCreate) =>
    request<CaseDetail>("/api/cases", { method: "POST", body: JSON.stringify(body) }),

  caseFiles: (id: string) => request<FileRecord[]>(`/api/cases/${q(id)}/files`),
  caseDocuments: (id: string) => request<LogicalDocument[]>(`/api/cases/${q(id)}/documents`),
  caseFields: (id: string, documentId?: string) =>
    request<FieldValue[]>(
      `/api/cases/${q(id)}/fields${documentId ? `?document_id=${q(documentId)}` : ""}`,
    ),
  caseChecklist: (id: string) => request<Readiness>(`/api/cases/${q(id)}/checklist`),
  caseQueries: (id: string) => request<QueryItem[]>(`/api/cases/${q(id)}/queries`),
  caseFindings: (id: string) => request<Finding[]>(`/api/cases/${q(id)}/findings`),
  reviewQueue: (caseId?: string) =>
    request<ReviewItem[]>(`/api/review${caseId ? `?case_id=${q(caseId)}` : ""}`),
};
