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
from .case import CaseCreate, CaseDeleteRequest, CaseDetail, CaseSummary, HeaderField
from .common import Evidence, Grade, Stage
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
    "ReviewDecisionRequest",
    "ReviewItem",
    "SessionUser",
    "Stage",
]
