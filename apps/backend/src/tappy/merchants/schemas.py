import uuid

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from tappy.merchants.models import (
    BENEFICIARY_NAME_MAX_LENGTH,
    MERCHANT_NAME_MAX_LENGTH,
    PROVIDER_ACCOUNT_ID_MAX_LENGTH,
)


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


class ReceiverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_account_id: str = Field(max_length=PROVIDER_ACCOUNT_ID_MAX_LENGTH)
    beneficiary_name: str = Field(max_length=BENEFICIARY_NAME_MAX_LENGTH)
    clabe: SecretStr
    enabled: bool


class IssuanceCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReceiverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    beneficiary_name: str
    masked_account: str
    enabled: bool
    can_issue: bool
    blocked_reason: str | None
