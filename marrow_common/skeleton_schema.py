"""
Skeleton transport contract — SCHEMA_VERSION 1.0

Single source of truth for field names and types exchanged between
marrow_worker (emitter) and marrow_server (consumer) over HTTP.
This is the TRANSPORT layer contract only.
Do NOT confuse with storage/models.py:SkeletonChunkRecord (LanceDB schema).
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

SCHEMA_VERSION = "1.0"

class ChunkType(str, Enum):
    """Canonical chunk type values. New types must be added here first."""
    file      = "file"
    imports   = "imports"
    namespace = "namespace"
    klass     = "class"
    method    = "method"
    property_ = "property"


class SkeletonChunk(BaseModel):
    """
    Transport-layer model for a single indexed code unit.
    Both Worker (sender) and Server (receiver) validate against this model.

    Field names match the LanceDB schema in storage/models.py:SkeletonChunkRecord.
    This is intentional — the transport contract mirrors the storage contract.
    If a field is renamed in storage, update this model first, then storage.
    """
    path:          str
    project:       str
    chunk_type:    str          # ChunkType value; str to allow forward-compatible extension
    chunk_name:    str
    start_line:    int
    end_line:      int
    skeleton_text: str
    vector:        List[float]
    is_test:       bool = False
    file_summary:  Optional[str] = None
