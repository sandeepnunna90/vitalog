"""Pydantic schema for a Mode A structured citation."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


class Citation(BaseModel):
    model_config = ConfigDict(strict=True)

    value: float
    unit: str
    collection_date: date
    source_record_id: uuid.UUID
