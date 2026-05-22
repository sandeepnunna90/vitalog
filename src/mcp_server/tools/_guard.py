"""Patient-ID contextvar — set per-request by BearerMiddleware in SSE mode.

get_patient_id() raises LookupError if called without BearerMiddleware having
first set the contextvar. This is the intended failure mode: tools must not
run without an authenticated patient context.
"""

from __future__ import annotations

import contextvars
import uuid

_patient_id_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("patient_id")


def get_patient_id() -> uuid.UUID:
    return _patient_id_var.get()


def set_patient_id(patient_id: uuid.UUID) -> contextvars.Token[uuid.UUID]:
    return _patient_id_var.set(patient_id)
