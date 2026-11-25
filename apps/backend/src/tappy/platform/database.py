from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from tappy.platform.config import Settings
from tappy.platform.schema import is_schema_current

CONNECT_TIMEOUT_SECONDS = 2


class Database:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.session_factory = sessionmaker(engine)

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        )
        return cls(engine)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with self.session_factory() as session, session.begin():
            yield session

    def is_ready(self) -> bool:
        try:
            with self.engine.connect() as connection:
                return is_schema_current(connection)
        except SQLAlchemyError:
            return False

    def dispose(self) -> None:
        self.engine.dispose()
