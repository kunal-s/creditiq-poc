import { z } from "zod";

// Mirrors engine/schemas.py by hand until the client is generated from the
// service's OpenAPI schema.

// Case stages (docs/functional-requirements.md §7).
export const StageSchema = z.enum(["Intake", "Readiness", "Appraisal", "Outputs", "Completed"]);
export type Stage = z.infer<typeof StageSchema>;

export const CaseSchema = z.object({
  id: z.string(),
  borrower: z.string(),
  constitution: z.string(),
  product: z.string(),
  amount: z.string(),
  stage: StageSchema,
  rm: z.string(),
  created: z.string(),
  openReviewItems: z.number(),
});
export type Case = z.infer<typeof CaseSchema>;

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
