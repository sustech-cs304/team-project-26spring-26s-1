from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from agent.rag.pipeline import persist_upload_to_raw, run_rag_pipeline_for_file


class RagUploadResponse(BaseModel):
    file_name: str = Field(description="上传的文件名")
    source_url: str | None = Field(default=None, description="文档来源 URL（可选）")
    stored_path: str = Field(description="raw 目录中的实际存储路径")
    cleaned_path: str = Field(description="cleaned 目录中的清洗后路径")
    chunk_path: str = Field(description="chunks 目录中的切分结果路径")
    chunks_count: int = Field(description="切分 chunk 数量")
    embedded_added: int = Field(description="本次新增入库数量")
    embedded_overwritten: int = Field(description="本次覆盖删除旧 chunk 数量")
    embedded_failed: int = Field(description="本次 embedding 失败数量")


router = APIRouter()


@router.post("/rag/upload", response_model=RagUploadResponse)
async def upload_rag_file(
    request: Request,
    file: UploadFile = File(...),
    source_url: str | None = Form(default=None),
) -> RagUploadResponse:
    try:
        raw_file = await persist_upload_to_raw(file, request.app.state.config)
        pipeline_result = await run_rag_pipeline_for_file(
            raw_file=raw_file,
            config=request.app.state.config,
            store_db=Path("agent_store.db"),
            source_url=source_url,
        )
        return RagUploadResponse(
            file_name=raw_file.name,
            source_url=source_url,
            stored_path=str(pipeline_result.stored_file),
            cleaned_path=str(pipeline_result.cleaned_file),
            chunk_path=str(pipeline_result.chunk_file),
            chunks_count=pipeline_result.chunks_count,
            embedded_added=pipeline_result.embedded_added,
            embedded_overwritten=pipeline_result.embedded_overwritten,
            embedded_failed=pipeline_result.embedded_failed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG upload pipeline failed: {exc}") from exc
