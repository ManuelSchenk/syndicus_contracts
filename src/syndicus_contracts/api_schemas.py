"""Request-/Response-Schemas der Core-API (Box ↔ Core).

Vollständige Read-Models des Fall-Korpus — ausschließlich anonymisierte
Inhalte. Box-only-Schemas (Posteingang-Mails, Mandanten-Stammdaten/ClientRead)
leben bewusst NICHT hier: sie sind kein Teil der Naht, sondern
Kanzlei-lokales Vokabular des ``syndicus_client``-BFF. Die Mandanten-Karte
(``client``) reichert das BFF-Gate in seine Antwort an — die zentrale DB
kennt keine Klartext-Stammdaten (Konzept-TODO D18).
"""

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel


class AuditEntryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agent: str
    action: str
    confidence: float
    timestamp: datetime.datetime
    detail_data: dict[str, Any] | None = None


class AuditAppend(BaseModel):
    """Box-seitiger Audit-Eintrag (``POST /cases/{case_id}/audit``).

    Vorgänge, die seit dem Split auf der Box laufen (Nachanonymisieren,
    Fehlteil-Verwerfen, Mappen-Freigabe), haben dort kein Audit-Log — die
    revisionsfeste Spur des Falls liegt zentral. Diese Naht trägt sie nach.

    Invarianten: ``action``/``detail_data`` sind wie jedes zentrale Feld
    ANONYMISIERT (die Box schreibt nie Klartext-PII hinein — auch keine
    markierten Aliasse, nur Platzhalter-Token und Zählwerte). Den Zeitstempel
    setzt der Core (wie bei ``IngestStatusEvent``) — eine schiefe Box-Uhr darf
    die Reihenfolge der Spur nicht verdrehen. ``agent`` darf KEIN
    Pipeline-Agent sein: deren Einträge räumt der nächste Lauf weg.
    """

    agent: str
    action: str
    confidence: float = 1.0
    detail_data: dict[str, Any] | None = None


class AnonymizationConfirm(BaseModel):
    """Fall-Level-Freigabe der Anonymisierung
    (``POST /cases/{case_id}/anonymization-confirm``, Box → Core).

    Die dokument-genauen Stempel schreibt die Box über ``confirm-review``;
    DAS hier ist die Aussage „diese Akte wurde am X von Y zur Übermittlung
    freigegeben" — ein Rechtsfakt (rechtliches.md). Er gehört in die
    zentrale, revisionsfeste Spur und nicht in eine SQLite-Datei der Box:
    im Streitfall zählt, was unveränderlich protokolliert ist.

    Den Zeitstempel setzt der Core; idempotent — eine bereits freigegebene
    Akte behält ihren ersten Stempel (und bekommt keinen zweiten Audit-Eintrag).
    """

    confirmed_by: str | None = None  # Anzeigename des Freigebenden (Box-UX)


class ReanonymizationReport(BaseModel):
    """Meldung der Box nach einer Nachanonymisierung
    (``POST /cases/{case_id}/reanonymized``).

    Der Anwalt hat einen vom Anonymizer ÜBERSEHENEN Klartext-Treffer
    nachgetragen oder geschwärzt. Die Box korrigiert, was sie besitzt
    (Dokumenttexte, Titel) — alles zentral daraus ABGELEITETE trägt den alten
    Klartext weiter: Dokument-Kurzfassungen und Wissensschicht, ``analysis``,
    ``advice``, ``legal_research``, Entwürfe, Neuigkeiten-Texte.

    Der Core kann sie nicht reparieren: die Suche bräuchte den Klartext-Alias,
    und genau der darf hier nie ankommen. Deshalb **verwirft** er sie — was
    aus dem alten Text entstand, ist ungültig. Die Felder sind reine
    Protokoll-Angaben (keine PII: Zählwert + Flag).
    """

    documents_changed: int = 0
    blackout: bool = False


class AttorneyWorkload(BaseModel):
    name: str
    open_cases: int
    specializations: list[str]


class CockpitStats(BaseModel):
    total_open_cases: int
    new_today: int
    critical_deadlines: int
    avg_processing_seconds: float | None
    attorney_workload: list[AttorneyWorkload]


# --- Briefing schemas ---


class CaseCreate(BaseModel):
    """Fall-Anlage durch die Box (``POST /cases``) — find-or-create per
    Aktennummer. Die optionalen Felder setzt die Box bei Bedarf (Upload-Mappe:
    ``source="upload"`` + anonymisierter ``title``; KS-Akte:
    ``adapter_aktennummer``); ``None`` = Feld nicht anfassen."""

    aktennummer: str
    source: str | None = None  # "manual" | "upload" | "inbox"
    # Anwalts-Titel einer Import-Mappe — von der Box VOR dem Push anonymisiert.
    title: str | None = None
    # KS-seitige Aktennummer, sobald die Akte in der Kanzleisoftware existiert.
    adapter_aktennummer: str | None = None


class CaseNoteCreate(BaseModel):
    # FG2 (Inline-Freigabe, Box-seitig): mit ``anon_token`` sind title/
    # description die vom Anwalt GEPRÜFTEN anonymisierten Texte aus der
    # Vorschau — der Server verwendet sie exakt (keine zweite Anonymisierung).
    title: str
    description: str = ""
    note_type: str = "NOTIZ"
    anon_token: str | None = None


class CaseNoteUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    note_type: str | None = None
    anon_token: str | None = None


class AttorneyNoteCreate(BaseModel):
    """Anwalts-Notiz anlegen (``POST /cases/{id}/notes``, Box → Core-Naht).

    ``content`` erreicht den Core BEREITS ANONYMISIERT — Anonymisierung und
    FG2-Vorschau/Inline-Freigabe leistet das Box-Gate. ``anon_token`` ist
    Box-Vokabular (``inline_approval``, prozess-lokales Secret der Box): der
    Core kann und darf ihn NICHT prüfen und ignoriert das Feld; es bleibt im
    Schema, damit das Gate den Frontend-Body unverändert durchreichen kann.
    """

    content: str
    anon_token: str | None = None


class AttorneyNoteUpdate(BaseModel):
    """Anwalts-Notiz ändern (``PATCH /cases/{id}/notes/{note_id}``).

    Gleiche Naht-Invariante wie ``AttorneyNoteCreate``: ``content`` kommt
    anonymisiert, ``anon_token`` wird vom Core ignoriert (Box-Sache).
    """

    content: str
    anon_token: str | None = None


class AttorneyNoteRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    content: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CaseDocumentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    document_id: str
    # ``filename`` bleibt der ROH gespeicherte (ggf. anonymisierte) Name — er ist
    # der Matching-Schlüssel für Dokument-Auswahl (Custom-Action/Kommunikation)
    # und darf NIE deanonymisiert an den Client, sonst bricht der Join.
    filename: str
    # ``filename_display`` ist der für die ANZEIGE deanonymisierte Name (unter dem
    # Deanonymisierungs-Toggle; leer ⇒ Frontend fällt auf ``filename`` zurück).
    # Deanonymisierung passiert auf der Box — der Core liefert das Feld leer.
    filename_display: str = ""
    mime_type: str
    size: int
    doc_type: str
    ocr_method: str
    origin: str = "kanzleisoftware"  # "kanzleisoftware" | "posteingang" | "upload"
    synced_to_adapter: bool = True   # False = local Posteingang/Upload doc, not yet in the KS
    actaport_url: str = ""  # Web-UI deep link — empty when the ordnerId is unknown
    # Actaport-ordnerId (roh, kein PII) — die Box baut daraus den Dokument-
    # Deep-Link (``services/actaport_links``); 0 = unbekannt (GAP 3, Slice 2a).
    actaport_ordner_id: int = 0
    # Dokument-genaues Prüf-Gate (rechtliches.md): None = noch nicht geprüft
    # (nur bei lokalen upload/posteingang-Dokumenten relevant). Wird beim
    # Nachanonymisieren/Rename zurückgesetzt.
    review_confirmed_at: datetime.datetime | None = None
    # Große Uploads (grosse-uploads.md § 5 U2): Seitenbereich eines logischen
    # Teil-Dokuments aus einem segmentierten Riesen-PDF (1-basiert inklusiv;
    # 0 = kein Segment-Dokument).
    page_start: int = 0
    page_end: int = 0
    page_count: int = 0
    created_at: datetime.datetime | None = None
    # KS-Metadaten as stored (Core-Nachtrag, Slice 2b): die Box braucht sie für
    # die Carry-Forward-Unverändert-Erkennung (``adapter_updated_at`` statt
    # size-Fallback) und für verlustfreie Echo-Pushes (``description``/
    # ``folder_path``); ``source_file_hash`` gruppiert Segment-Dokumente
    # (grosse-uploads.md § 5 U2) über den Roundtrip hinweg. Adapter-Timestamps
    # sind rohe Adapter-Strings, kein PII; "" = unbekannt.
    description: str = ""
    folder_path: str = ""
    source_file_hash: str = ""
    adapter_created_at: str = ""
    adapter_updated_at: str = ""


class CaseDocumentPatch(BaseModel):
    """Partielles Update EINER Dokument-Row
    (``PATCH /cases/{case_id}/documents/{row_id}``). ``None`` = nicht anfassen.

    Gegenstück zum Vollstand-Push: lädt die Box ein einzelnes lokales Dokument
    in die Kanzleisoftware, ändert sich genau diese Row (echte ``document_id``,
    ``synced_to_adapter``). Vor dieser Naht ging das nur als Echo-Push über
    ``PUT /ingest`` — der komplette Bestand samt Volltext je Dokument über die
    Leitung, nur damit ein Feld kippt.

    Bewusst OHNE ``extracted_text``: Textänderungen gehören in den
    Ingest-Push, wo die Review-Äquivalenz über Prüf-Freigabe, Summaries und
    Wissensschicht entscheidet. Diese Route ändert nur Identität/Metadaten —
    der Prüf-Stempel bleibt darum unberührt (und muss es: der Anwalt hat den
    unveränderten Text freigegeben).
    """

    document_id: str | None = None
    actaport_ordner_id: int | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    description: str | None = None
    doc_type: str | None = None
    folder_path: str | None = None
    synced_to_adapter: bool | None = None
    adapter_created_at: str | None = None
    adapter_updated_at: str | None = None
    source_file_hash: str | None = None


class CaseDisplay(BaseModel):
    """Minimal display fields the overview card renders.

    Kept separate from ``case_data`` / ``analysis`` so the list endpoint only
    touches ~4 short strings per case instead of the full JSON blobs. Der Core
    liefert sie anonymisiert; das Box-Gate deanonymisiert sie im Durchlauf.
    """

    area_of_law: str = ""
    summary: str = ""
    mandant: str = ""
    gegner: str = ""


class WiedervorlageState(BaseModel):
    """Wiedervorlage (Hinhaltefunktion) *scheduling* state for a case."""

    enabled: bool = False
    interval_weeks: int = 2
    next_run_at: datetime.datetime | None = None
    last_run_at: datetime.datetime | None = None


class CaseNewsItem(BaseModel):
    """One entry in the unified Neuigkeiten feed (``case_news``)."""

    id: uuid.UUID
    source: str  # "posteingang" | "kanzleisoftware"
    result: str  # "news" | "missing_docs" | "no_news" | "merge"
    headline: str
    new_documents: list[str] = []
    # Dokument-IDs hinter der Neuigkeit (``case_news.new_document_ids``):
    # Adapter-IDs (KS-Delta) bzw. lokale document_ids (Posteingang). Die Box
    # braucht sie für den News-Upload (Posteingang: verlinkte Mail-Dokumente
    # hochladen); ``new_documents`` bleibt die Anzeige-Liste (Dateinamen).
    new_document_ids: list[str] = []
    draft_blob_index: int | None = None
    note_text: str | None = None
    detail: dict[str, Any] | None = None
    created_at: datetime.datetime
    resolved_at: datetime.datetime | None = None
    uploaded_at: datetime.datetime | None = None


class CaseNewsCreate(BaseModel):
    """Body für ``POST /cases/{id}/news`` (Box → Core).

    Für Neuigkeiten, die NICHT aus der Analyse-Hälfte stammen: die
    Auto-Zuordnung des Posteingangs meldet die frisch angehängte Mail sofort,
    weil ``document_delta`` sie nicht melden kann — der Agent braucht eine
    vorherige Analyse, die ein eben erst aus der Kanzleisoftware gezogener Fall
    per Definition nicht hat (docs/client/mail-auto-zuordnung.md § 7).

    ``headline``/``note_text`` sind bereits anonymisiert — die Box anonymisiert
    vor dem Push, dieser Stack persistiert nie Klartext.
    """

    source: str  # NEWS_SOURCES: "posteingang" | "kanzleisoftware"
    result: str = "news"
    headline: str
    # Dokument-IDs der Neuigkeit — zugleich der Idempotenz-Schlüssel von
    # ``document_delta``: was hier referenziert ist, meldet der Agent später
    # nicht ein zweites Mal.
    new_document_ids: list[str] = []
    # Anzeigenamen (Dateinamen) für die UI; landen in ``detail.new_documents``,
    # wo ``CaseNewsItem.new_documents`` sie liest.
    new_documents: list[str] = []
    note_text: str | None = None


class CaseNewsMarkUploaded(BaseModel):
    """Body für ``POST /cases/{id}/news/{news_id}/mark-uploaded`` (Box → Core).

    Die Box führt den eigentlichen Adapter-Upload (Dokumente + Aktennotiz,
    deanonymisiert) selbst aus und meldet danach nur den Erfolg zentral zurück;
    ``note_uploaded_id`` = KS-ID der angelegten Aktennotiz, falls vorhanden.
    """

    note_uploaded_id: str | None = None


class RunState(BaseModel):
    """The current/latest durable pipeline run for a case (the authoritative
    run-state). The frontend derives "is a run active / which step / why is it
    waiting" from this over REST — SSE is only a nudge over the same record.
    """

    status: str  # queued|running|waiting|completed|completed_with_errors|cancelled
    trigger: str  # manual_refresh|scheduled|inbox
    current_step: str | None = None
    blocked_on: str | None = None  # ai_tools|llm|adapter (only while waiting)
    blocked_reason: str | None = None
    next_retry_at: datetime.datetime | None = None
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None


class CaseSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    aktennummer: str
    status: str
    document_count: int = 0
    case_data: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    display: CaseDisplay = CaseDisplay()
    urgency: int = 0
    assigned_attorney: str | None = None
    source: str = "manual"
    last_run_pipeline: str = "briefing"
    created_at: datetime.datetime
    updated_at: datetime.datetime
    last_read_at: datetime.datetime | None = None
    wiedervorlage: WiedervorlageState = WiedervorlageState()
    # Combined new-arrival signal (un-acknowledged inbox merges + Wiedervorlage
    # runs) — drives the Fälle-list "neu" dot.
    has_unseen_news: bool = False
    unseen_news_count: int = 0
    in_kanzleisoftware: bool = True  # False = provisional/local Akte (not in the KS yet)
    # Platzhalter wurden umbenannt (Rollen-Promotion/Merge im Anonymizer) —
    # die gespeicherte Analyse basiert auf alten Tokens. Badge im UI.
    reanalysis_recommended: bool = False
    # Mindestens ein lokales Dokument (upload/posteingang) ist noch nicht geprüft
    # (review_confirmed_at IS NULL) — treibt das „Freigabe erforderlich"-Badge.
    needs_document_review: bool = False


class CaseDetail(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    aktennummer: str
    status: str
    case_data: dict[str, Any] | None = None
    notes_data: list[Any] | None = None
    deadlines_data: list[Any] | None = None
    tasks_data: list[Any] | None = None
    follow_ups_data: list[Any] | None = None
    analysis: dict[str, Any] | None = None
    advice: dict[str, Any] | None = None
    legal_research: dict[str, Any] | None = None  # agentic-RAG funde (Wissen tab)
    documents: list[CaseDocumentRead] = []
    audit_log: list[AuditEntryRead] = []
    attorney_notes: list[AttorneyNoteRead] = []
    communication_drafts: list["CommunicationDraftRead"] = []
    case_actaport_url: str = ""
    summary: str = ""
    description: str = ""
    urgency: int = 0
    assigned_attorney: str | None = None
    source: str = "manual"
    last_run_pipeline: str = "briefing"
    news: list[CaseNewsItem] = []
    custom_actions: list[Any] | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    last_read_at: datetime.datetime | None = None
    wiedervorlage: WiedervorlageState = WiedervorlageState()
    run: RunState | None = None
    in_kanzleisoftware: bool = True  # False = provisional/local Akte (not in the KS yet)
    adapter_aktennummer: str | None = None  # the KS-side Aktennummer once created there
    # Platzhalter wurden umbenannt (Rollen-Promotion/Merge) — Analyse veraltet.
    reanalysis_recommended: bool = False
    # Mindestens ein lokales Dokument (upload/posteingang) noch ungeprüft.
    needs_document_review: bool = False
    # Anonymisierungs-Freigabe (source="upload", rechtliches.md):
    # None = Prüfung steht aus, der Fall ist aus der Übersicht ausgeblendet.
    anonymization_confirmed_at: datetime.datetime | None = None
    anonymization_confirmed_by: str | None = None


class CommunicationDraftRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    case_id: uuid.UUID
    blob_index: int
    recipient_name: str
    recipient_email: str
    subject: str
    body: str
    confidence: float
    status: str
    actaport_document_id: str | None = None
    uploaded_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CommunicationDraftUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    # Versandstempel des Box-seitigen KS-Uploads (DOCX + Briefkopf): der Upload
    # passiert in der Kanzlei, der Zustand gehört zum Fall. Ohne ihn gäbe es
    # weder Doppelversand-Schutz noch den „erledigt"-Zustand im UI — ein Reload
    # zeigte den versendeten Entwurf wieder als „draft".
    status: Literal["draft", "sent"] | None = None
    actaport_document_id: str | None = None
    uploaded_at: datetime.datetime | None = None
