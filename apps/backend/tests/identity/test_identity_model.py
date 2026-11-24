import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tappy.models import metadata

INSERT = text(
    "INSERT INTO identities (id, email, password_hash, role, status) "
    "VALUES (gen_random_uuid(), :email, 'hash', 'operator', 'active')"
)


def test_model_schema_enforces_case_insensitive_unique_email(empty_database_url: str) -> None:
    engine = create_engine(empty_database_url)
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(INSERT, {"email": "first@tappy.example"})
            connection.execute(INSERT, {"email": "second@tappy.example"})
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(INSERT, {"email": "FIRST@tappy.example"})
    finally:
        engine.dispose()
