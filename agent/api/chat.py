"""Routes for icebreakers (recommended topics) and file upload."""

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from .models import ErrorResponse, IcebreakerResponse, IcebreakerTopic

router = APIRouter()


# ── GET /chat/icebreakers  –  recommended topics ────────────────────────────


@router.get(
    "/chat/icebreakers",
    summary="推荐话题接口",
    response_model=IcebreakerResponse,
    description="根据用户历史输入、剪切板、日程等信息推荐话题。",
)
async def get_icebreakers() -> IcebreakerResponse:
    # TODO: generate personalised icebreakers
    return IcebreakerResponse(topics=[])


# ── POST /  –  file upload ──────────────────────────────────────────────────


@router.post(
    "/",
    summary="文件上传",
    responses={200: {"description": "Upload result"}},
)
async def upload_file(
    file: UploadFile = File(...),
) -> dict:
    # TODO: persist the uploaded file and return metadata
    return {}
