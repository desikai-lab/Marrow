from fastapi import APIRouter, Request

router = APIRouter(tags=["meta"])


@router.get("/openapi.json", include_in_schema=False)
async def openapi_spec(request: Request, project: str):
    return request.app.openapi()
