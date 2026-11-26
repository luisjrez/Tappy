from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tappy.identity.models import IdentityStatus, Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


class IdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference: str
    email: str
    role: Role
    status: IdentityStatus


class OperatorCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)
    initial_password: str = Field(min_length=1, max_length=1024)


class PasswordResetRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)


class AcceptedResponse(BaseModel):
    detail: str
