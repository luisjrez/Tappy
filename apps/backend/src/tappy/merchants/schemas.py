import uuid

from pydantic import BaseModel, ConfigDict, Field

from tappy.merchants.models import MERCHANT_NAME_MAX_LENGTH


class MerchantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MERCHANT_NAME_MAX_LENGTH)


class MembershipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_reference: uuid.UUID


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reference: str
    email: str


class MerchantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    members: list[MemberResponse]
