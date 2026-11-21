from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from tappy.platform.config import Settings
from tappy.platform.database import Database


def get_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise TypeError("Application settings are not configured")
    return settings


def get_database(request: Request) -> Database:
    database = request.app.state.database
    if not isinstance(database, Database):
        raise TypeError("Application database is not configured")
    return database


SettingsDependency = Annotated[Settings, Depends(get_settings)]
DatabaseDependency = Annotated[Database, Depends(get_database)]


def get_session(database: DatabaseDependency) -> Iterator[Session]:
    with database.transaction() as session:
        yield session


SessionDependency = Annotated[Session, Depends(get_session)]
