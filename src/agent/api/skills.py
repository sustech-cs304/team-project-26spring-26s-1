from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status

from agent.api.skills_models import (
    DownloadedLocalSkillDetailResponse,
    DownloadedLocalSkillResponse,
    LoginRequest,
    MessageResponse,
    RegisterCaptchaRequest,
    RegisterRequest,
)
from agent.services.skills_auth_state import SkillsAuthState
from agent.services.skills_hub_client import SkillsHubClient
from agent.services.skills_local_store import SkillsLocalStore

router = APIRouter(tags=["skills"])


def _skills_client(request: Request) -> SkillsHubClient:
    return request.app.state.skills_hub_client


def _skills_auth_state(request: Request) -> SkillsAuthState:
    return request.app.state.skills_auth_state


def _skills_local_store(request: Request) -> SkillsLocalStore:
    return request.app.state.skills_local_store


async def _require_cloud_token(request: Request) -> str:
    auth_state = _skills_auth_state(request)
    token = await auth_state.get_access_token()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in.")
    return token


async def _request_with_token(
    request: Request,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    token = await _require_cloud_token(request)
    client = _skills_client(request)
    auth_state = _skills_auth_state(request)
    try:
        return await client.request_json(
            method,
            path,
            token=token,
            params=params,
            json_body=json_body,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            await auth_state.clear()
        raise


@router.post("/auth/register/captcha")
async def send_register_captcha(
    body: RegisterCaptchaRequest,
    request: Request,
) -> Any:
    return await _skills_client(request).request_json(
        "POST",
        "/auth/register/captcha",
        json_body=body.model_dump(),
    )


@router.post("/auth/register")
async def register_user(
    body: RegisterRequest,
    request: Request,
) -> Any:
    return await _skills_client(request).request_json(
        "POST",
        "/auth/register",
        json_body=body.model_dump(),
    )


@router.post("/auth/login")
async def login_user(body: LoginRequest, request: Request) -> Any:
    payload = await _skills_client(request).request_json(
        "POST",
        "/auth/login",
        json_body=body.model_dump(),
    )

    if not isinstance(payload, dict) or "access_token" not in payload:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream login response missing access_token.",
        )

    user = {
        "email": payload.get("email"),
        "username": payload.get("username"),
        "role": payload.get("role"),
    }
    await _skills_auth_state(request).set_token(str(payload["access_token"]), user=user)
    return payload


@router.get("/auth/me")
async def get_current_user(request: Request) -> Any:
    payload = await _request_with_token(request, "GET", "/auth/me")
    if isinstance(payload, dict):
        await _skills_auth_state(request).set_user(payload)
    return payload


@router.get("/skills")
async def list_skills(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tag_id: int | None = Query(None),
    search: str | None = Query(None),
) -> Any:
    params: dict[str, Any] = {
        "page": page,
        "page_size": page_size,
    }
    if tag_id is not None:
        params["tag_id"] = tag_id
    if search is not None and search.strip():
        params["search"] = search.strip()

    return await _skills_client(request).request_json("GET", "/api/skills", params=params)


@router.get("/skills/me")
async def list_my_skills(request: Request) -> Any:
    return await _request_with_token(request, "GET", "/api/skills/me")


@router.get("/skills/downloaded", response_model=list[DownloadedLocalSkillResponse])
async def list_downloaded_skills(request: Request) -> list[DownloadedLocalSkillResponse]:
    skills = await _skills_local_store(request).list_downloaded_skills()
    return [
        DownloadedLocalSkillResponse(
            cloud_skill_id=skill.cloud_skill_id,
            name=skill.name,
            description=skill.description,
            markdown_path=skill.markdown_path,
        )
        for skill in skills
    ]


@router.get("/skills/downloaded/{skill_id}", response_model=DownloadedLocalSkillDetailResponse)
async def get_downloaded_skill_detail(
    request: Request,
    skill_id: int,
) -> DownloadedLocalSkillDetailResponse:
    skill = await _skills_local_store(request).get_downloaded_skill_by_id(skill_id)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Downloaded skill not found.")

    markdown_path = Path(skill.markdown_path)
    if not markdown_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Downloaded skill file not found.",
        )

    try:
        markdown_content = markdown_path.read_text(encoding="utf-8")
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read downloaded skill file: {error}",
        ) from error

    return DownloadedLocalSkillDetailResponse(
        cloud_skill_id=skill.cloud_skill_id,
        name=skill.name,
        description=skill.description,
        markdown_path=skill.markdown_path,
        markdown_content=markdown_content,
    )


@router.get("/skills/{skill_id}")
async def get_skill_detail(request: Request, skill_id: int) -> Any:
    return await _skills_client(request).request_json("GET", f"/api/skills/{skill_id}")


@router.get("/skills/{skill_id}/download", response_model=MessageResponse)
async def download_skill(request: Request, skill_id: int) -> MessageResponse:
    skill_detail = await _skills_client(request).request_json("GET", f"/api/skills/{skill_id}")
    markdown_content = await _skills_client(request).request_text(
        "GET",
        f"/api/skills/{skill_id}/download",
    )

    if not isinstance(skill_detail, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upstream skill detail format is invalid.",
        )

    await _skills_local_store(request).save_downloaded_skill(
        cloud_skill_id=skill_id,
        name=str(skill_detail.get("name") or f"skill_{skill_id}"),
        description=str(skill_detail.get("description") or ""),
        markdown_content=markdown_content,
    )

    return MessageResponse(message="下载成功")


@router.get("/tags")
async def list_tags(request: Request) -> Any:
    return await _skills_client(request).request_json("GET", "/api/tags")


@router.post("/skills")
async def upload_skill(
    request: Request,
    file: UploadFile = File(...),
    tag_ids: str | None = Form(None),
) -> Any:
    token = await _require_cloud_token(request)
    payload = await file.read()
    content_type = file.content_type or "text/markdown"
    filename = file.filename or "skill.md"

    fields: dict[str, str] = {}
    if tag_ids is not None and tag_ids.strip():
        fields["tag_ids"] = tag_ids.strip()

    return await _skills_client(request).post_multipart(
        "/api/skills",
        token=token,
        fields=fields,
        files={
            "file": (filename, payload, content_type),
        },
    )


@router.delete("/skill/{skill_id}/delete")
async def delete_submission_skill(request: Request, skill_id: int) -> Any:
    token = await _require_cloud_token(request)
    client = _skills_client(request)
    cloud_config = client.get_config_snapshot()
    raw_path = client.get_delete_submission_path(cloud_config).strip()
    if not raw_path:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Cloud delete-submission endpoint is not configured. "
                "See doc/skills_delete_cloud_spec.md for upstream API requirements."
            ),
        )

    cloud_path = raw_path.format(skill_id=skill_id)
    return await client.request_json("DELETE", cloud_path, config=cloud_config, token=token)


@router.post("/skill/{skill_id}/uninstall", response_model=MessageResponse)
async def uninstall_skill(request: Request, skill_id: int) -> MessageResponse:
    removed = await _skills_local_store(request).uninstall_local_skill(skill_id)
    if removed:
        return MessageResponse(message="卸载成功")
    return MessageResponse(message="技能未安装")
