import sys

import uvicorn

from tappy.main import create_app
from tappy.platform.config import ConfigurationError, load_settings

try:
    settings = load_settings()
except ConfigurationError as error:
    sys.exit(str(error))

uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
