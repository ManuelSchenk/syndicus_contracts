"""Syndicus HTTP-Contract — Boundary-Vokabular zwischen Box und Core.

Der Server (``syndicus_agents``-Core-API) besitzt den Contract
(repo-split-plan.md § 4.1); ``syndicus_client`` konsumiert dieses Paket.
Kompatibilitätsregel: der Core akzeptiert ``CONTRACT_VERSION`` und N-1.
"""

CONTRACT_VERSION = "1"

# Header, über den die Box ihre Contract-Version mitsendet (Phase-2-Härtung:
# der Core lehnt unbekannte/zu alte Versionen mit 409 ab).
CONTRACT_VERSION_HEADER = "X-Syndicus-Contract-Version"

# Header für den Tenant-API-Key (der Tenant wird serverseitig aus dem Key
# abgeleitet — er ist NIE ein Feld, das der Client selbst behauptet).
API_KEY_HEADER = "X-Api-Key"
