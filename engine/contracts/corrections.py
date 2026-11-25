"""A person's corrections on the Files tab (Story 7.2): a page given its own type, a document's period set."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageTypeRequest(BaseModel):
    """Read one page of a document as another type, in a document of its own."""

    type_id: str
    reason: str = Field(min_length=1, max_length=2000)


class PeriodRequest(BaseModel):
    """The period a document covers, as a person reads it from the document: an ISO date range."""

    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    reason: str = Field(min_length=1, max_length=2000)


class CorrectionQueued(BaseModel):
    job_id: str | None = None
