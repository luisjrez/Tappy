from enum import StrEnum

from psycopg.errors import UniqueViolation
from sqlalchemy import Enum
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def enum_column(enum: type[StrEnum], name: str, length: int = 16) -> Enum:
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


def is_unique_violation(error: IntegrityError, constraint: str) -> bool:
    return isinstance(error.orig, UniqueViolation) and error.orig.diag.constraint_name == constraint
