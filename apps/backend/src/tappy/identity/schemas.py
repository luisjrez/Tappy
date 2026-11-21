from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tappy.identity.models import IdentityStatus, Role


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_at: datetime


class IdentityResponse(BaseModel):
    reference: str
    email: str
    role: Role
    status: IdentityStatus
