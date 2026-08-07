"""Die SSE-Event-Form des Fortschritts-Streams (Quelle: Core, Relay: Box).

Der Worker published diese Form auf ``{tenant}:case:{id}:status`` (Redis
Pub/Sub); die Core-API-SSE-Quelle streamt sie an die Box, das Box-Relay
deanonymisiert die Statusstrings im Durchlauf (D11) und reicht sie an den
Browser weiter — die JSON-Form bleibt auf dem ganzen Weg identisch.
"""

from typing import Any

from pydantic import BaseModel


class StatusEvent(BaseModel):
    """One agent status event as published on the pipeline channel."""

    agent: str
    action: str
    status: str  # processing | completed | completed_with_errors | error | skipped | cancelled
    timestamp: str  # ISO 8601
    detail_data: dict[str, Any] | None = None
