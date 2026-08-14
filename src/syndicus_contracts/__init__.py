"""Syndicus HTTP-Contract — Boundary-Vokabular zwischen Box und Core.

Der Server (``syndicus_agents``-Core-API) besitzt den Contract
(syndicus_agents/docs/architecture.md § 1); ``syndicus_client`` konsumiert
dieses Paket.
Kompatibilitätsregel: der Core akzeptiert ``CONTRACT_VERSION`` und N-1.
"""

CONTRACT_VERSION = "1"

# Header, über den die Box ihre Contract-Version mitsendet (Phase-2-Härtung:
# der Core lehnt unbekannte/zu alte Versionen mit 409 ab).
CONTRACT_VERSION_HEADER = "X-Syndicus-Contract-Version"

# Header für den Tenant-API-Key (der Tenant wird serverseitig aus dem Key
# abgeleitet — er ist NIE ein Feld, das der Client selbst behauptet).
API_KEY_HEADER = "X-Api-Key"

# Betriebsmodus-Deklaration der Box (ab v1.3.0, additiv): "anonym" oder
# "klartext". Die Box sendet den Header auf JEDEM Core-Call; der Core
# validiert ihn gegen die konfigurierte Tenant-Eigenschaft und lehnt einen
# Mismatch mit 409 ab, BEVOR irgendetwas geschrieben wird — Config-Drift
# zwischen Box und Core kann so nie still Rohtext in einen Anonym-Korpus
# (oder Platzhalter in einen Klartext-Korpus) schieben. Fehlender Header
# gilt im Registry-Betrieb als Deklaration "anonym" (alte Boxen laufen bei
# Anonym-Tenants weiter; ein Klartext-Tenant verlangt die explizite
# Deklaration).
OPERATING_MODE_HEADER = "X-Syndicus-Operating-Mode"
