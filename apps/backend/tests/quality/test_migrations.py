from sqlalchemy import Column, Integer, MetaData, Table

from quality.migrations import verify_migrations
from tappy.models import metadata


def test_current_migrations_apply_roll_back_and_match_models(test_server_url: str) -> None:
    assert verify_migrations(test_server_url, metadata) == []


def test_models_without_migration_are_reported(test_server_url: str) -> None:
    drifted = MetaData()
    Table("unmigrated_model", drifted, Column("id", Integer, primary_key=True))

    problems = verify_migrations(test_server_url, drifted)

    assert len(problems) == 1
    assert "unmigrated_model" in problems[0]
