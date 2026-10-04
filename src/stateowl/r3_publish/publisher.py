from __future__ import annotations

from typing import Any, Mapping

from .types import PublicationProvider
from .publisher_state import PublisherState
from .publisher_history import PublisherHistory
from .publisher_ops import PublisherOps

class Publisher(PublisherOps, PublisherHistory, PublisherState):
    pass

def publish(raw: bytes, capabilities: Mapping[str, Any], provider: PublicationProvider) -> dict[str, Any]:
    return Publisher(provider, capabilities).run(raw)
