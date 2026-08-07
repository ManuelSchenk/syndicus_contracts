"""Ingest-Push der Box — die Schreibseite der Naht (repo-split-plan.md § 1.2/D8).

Die Einlese-Hälfte (retrieve → ocr → anonymize) läuft auf der Kanzlei-Box
(``syndicus_client``); ihre Ergebnisse — KS-Falldaten, anonymisierte
Dokumenttexte, die PII-freie Legende — erreichen den Core ausschließlich über
``PUT /cases/{id}/ingest`` mit diesem Payload. Konstruktionsbedingt
anonymisiert: die Box anonymisiert VOR dem Push, Klartext hat in keinem Feld
etwas verloren.

Update-Semantik: partiell — ``None`` heißt „Feld nicht anfassen", nur
mitgeschickte (nicht-``None``) Felder werden gesetzt. ``documents`` ersetzt
den Dokumentbestand ATOMISCH (Vollstand des letzten Box-Syncs, kein Delta);
die dokument-genauen Prüf-Freigaben überleben dabei für review-äquivalente
Texte (``CaseRepository.replace_documents``).
"""

import datetime
from typing import Any, Literal

from pydantic import BaseModel

__all__ = [
    "CaseIngestPayload",
    "IngestDocument",
    "IngestRunFinish",
    "IngestRunStart",
    "IngestStatusEvent",
    "StagePosteingangBody",
]


class IngestDocument(BaseModel):
    """Ein Dokument des Box-Syncs — Spiegel der ``CaseDocumentDB``-Felder,
    die die Box liefert (Texte bereits anonymisiert, inkl. ``filename``:
    Dateinamen sind ein PII-Kanal)."""

    document_id: str  # Adapter-/lokale Dokument-Id (stabiler Matching-Schlüssel)
    actaport_ordner_id: int = 0
    filename: str
    mime_type: str = ""
    size: int = 0
    description: str = ""
    doc_type: str = ""
    folder_path: str = ""
    extracted_text: str = ""
    ocr_method: str = ""
    origin: str = "kanzleisoftware"  # "kanzleisoftware" | "posteingang" | "upload" | "falldaten"
    synced_to_adapter: bool = True
    adapter_created_at: str = ""
    adapter_updated_at: str = ""
    # Expliziter Prüf-Stempel der Box (D8: die Box führt die Prüf-UX, der
    # Stempel liegt zentral). ``None`` = kein expliziter Stempel — dann
    # entscheidet die Review-Äquivalenz zum Bestand (``replace_documents``).
    review_confirmed_at: datetime.datetime | None = None
    # A5/V4-Wissensschicht — mitgeliefert, wenn die Box sie kennt (sonst
    # bleibt der zentrale Bestand für review-äquivalente Texte erhalten).
    summary: str = ""
    summary_source_hash: str = ""
    summary_meta: dict[str, Any] | None = None
    chunk_summaries: dict[str, Any] | None = None
    # Große Uploads (grosse-uploads.md § 5 U2): Segment-Herkunft eines
    # Riesen-PDF-Teils. Entsteht nur auf der Box — der Core übernimmt die
    # Werte unverändert.
    source_file_hash: str = ""
    page_start: int = 0
    page_end: int = 0
    page_count: int = 0


class CaseIngestPayload(BaseModel):
    """Body von ``PUT /cases/{case_id}/ingest`` — der Voll-/Teilstand eines
    Box-Syncs. Alle Felder optional; ``None`` = unverändert lassen."""

    case_data: dict[str, Any] | None = None
    notes_data: list[Any] | None = None
    deadlines_data: list[Any] | None = None
    tasks_data: list[Any] | None = None
    follow_ups_data: list[Any] | None = None
    # PII-freie Besetzungsliste aus der letzten ``/anonymize``-Response der
    # Box — ``analyse_case`` rendert sie als Legenden-Block in den Prompt.
    anonymization_legend: dict[str, Any] | None = None
    # Vollstand der Dokumente (kein Delta): ``None`` = Bestand nicht anfassen,
    # ``[]`` = alle Dokumente entfernen.
    documents: list[IngestDocument] | None = None
    status: str | None = None


class IngestStatusEvent(BaseModel):
    """Body von ``POST /cases/{case_id}/events`` — eine Einlese-SSE-Perle.

    Die Box hat kein Redis: ihre Fortschritts-Perlen (retrieve/ocr/anonymize)
    erreichen den Fortschritts-Stream über diesen Push. Der Core published sie
    exakt wie ein Worker-Event (``StatusEvent``-Form auf dem Tenant-Kanal,
    Timestamp stempelt der Core) und hängt sie — wenn ein Lauf aktiv ist —
    ans durable Run-Log (SSE-Replay). ``action``/``detail_data`` sind wie
    jedes SSE-Event anonymisiert (die Box anonymisiert VOR dem Push).
    """

    agent: str
    action: str
    status: str = "processing"  # processing | completed | error | skipped | cancelled
    detail_data: dict[str, Any] | None = None


class IngestRunStart(BaseModel):
    """Body von ``POST /cases/{case_id}/ingest-runs`` — ein Box-Sync als
    durable Run.

    ``trigger`` wählt die Frontend-Darstellung (RUN_TRIGGERS des Core:
    ``manual_refresh`` | ``scheduled`` | ``inbox``); unbekannte Werte lehnt
    der Core mit 400 ab.
    """

    trigger: str = "manual_refresh"


class IngestRunFinish(BaseModel):
    """Body von ``POST /cases/{case_id}/ingest-runs/{run_id}/finish``.

    Die Box ist der „Worker" ihres Ingest-Laufs — sie MUSS ihn terminal
    schließen (Pendant zum ``finally`` in ``tracked_run``); den Crash-Fall
    fängt der zentrale Reconciler über den Heartbeat ab.
    """

    status: Literal["completed", "completed_with_errors", "cancelled"]
    error: str | None = None


class StagePosteingangBody(BaseModel):
    """Body von ``POST /cases/{case_id}/documents/stage-posteingang``.

    ``body`` ist der ANONYMISIERTE Mailtext — die Box anonymisiert die
    Posteingang-Mail VOR dem Push, der Core sieht nur Platzhalter.
    ``dedupe_key`` (Hash des ROHEN Mailinhalts, Box-seitig gebildet) macht
    die document_id deterministisch: eine erneut zugestellte, inhaltsgleiche
    Mail landet nicht doppelt in der Akte.
    """

    body: str
    filename: str = "Posteingang_Mandanten-Mail.txt"
    dedupe_key: str | None = None
