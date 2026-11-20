from logging.config import fileConfig

from alembic import context
from sqlalchemy import MetaData, create_engine
from sqlalchemy.pool import NullPool

from tappy.platform.config import load_settings
from tappy.platform.persistence import Base


def database_url() -> str:
    configured = context.config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    return load_settings().database_url.get_secret_value()


def target_metadata() -> MetaData:
    configured = context.config.attributes.get("target_metadata", Base.metadata)
    if not isinstance(configured, MetaData):
        raise TypeError("target_metadata must be SQLAlchemy MetaData")
    return configured


def run_migrations() -> None:
    engine = create_engine(database_url(), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata())
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.config.config_file_name:
    fileConfig(context.config.config_file_name, disable_existing_loggers=False)
run_migrations()
