import logging
from typing import List
from pydantic import BaseModel, field_validator, Field
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from config import EMBEDDING_DIMENSIONS
from services.skeleton_command_service import skeleton_command_service
from marrow_common.skeleton_schema import SCHEMA_VERSION

logger = logging.getLogger("marrow.transport.vectorize")

router = APIRouter()

class ChunkPayload(BaseModel):
    """HTTP transport model for a single skeleton chunk. Fields mirror common/skeleton_schema.py:SkeletonChunk."""
    chunk_type: str = Field(validation_alias="type")
    chunk_name: str = Field(validation_alias="name")
    skeleton_text: str
    vector: List[float]
    start_line: int = Field(validation_alias="line_start")
    end_line: int = Field(validation_alias="line_end")

    @field_validator("vector")
    @classmethod
    def validate_vector_dim(cls, v: List[float]) -> List[float]:
        if len(v) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"vector must have {EMBEDDING_DIMENSIONS} dimensions, got {len(v)}"
            )
        return v


class VectorizeRequest(BaseModel):
    schema_version: str
    project_name: str
    path: str
    file_summary: str
    chunks: List[ChunkPayload]

    @field_validator("chunks")
    @classmethod
    def validate_non_empty(cls, v: List[ChunkPayload]) -> List[ChunkPayload]:
        if not v:
            raise ValueError("chunks list must not be empty")
        return v

@router.post("/api/vectorize")
async def vectorize_endpoint(request: Request, payload: VectorizeRequest):
    """Receives pre-vectorized code skeleton chunks from marrow_worker."""
    if payload.schema_version != SCHEMA_VERSION:
        return JSONResponse(
            {
                "error": "schema_version_mismatch",
                "expected": SCHEMA_VERSION,
                "received": payload.schema_version,
            },
            status_code=422,
        )
    try:
        request_id = request.scope.get("request_id", "unknown")
        count = await skeleton_command_service.ingest(
            payload, 
            _perf_extra={"request_id": request_id, "file": payload.path}
        )
        return {"status": "ok", "chunks_stored": count}
    except Exception as e:
        logger.error("[vectorize_endpoint] %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


class DeleteRequest(BaseModel):
    project_name: str
    path: str


@router.delete("/api/vectorize")
async def delete_vectorize_endpoint(request: Request, payload: DeleteRequest):
    """Removes all skeleton chunks for a deleted/moved source file."""
    try:
        request_id = request.scope.get("request_id", "unknown")
        count = await skeleton_command_service.delete(
            payload.path, 
            payload.project_name,
            _perf_extra={"request_id": request_id, "file": payload.path, "op": "delete"}
        )
        return {"status": "ok", "chunks_deleted": count}
    except Exception as e:
        logger.error("[delete_vectorize_endpoint] %s", e)
        return JSONResponse({"error": str(e)}, status_code=400)
