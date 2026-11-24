import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tappy.identity.provisioning import IdentitySummary
from tappy.merchants.errors import (
    InvalidReceiverError,
    IssuanceBlockedError,
    MerchantNotFoundError,
    ReceiverAccountTakenError,
    ReceiverNotConfiguredError,
)
from tappy.merchants.models import (
    BENEFICIARY_NAME_MAX_LENGTH,
    PROVIDER_ACCOUNT_CONSTRAINT,
    PROVIDER_ACCOUNT_ID_MAX_LENGTH,
    Merchant,
    ReceivingAccount,
)
from tappy.merchants.service import accessible_merchant, collapsed_text

CLABE = re.compile(r"\d{18}")
CLABE_WEIGHTS = (3, 7, 1)
PROVIDER_ACCOUNT_ID = re.compile(rf"[A-Za-z0-9_-]{{1,{PROVIDER_ACCOUNT_ID_MAX_LENGTH}}}")
MASKED_DIGITS = 14
DISABLED_REASON = "The receiving account is disabled; new charges are blocked until it is enabled"
MISSING_REASON = "No receiving account is configured; new charges are blocked"


@dataclass(frozen=True)
class ReceiverSettings:
    provider_account_id: str
    beneficiary_name: str
    clabe: str
    enabled: bool


@dataclass(frozen=True)
class ReceiverView:
    beneficiary_name: str
    masked_account: str
    provider_account_id: str
    enabled: bool
    blocked_reason: str | None

    @property
    def can_issue(self) -> bool:
        return self.blocked_reason is None


def has_valid_check_digit(clabe: str) -> bool:
    total = sum(
        int(digit) * CLABE_WEIGHTS[index % len(CLABE_WEIGHTS)] % 10
        for index, digit in enumerate(clabe[:-1])
    )
    return (10 - total % 10) % 10 == int(clabe[-1])


def validated(settings: ReceiverSettings) -> ReceiverSettings:
    beneficiary_name = collapsed_text(
        settings.beneficiary_name,
        BENEFICIARY_NAME_MAX_LENGTH,
        InvalidReceiverError(
            f"Beneficiary name must have between 1 and {BENEFICIARY_NAME_MAX_LENGTH} characters"
        ),
    )
    if not PROVIDER_ACCOUNT_ID.fullmatch(settings.provider_account_id):
        raise InvalidReceiverError(
            "Provider account ID must use letters, digits, '-' or '_' "
            f"(up to {PROVIDER_ACCOUNT_ID_MAX_LENGTH})"
        )
    if not CLABE.fullmatch(settings.clabe) or not has_valid_check_digit(settings.clabe):
        raise InvalidReceiverError("CLABE must have 18 digits and a valid check digit")
    return ReceiverSettings(
        settings.provider_account_id, beneficiary_name, settings.clabe, settings.enabled
    )


def issuance_block(receiver: ReceivingAccount | None) -> str | None:
    if receiver is None:
        return MISSING_REASON
    return None if receiver.enabled else DISABLED_REASON


def masked_account(account_last4: str) -> str:
    return "*" * MASKED_DIGITS + account_last4


def describe_receiver(receiver: ReceivingAccount) -> ReceiverView:
    return ReceiverView(
        beneficiary_name=receiver.beneficiary_name,
        masked_account=masked_account(receiver.account_last4),
        provider_account_id=receiver.provider_account_id,
        enabled=receiver.enabled,
        blocked_reason=issuance_block(receiver),
    )


def receiver_of(db: Session, merchant_id: uuid.UUID) -> ReceivingAccount | None:
    return db.scalar(select(ReceivingAccount).where(ReceivingAccount.merchant_id == merchant_id))


def configure_receiver(
    db: Session, merchant_id: uuid.UUID, settings: ReceiverSettings, now: datetime
) -> ReceiverView:
    clean = validated(settings)
    merchant = db.scalar(
        select(Merchant).where(Merchant.id == merchant_id).with_for_update(key_share=True)
    )
    if merchant is None:
        raise MerchantNotFoundError
    receiver = receiver_of(db, merchant.id) or ReceivingAccount(
        merchant_id=merchant.id, created_at=now
    )
    try:
        with db.begin_nested():
            receiver.provider_account_id = clean.provider_account_id
            receiver.beneficiary_name = clean.beneficiary_name
            receiver.account_last4 = clean.clabe[-4:]
            receiver.enabled = clean.enabled
            receiver.updated_at = now
            db.add(receiver)
    except IntegrityError as error:
        if (
            isinstance(error.orig, UniqueViolation)
            and error.orig.diag.constraint_name == PROVIDER_ACCOUNT_CONSTRAINT
        ):
            raise ReceiverAccountTakenError from None
        raise
    return describe_receiver(receiver)


def accessible_receiver(
    db: Session, actor: IdentitySummary, merchant_id: uuid.UUID
) -> ReceivingAccount | None:
    return receiver_of(db, accessible_merchant(db, actor, merchant_id).id)


def read_receiver(db: Session, actor: IdentitySummary, merchant_id: uuid.UUID) -> ReceiverView:
    receiver = accessible_receiver(db, actor, merchant_id)
    if receiver is None:
        raise ReceiverNotConfiguredError
    return describe_receiver(receiver)


def issuable(receiver: ReceivingAccount | None) -> ReceivingAccount:
    reason = issuance_block(receiver)
    if reason is not None or receiver is None:
        raise IssuanceBlockedError(reason)
    return receiver


def issuing_receiver(db: Session, actor: IdentitySummary, merchant_id: uuid.UUID) -> ReceiverView:
    return describe_receiver(issuable(accessible_receiver(db, actor, merchant_id)))


def held_issuing_receiver(db: Session, merchant_id: uuid.UUID) -> ReceivingAccount:
    return issuable(
        db.scalar(
            select(ReceivingAccount)
            .where(ReceivingAccount.merchant_id == merchant_id)
            .with_for_update(read=True)
        )
    )


def list_receivers(db: Session) -> dict[uuid.UUID, ReceiverView]:
    return {
        receiver.merchant_id: describe_receiver(receiver)
        for receiver in db.scalars(select(ReceivingAccount))
    }
