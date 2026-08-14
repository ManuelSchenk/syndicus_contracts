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
    # Lauf-Zugehörigkeit (1.9.0, todo Nr. 57): getrackte Perlen tragen den
    # Lauf, zu dem sie gehören — der Browser ordnet damit jede Perle ihrem
    # Lauf zu, statt sich auf die Ankunftsreihenfolge zu verlassen (vorher
    # zeigte ``buildStepInfo`` je Agent das LETZTE Event, egal aus welchem
    # Lauf, und der sessionStorage-Puffer kannte keine Lauf-Grenze).
    # ``None`` bei untracked One-Shot-Events (Aktions-Buttons, Lauf-lose
    # Publisher) — die haben keinen Lauf.
    run_id: str | None = None
    # Durable ``case_run_events.id`` — NUR auf Replay-Events gesetzt (der
    # Live-Publish läuft bewusst VOR dem best-effort-Append, die id existiert
    # dort noch nicht). Der Client dedupliziert Replay-vs-Live darüber; das
    # Feld stand seit jeher auf der Leitung und fehlte nur im Modell.
    event_id: int | None = None
