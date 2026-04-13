from __future__ import annotations

from pydantic import BaseModel, Field

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
