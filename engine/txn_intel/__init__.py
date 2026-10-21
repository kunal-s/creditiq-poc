"""Bank-statement transaction intelligence (the deterministic pass).

Each statement transaction gets a category, the party it names and the rule that decided it, from
configuration (config/txn_classification.yaml). Whatever the rules cannot settle is marked for the
model pass. Nothing here reads a document or the database: it takes plain transactions and a
context, so the same input always gives the same labels.
"""

from .classify import classify
from .models import Context, Label, Txn

__all__ = ["Context", "Label", "Txn", "classify"]
