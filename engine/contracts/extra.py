"""What the case's documents print that no field and no table claimed (Story 6.4), as the assistant reads it
(Story 6.5). Not shown on any screen."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AdditionalInformation(BaseModel):
    document_id: str
    document: str
    """The document's type name and file."""
    document_type: str
    page: int
    kind: Literal["pair", "table"]
    label: str
    """The printed label, or the table's description."""
    value: str
    """The printed value(s), or the table's rows as "label: values" separated by semicolons."""
