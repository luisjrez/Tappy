from typing import Annotated

from fastapi import Depends, Request

from tappy.platform.config import Settings


def get_settings(request: Request) -> Settings:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):
        raise TypeError("Application settings are not configured")
    return settings


SettingsDependency = Annotated[Settings, Depends(get_settings)]
