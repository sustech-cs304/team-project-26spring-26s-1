from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from agent.rag.restore import load_embedding_array, restore_from_embedding_array


class RagImportEmbeddingsResponse(BaseModel):
    file_name: str = Field(description="导入的 embeddings JSON 文件名")
    items_count: int = Field(description="JSON array 条目数量")
    embedded_added: int = Field(description="本次新增入库数量")
    embedded_overwritten: int = Field(description="本次覆盖删除旧 chunk 数量")
    embedded_failed: int = Field(description="本次 restore 失败数量")


router = APIRouter()


@router.post("/rag/import-embeddings", response_model=RagImportEmbeddingsResponse)
async def import_embeddings(
    request: Request,
    embeddings_file: UploadFile = File(...),
    overwrite_sources: str | None = Form(default=None),
) -> RagImportEmbeddingsResponse:
    try:
        rag_root = Path(request.app.state.config.file.rag_path)
        embeddings_dir = rag_root / "embeddings"
        embeddings_dir.mkdir(parents=True, exist_ok=True)
        file_name = Path(embeddings_file.filename or "embeddings.json").name
        target_path = embeddings_dir / file_name
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

        # Keep the API in "restore-only" mode; uploaded JSON is temporary.
        try:
            target_path.unlink(missing_ok=True)
        except Exception:
            pass

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
