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
export type FileStatus = FileRecord["status"];
export type LogicalDocument = S["LogicalDocument"];
export type DocumentStatus = LogicalDocument["status"];
export type Grade = LogicalDocument["grade"];
export type PageInfo = S["PageInfo"];
export type Classification = S["Classification"];
export type ExitTier = Classification["exit_tier"];
export type Candidate = S["Candidate"];
export type FieldValue = S["FieldValue"];
export type FieldStatus = FieldValue["status"];
export type FieldMethod = FieldValue["method"];
export type Evidence = S["Evidence"];
export type Readiness = S["Readiness"];
export type ChecklistItemState = S["ChecklistItemState"];
export type ChecklistStatus = ChecklistItemState["status"];
export type ChecklistTaxonomy = S["ChecklistTaxonomySection"];
export type QueryItem = S["QueryItem"];
export type QueryGroup = QueryItem["group"];
export type Finding = S["Finding"];
export type ReviewItem = S["ReviewItem"];
export type ReviewKind = ReviewItem["kind"];
export type ReviewDecision = NonNullable<ReviewItem["decision"]>;
export type ReviewDecisionRequest = S["ReviewDecisionRequest"];
export type SessionUser = S["SessionUser"];
export type LoginResponse = S["LoginResponse"];
export type Meta = S["Meta"];
export type Option = S["Option"];
export type CaseProposal = S["CaseProposal"];
export type ProposalRequest = S["ProposalRequest"];
export type ProposedField = S["ProposedField"];
export type ProposedStatus = ProposedField["status"];
export type ProposedCandidate = S["ProposedCandidate"];
export type Span = S["Span"];
export type UploadResult = S["UploadResult"];
export type Party = S["Party"];
export type PartyRole = Party["role"];
export type DocumentTypeDef = S["DocumentTypeDef"];
export type DocumentTypeGroup = DocumentTypeDef["group"];
export type DocumentTypes = S["DocumentTypesSection"];
