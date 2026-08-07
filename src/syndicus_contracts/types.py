"""Boundary-Typen, die beide Seiten der Naht sprechen.

* ``DetectedDeadline`` — von der Analyse erkannte Frist; die Adapter der Box
  (Actaport …) übertragen sie in den Fristen-Kalender der Kanzleisoftware.
* ``CommunicationBlob`` — in sich geschlossener Auftrag an den redakteur
  (Brief/Schriftsatz); entsteht zentral (followup_advice), wird auf der Box
  angezeigt/editiert und geht für Drafts zurück an den Core.
"""

import datetime

from pydantic import BaseModel


class DetectedDeadline(BaseModel):
    """A statutory deadline identified by the analysis."""

    type: str
    date: datetime.date
    pre_deadline: datetime.date | None = None
    basis: str


class CommunicationBlob(BaseModel):
    """Pre-filled input for the communication agent.

    Contains everything the agent needs — no additional state lookup required.
    """

    recipient_name: str
    recipient_email: str = ""  # may be empty — attorney fills in
    summary: str
    area_of_law: str
    case_reference: str = ""
    assigned_attorney: str = ""
    purpose: str  # Why this communication is needed
    rationale: str  # Why the LLM suggests this
    recipient_category: str = "sonstiges"  # mandant | gegner | rsv | gericht | behoerde | sonstiges
    # A3 (docs/aktionen.md § 7.3): Anreicherung für bessere Drafts + späteres
    # Spezial-Agenten-Routing — durchgereicht aus der NextStepGroup.
    action_type: str = ""
    key_points: list[str] = []  # was inhaltlich ins Schreiben muss
    desired_outcome: str = ""  # was das Schreiben erreichen soll
    deadline_date: str = ""  # TT.MM.JJJJ des Fristbezugs, falls fristgebunden
    # A4: gerichtliches Aktenzeichen (≠ Kanzlei-Az) — Pflichtangabe für
    # Schreiben/Schriftsätze ans Gericht.
    gerichts_az: str = ""
    # A7.1: Dokument-Assignments der zugehörigen Handlung — deterministisch
    # per Code aus der NextStepGroup übernommen (nie vom LOW-LLM erfunden).
    # Der Schriftsatz-Agent lädt exakt diese Volltexte (Freigabe-Gate-Filter
    # bleibt Pflicht); das Dateinamen-Matching ist nur noch Fallback.
    dokumente: list[str] = []
