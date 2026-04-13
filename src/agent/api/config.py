from __future__ import annotations

from typing import Any

import pydantic
from fastapi import APIRouter, Body, status
from fastapi.responses import JSONResponse

from agent.config import get_config, patch_config, save_config

router = APIRouter(tags=["config"])


class ErrorMessageResponse(pydantic.BaseModel):
    message: str


def _build_validation_message(exc: pydantic.ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid config patch"
    first_error = errors[0]
    location = ".".join(str(item) for item in first_error.get("loc", ()))
    detail = first_error.get("msg", "Invalid value")
    if location:
        return f"{location}: {detail}"
    return str(detail)


@router.get(
    "/get_config",
    response_model=dict[str, Any],
    summary="获取配置接口",
)
async def api_get_config() -> dict[str, Any]:
    return get_config().model_dump()


@router.patch(
    "/patch_config",
    response_model=dict[str, Any],
    summary="修改配置接口",
    description="修改config",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorMessageResponse,
            "description": "请求参数错误",
        }
    },
)
async def api_patch_config(
    delta: dict[str, Any] = Body(
        ...,
        description="需要merge进入config的字典",
    ),
) -> dict[str, Any] | JSONResponse:
    try:
        updated = patch_config(delta)
    except pydantic.ValidationError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": _build_validation_message(exc)},
        )

    save_config(updated)
    return updated.model_dump()
