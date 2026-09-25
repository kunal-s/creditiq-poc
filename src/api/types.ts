import { z } from "zod";

// Mirrors engine/schemas.py by hand until the client is generated from the
// service's OpenAPI schema (plan.md section 3).

export const StageSchema = z.enum([
  "Identity",
  "Data",
  "Spread",
  "Cross-Verification",
  "Draft",
  "Submission",
  "Completed",
]);
export type Stage = z.infer<typeof StageSchema>;

export const STAGE_ROUTE: Record<Stage, string> = {
  Identity: "identity",
  Data: "data",
  Spread: "spread",
  "Cross-Verification": "cross-verification",
  Draft: "draft",
  Submission: "submission",
  Completed: "submission",
};

export const CaseSchema = z.object({
  id: z.string(),
  borrower: z.string(),
  sector: z.string(),
  pan: z.string(),
  gstin: z.string(),
  proposal: z.string(),
  facilities: z.string(),
  exposure: z.string(),
  stage: StageSchema,
  analyst: z.string(),
  rm: z.string(),
  started: z.string(),
  completed: z.string().optional(),
  rating: z.string(),
  ratingLabel: z.string(),
  discrepancies: z.number(),
  reviewDue: z.string().optional(),
  branch: z.string(),
});
export type Case = z.infer<typeof CaseSchema>;

export const RoleSchema = z.object({
  id: z.string(),
  label: z.string(),
});
export type Role = z.infer<typeof RoleSchema>;

export const DirectoryUserSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  roleLabel: z.string(),
  email: z.string(),
  branch: z.string(),
});
export type DirectoryUser = z.infer<typeof DirectoryUserSchema>;

export const SessionUserSchema = z.object({
  id: z.string(),
  name: z.string(),
  role: z.string(),
  roleLabel: z.string(),
  email: z.string(),
  branch: z.string(),
  initials: z.string(),
  navGroups: z.array(z.string()),
});
export type SessionUser = z.infer<typeof SessionUserSchema>;

export const LoginResponseSchema = z.object({
  token: z.string(),
  user: SessionUserSchema,
});
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
