from __future__ import annotations

from pydantic import BaseModel, Field


class DownloadedLocalSkillResponse(BaseModel):
    cloud_skill_id: int
    name: str
    description: str
    markdown_path: str


class DownloadedLocalSkillDetailResponse(BaseModel):
    cloud_skill_id: int
    name: str
    description: str
    markdown_path: str
    markdown_content: str


class RegisterCaptchaRequest(BaseModel):
    email: str = Field(..., description="Education email address")


class RegisterRequest(BaseModel):
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Education email address")
    password: str = Field(..., description="Password")
    verificationCode: str = Field(..., description="Verification code")


class LoginRequest(BaseModel):
    email: str = Field(..., description="Education email address")
    password: str = Field(..., description="Password")


class MessageResponse(BaseModel):
    message: str
