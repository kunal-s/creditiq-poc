"""Types shared across the contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Case stages (FRD §7): Intake, then the six processing stages of §5 in order.
Stage = Literal[
    "Intake", "Documents", "Extraction", "Completeness", "CrossVerification", "Policy", "Outputs", "Completed"
]

# Page quality grade (FRD F-07.2).
Grade = Literal["A", "B", "C", "U"]


class Evidence(BaseModel):
    """Where a value came from (FRD §7, F-16). Page is mandatory (C7); the
    region is optional, as normalised page coordinates (0 to 1, top-left
    origin): [x0, y0, x1, y1]."""

    document_id: str
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] | None = None
