# syndicus_contracts

Das **Naht-Vokabular** zwischen der Kanzlei-Box (`syndicus_client`) und dem
zentralen Analyse-Stack (`syndicus_agents`): die Boundary-Typen der HTTP-Naht,
die Form der Fortschritts-Events, und zwei Verhaltensmodule, die beide Seiten
identisch ausführen müssen.

Der **Server besitzt den Contract** — gepflegt wird er in `syndicus_agents`,
dieses Repo ist die veröffentlichte, versionierte Fassung, gegen die eine Box
baut.

## Inhalt

| Modul | Was |
|---|---|
| `api_schemas.py` | Request-/Response-Modelle der Core-API (`CaseDetail`, `CaseSummary`, `CaseDocumentRead`, Notizen, Kommunikations-Drafts …) |
| `ingest.py` | `IngestDocument` / `CaseIngestPayload` — der Vollstand-Push der Box |
| `sse.py` | `StatusEvent` — die Form des Fortschritts-Streams |
| `types.py` | `DetectedDeadline`, `CommunicationBlob` — geteilte Werttypen |
| `dependency.py` | `DependencyUnavailable`, Blocked-Codes, Backoff-Leiter mit Jitter — **Verhalten**, kein Schema |
| `gpu_jobs.py` | submit→poll-Client der GPU-Job-Queue inkl. Fehler-Mapping — **Verhalten** |
| `__init__.py` | `CONTRACT_VERSION` + die Header-Namen der Naht |

Warum ein Paket und kein Endpunkt: Schemata braucht Python zur **Importzeit**,
nicht zur Laufzeit — und Verhalten (Backoff-Kurve, Fehler-Mapping) kann kein
Endpunkt ausliefern. Die Laufzeit-Seite existiert zusätzlich: der Core meldet
`contract_version`, die Box sendet `X-Syndicus-Contract-Version`. Der Endpunkt
**erkennt** Drift, das Paket **definiert** die Form.

## Versionierung

`MAJOR` der Paketversion **ist** `CONTRACT_VERSION`. Am Pin liest man ohne
Code-Öffnen ab, welche Draht-Version eine Box spricht.

| Bump | wann | Wirkung |
|---|---|---|
| MAJOR | brechende Naht (zusammen mit `CONTRACT_VERSION`) | Core akzeptiert N und N‑1 — ein MAJOR-Sprung braucht alle Boxen in einer Welle |
| MINOR | additiv (neues optionales Feld/Modell) | alte Boxen laufen weiter |
| PATCH | Verhalten/Doku ohne Formänderung | — |

Konsumenten pinnen einen **Tag**, nie einen Branch:

```toml
[tool.uv.sources]
syndicus-contracts = { git = "https://github.com/<org>/syndicus_contracts.git",
                       tag = "v1.0.0" }
```

Ein Branch bewegt sich; damit änderte sich die Naht unter einer Installation
beim nächsten Rebuild still. Ein Tag macht den Stand reproduzierbar und den
Wechsel zu einem sichtbaren Commit.

## Dieses Repo ist ÖFFENTLICH

Das ist Absicht: der Inhalt ist per Definition das, was ohnehin über die Leitung
geht. Damit ein Konsument ohne Zugangsdaten bauen kann, darf hier **nichts**
liegen, was das nicht ist.

**Nie hier hinein:** API-Keys/Tokens/Schlüssel · interne Hostnamen, IP- oder
MAC-Adressen · E-Mail-Adressen · Mandanten-, Kanzlei- oder Personennamen ·
Aktennummern · echte Beispieldaten jeder Art. Feldnamen (`anon_token`,
`X-Api-Key`) sind Vokabular und in Ordnung — belegte Werte nie.

`scripts/scan_public_safe.py` prüft das musterbasiert; die CI führt es über den
Arbeitsbaum **und über jeden je committeten Stand** aus. Ein Fehlalarm wird mit
`public-safe:allow` plus Begründung in derselben Zeile entschärft — nie durch
Aufweichen des Musters.

**Eine Denylist mit Kunden-/Kanzlei-Namen gehört NICHT in dieses Repo** — sie
wäre selbst die Preisgabe, die sie verhindern soll. Der Scanner lehnt eine
Denylist ab, die innerhalb des Repos liegt.

## Der Weg hierher

Gepflegt wird in `syndicus_agents/packages/contracts`. Vor jeder
Veröffentlichung:

```sh
# 1) namensbasiert prüfen — mit der PRIVATEN Denylist, die hier nie liegt
python scripts/scan_public_safe.py --denylist ~/privat/denylist.txt
# 2) Paket baut + Version passt (macht die CI ebenfalls)
python -m build --wheel
# 3) committen, taggen, pushen
git tag v1.0.0 && git push origin main --tags
```

Ein Secret, das einmal hier lag, ist auch nach dem Löschen in Forks, Caches und
Suchindizes — deshalb prüft die CI die Historie, nicht nur den Kopf. Bei einem
echten Fund gilt: Key rotieren, dann erst aufräumen.

## Lizenz

Bewusst noch keine Lizenzdatei — ohne Lizenz gilt „alle Rechte vorbehalten",
was für einen reinen Konsum-Contract die konservative Voreinstellung ist. Soll
das Paket von Dritten nutzbar sein, hier bewusst eine Lizenz ergänzen.
