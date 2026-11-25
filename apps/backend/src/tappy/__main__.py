import sys

import uvicorn

from tappy.main import create_app
from tappy.platform.config import ConfigurationError, load_settings
from tappy.platform.diagnostics import configure_logging

try:
    settings = load_settings()
except ConfigurationError as error:
    sys.exit(str(error))

configure_logging(settings)
uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
