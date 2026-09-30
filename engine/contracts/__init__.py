"""The API contract (docs/functional-requirements.md AD-4).

These pydantic models are the single source for:
- the engine's HTTP API (FastAPI response models, and so its OpenAPI);
- the TypeScript types the screens use (`npm run gen:api` -> src/api/schema.gen.ts);
- the document-processing sidecar's result schema
  (contracts/ingest-result.schema.json).

Change a model here, regenerate, and both sides see the change.
"""

from .appraisal import (
    ChecklistItemState,
    Finding,
    FindingSide,
    QueryItem,
    Readiness,
    ReviewDecisionRequest,
    ReviewItem,
)
from .case import (
    CaseCreate,
    CaseDeleteRequest,
    CaseDetail,
    CaseProgress,
    CaseSummary,
    HeaderField,
    StageKey,
    StageProgress,
    StageStatus,
)
from .common import Evidence, Grade, Stage
from .policy import NormInput, NormOutcome, NormResult, PolicyAssessment
from .facts import (
    AccountCredits,
    AccountFact,
    CaseFacts,
    Exclusion,
    FacilityFact,
    FactValue,
    IdentityFacts,
    Obligation,
    PersonSet,
    TurnoverFigure,
    TurnoverYear,
)
from .documents import (
    Candidate,
    Classification,
    FieldValue,
    FileRecord,
    LogicalDocument,
    PageInfo,
)
from .ingest import (
    DocumentDefect,
    ExtractedField,
    IngestDocument,
    IngestFile,
    IngestFileOutcome,
    IngestRequest,
    IngestResult,
    TypeAssignment,
)
from .intake import (
    CaseProposal,
    Party,
    ProposalRequest,
    ProposedCandidate,
    ProposedField,
    Span,
    StrippedSpan,
    UploadResult,
)
from .session import LoginRequest, LoginResponse, Meta, Option, SessionUser

__all__ = [
    "NormInput",
    "NormOutcome",
    "NormResult",
    "PolicyAssessment",
    "AccountCredits",
    "AccountFact",
    "CaseFacts",
    "Exclusion",
    "FacilityFact",
    "FactValue",
    "IdentityFacts",
    "Obligation",
    "PersonSet",
    "TurnoverFigure",
    "TurnoverYear",
    "Candidate",
    "CaseProposal",
    "CaseCreate",
    "CaseDeleteRequest",
    "DocumentDefect",
    "ExtractedField",
    "IngestFile",
    "Party",
    "ProposalRequest",
    "ProposedCandidate",
    "ProposedField",
    "Span",
    "StrippedSpan",
    "TypeAssignment",
    "UploadResult",
    "CaseDetail",
    "CaseSummary",
    "ChecklistItemState",
    "Classification",
    "Evidence",
    "FieldValue",
    "FileRecord",
    "Finding",
    "FindingSide",
    "Grade",
    "HeaderField",
    "IngestDocument",
    "IngestFileOutcome",
    "IngestRequest",
    "IngestResult",
    "LoginRequest",
    "LoginResponse",
    "LogicalDocument",
    "Meta",
    "Option",
    "PageInfo",
    "QueryItem",
    "Readiness",
    "CaseProgress",
    "StageKey",
    "StageProgress",
    "StageStatus",
    "ReviewDecisionRequest",
    "ReviewItem",
    "SessionUser",
    "Stage",
]
