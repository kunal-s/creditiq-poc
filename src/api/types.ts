// Types for the engine API, generated from its OpenAPI schema
// (docs/functional-requirements.md AD-4). Run `npm run gen:api` after
// changing engine/contracts; never edit schema.gen.ts by hand.
import type { components } from "./schema.gen";

type S = components["schemas"];

export type CaseSummary = S["CaseSummary"];
export type CaseDetail = S["CaseDetail"];
export type CaseCreate = S["CaseCreate"];
export type HeaderField = S["HeaderField"];
export type Stage = CaseSummary["stage"];
export type FileRecord = S["FileRecord"];
export type LogicalDocument = S["LogicalDocument"];
export type PageInfo = S["PageInfo"];
export type Classification = S["Classification"];
export type FieldValue = S["FieldValue"];
export type Evidence = S["Evidence"];
export type Readiness = S["Readiness"];
export type ChecklistItemState = S["ChecklistItemState"];
export type QueryItem = S["QueryItem"];
export type Finding = S["Finding"];
export type ReviewItem = S["ReviewItem"];
export type SessionUser = S["SessionUser"];
export type LoginResponse = S["LoginResponse"];
export type Meta = S["Meta"];
