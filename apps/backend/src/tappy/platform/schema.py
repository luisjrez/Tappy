from functools import cache

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

SCRIPT_LOCATION = "tappy:migrations"


def alembic_config(database_url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", SCRIPT_LOCATION)
    if database_url is not None:
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


@cache
def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def is_schema_current(connection: Connection) -> bool:
    return MigrationContext.configure(connection).get_current_revision() == head_revision()
