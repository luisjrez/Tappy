from tappy.identity.models import AccessSession, Identity
from tappy.platform.persistence import Base

__all__ = ["AccessSession", "Identity", "metadata"]

metadata = Base.metadata
