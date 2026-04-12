from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from agent.rag.embedding_and_restore import load_embedding_array, restore_from_embedding_array
from agent.rag.paths import get_rag_paths
from agent.rag.pipeline import persist_upload_to_raw, run_rag_pipeline_for_file


class RagUploadResponse(BaseModel):
    file_name: str = Field(description="上传的文件名")
    source_url: str | None = Field(default=None, description="文档来源 URL（可选）")
    stored_path: str = Field(description="raw 目录中的实际存储路径")
    cleaned_path: str = Field(description="cleaned 目录中的清洗后路径")
    chunk_path: str = Field(description="chunks 目录中的切分结果路径")
    embeddings_json_path: str = Field(description="embedding 结果 JSON 文件路径")
    chunks_count: int = Field(description="切分 chunk 数量")
    embedded_added: int = Field(description="本次新增入库数量")
    embedded_overwritten: int = Field(description="本次覆盖删除旧 chunk 数量")
    embedded_failed: int = Field(description="本次 embedding 失败数量")


class RagImportEmbeddingsResponse(BaseModel):
    file_name: str = Field(description="导入的 embeddings JSON 文件名")
    items_count: int = Field(description="JSON array 条目数量")
    embedded_added: int = Field(description="本次新增入库数量")
    embedded_overwritten: int = Field(description="本次覆盖删除旧 chunk 数量")
    embedded_failed: int = Field(description="本次 restore 失败数量")


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
            embeddings_json_path=str(pipeline_result.embeddings_json_file),
            chunks_count=pipeline_result.chunks_count,
            embedded_added=pipeline_result.embedded_added,
            embedded_overwritten=pipeline_result.embedded_overwritten,
            embedded_failed=pipeline_result.embedded_failed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"RAG upload pipeline failed: {exc}") from exc


@router.post("/rag/import-embeddings", response_model=RagImportEmbeddingsResponse)
async def import_embeddings(
    request: Request,
    embeddings_file: UploadFile = File(...),
    overwrite_sources: str | None = Form(default=None),
) -> RagImportEmbeddingsResponse:
    try:
        rag_paths = get_rag_paths(request.app.state.config)
        file_name = Path(embeddings_file.filename or "embeddings.json").name
        target_path = rag_paths.embeddings_dir / file_name
        content = await embeddings_file.read()
        target_path.write_bytes(content)

        embedding_items = load_embedding_array(target_path)
        overwrite_set = None
        if overwrite_sources:
            parsed = {x.strip() for x in overwrite_sources.split(",") if x.strip()}
            overwrite_set = parsed or None

        stats = await restore_from_embedding_array(
            config=request.app.state.config,
            embedding_items=embedding_items,
            store_db=Path("agent_store.db"),
            overwrite_sources=overwrite_set,
        )

        return RagImportEmbeddingsResponse(
            file_name=file_name,
            items_count=len(embedding_items),
            embedded_added=stats.added,
            embedded_overwritten=stats.overwritten,
            embedded_failed=stats.failed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import embeddings failed: {exc}") from exc
