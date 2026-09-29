import {
  CaseSchema,
  LoginResponseSchema,
  SessionUserSchema,
  type Case,
  type LoginResponse,
  type SessionUser,
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

async function request<T>(
  path: string,
  schema: { parse: (v: unknown) => T },
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) return undefined as T;
  return schema.parse(await response.json());
}

export const api = {
  listCases: () => request<Case[]>("/api/cases", { parse: (v) => CaseSchema.array().parse(v) }),
  getCase: (id: string) => request<Case>(`/api/cases/${encodeURIComponent(id)}`, CaseSchema),
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/auth/login", LoginResponseSchema, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  session: (token: string) =>
    request<SessionUser>("/api/auth/session", SessionUserSchema, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  logout: (token: string) =>
    request<undefined>(
      "/api/auth/logout",
      { parse: () => undefined },
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      },
    ),
};
