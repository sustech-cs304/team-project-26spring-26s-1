from __future__ import annotations

from pydantic import BaseModel, Field


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
