from __future__ import annotations

from pydantic import BaseModel, Field

class RagImportEmbeddingsResponse(BaseModel):
    file_name: str = Field(description="导入的 embeddings JSON 文件名")
    items_count: int = Field(description="JSON array 条目数量")
    embedded_added: int = Field(description="本次新增入库数量")
    embedded_overwritten: int = Field(description="本次覆盖删除旧 chunk 数量")
    embedded_failed: int = Field(description="本次 restore 失败数量")


class RagCloudSyncStatusResponse(BaseModel):
    status: str
    stage: str
    progress: int
    message: str
    knowledge_base_id: str
    version: str | None = None
    downloaded_files: list[str] = Field(default_factory=list)
    embedded_added: int = 0
    embedded_overwritten: int = 0
    embedded_failed: int = 0
    error: str | None = None
