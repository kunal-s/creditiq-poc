"""Field kinds added with the document-fields adoption: TAN and UDIN formats, and yes/no facts read
from the wording that states them."""

import pytest

from ingestion.stages.extract import identifiers
from ingestion.stages.extract.normalise import normalise


@pytest.mark.parametrize("kind, value, ok", [
    ("tan", "CMBS12345F", True),
    ("tan", "CMBS1234F", False),
    ("udin", "25214536BMKXYZ1234", True),
    ("udin", "2521453BMKXYZ1234", False),
])
def test_tan_and_udin_formats(kind, value, ok):
    assert identifiers.check(kind, value)[0] is ok


def test_a_stated_fact_is_true_and_an_absent_one_stays_missing():
    assert normalise("Material Uncertainty Related to Going Concern", "present") == (True, None)
    assert normalise("   ", "present") == (None, "empty")
