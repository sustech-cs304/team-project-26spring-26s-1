from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


FileType = Literal["image", "pdf", "markdown", "text", "other"]


class FileDimensions(BaseModel):
	width: int | None = None
	height: int | None = None


class FileMetadata(BaseModel):
	dimensions: FileDimensions | None = None
	page_count: int | None = None
	markdown_length: int | None = None


class FileUploadResponse(BaseModel):
	file_id: str = Field(description="上传成功后返回的文件唯一标识符")
	mime_type: str | None = Field(description="文件的MIME类型")


class FileInfoResponse(BaseModel):
	file_id: str = Field(description="文件的唯一标识符")
	file_type: FileType = Field(description="文件类型，例如：图片、PDF、Markdown等")
	file_name: str = Field(description="文件的原始名称")