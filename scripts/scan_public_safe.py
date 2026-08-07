#!/usr/bin/env python3
"""Wächter für ein ÖFFENTLICHES Repo: findet, was hier nie landen darf.

Dieses Repo ist öffentlich, weil sein Inhalt per Definition das ist, was ohnehin
über die Leitung geht: Schemata der HTTP-Naht plus zwei Verhaltensmodule. Alles
andere ist ein Unfall — und ein Unfall in einem öffentlichen Repo ist auch nach
dem Löschen noch in Forks, Caches und Suchindizes.

Der Scanner prüft **musterbasiert**, nicht namensbasiert. Das ist Absicht:

    Eine Denylist mit Mandanten-/Kanzlei-Namen DARF NICHT in dieses Repo.
    Sie wäre selbst die Preisgabe, die sie verhindern soll.

Namensprüfungen gehören auf die private Seite — ``--denylist <datei>`` nimmt eine
Datei mit je einem Begriff pro Zeile entgegen (z. B. aus dem privaten
Tenant-Register) und wird lokal bzw. in der privaten CI verwendet, bevor ein
Contract-Stand hierher synchronisiert wird. Ohne die Option prüft der Scanner
nur die Muster — genau das läuft in der öffentlichen CI.

Aufruf:
    uv run --no-project python scripts/scan_public_safe.py            # CI
    … python scripts/scan_public_safe.py --denylist /pfad/privat.txt  # vor dem Sync

Exit 0 = sauber, Exit 1 = Fund (mit Datei:Zeile und Grund).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Verzeichnisse, die nie gescannt werden (Build-Artefakte, VCS).
SKIP_DIRS = {".git", ".venv", "__pycache__", "dist", "build", ".ruff_cache", ".pytest_cache"}
# Nur Textdateien prüfen; alles andere hat in diesem Repo ohnehin nichts zu suchen.
TEXT_SUFFIXES = {".py", ".toml", ".md", ".yml", ".yaml", ".txt", ".json", ".cfg", ".ini"}

# (Name, Regex, Begründung) — bewusst konservativ: lieber ein Fehlalarm, den man
# mit einer Zeile Kommentar erklärt, als ein stiller Durchrutscher.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"), "Anthropic-API-Key"),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "OpenAI-artiger API-Key"),
    ("github-token", re.compile(r"\b(ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
     "GitHub-Token"),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS-Access-Key"),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "privater Schlüssel"),
    ("uuid-secret", re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[=:]\s*['\"][^'\"\s]{8,}['\"]"),
     "belegtes Secret-Feld (Wert statt Feldname)"),
    ("tailnet-ip", re.compile(r"\b100\.(?:[6-9]\d|1[0-2]\d)\.\d{1,3}\.\d{1,3}\b"), "Tailnet-IP"),
    ("private-ip", re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
     "private IP-Adresse"),
    ("mac", re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b"), "MAC-Adresse"),
    ("intern-host", re.compile(r"(?i)\b[a-z0-9-]+\.syndicus\.work\b"), "interner Hostname"),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "E-Mail-Adresse"),
    ("aktenzeichen", re.compile(r"\b\d{3}/\d{2}\b"), "Aktennummer-artiger Wert"),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,}\b"), "IBAN"),
]

# Zeilen mit diesem Marker sind geprüft und bewusst erlaubt (mit Begründung!).
ALLOW_MARKER = "public-safe:allow"


def iter_files() -> list[Path]:
    out: list[Path] = []
    for path in sorted(REPO.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return out


def scan(denylist: list[str]) -> list[str]:
    findings: list[str] = []
    lowered = [t.lower() for t in denylist if t.strip()]
    for path in iter_files():
        rel = path.relative_to(REPO)
        if rel.as_posix() == "scripts/scan_public_safe.py":
            continue  # die Musterdefinitionen selbst
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            findings.append(f"{rel}: keine UTF-8-Textdatei — in diesem Repo unerwartet")
            continue
        for n, line in enumerate(lines, 1):
            if ALLOW_MARKER in line:
                continue
            for name, rx, why in PATTERNS:
                if rx.search(line):
                    findings.append(f"{rel}:{n}: [{name}] {why} — {line.strip()[:100]}")
            for term in lowered:
                if term in line.lower():
                    findings.append(f"{rel}:{n}: [denylist] privater Begriff gefunden")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--denylist", type=Path, default=None,
        help="Datei mit privaten Begriffen (ein Begriff je Zeile). NIE in dieses Repo legen.",
    )
    args = ap.parse_args()

    terms: list[str] = []
    if args.denylist:
        if not args.denylist.is_file():
            print(f"FEHLER: Denylist {args.denylist} nicht gefunden", file=sys.stderr)
            return 2
        if args.denylist.resolve().is_relative_to(REPO):
            print("FEHLER: Die Denylist liegt IM öffentlichen Repo — genau das darf sie nie.",
                  file=sys.stderr)
            return 2
        terms = args.denylist.read_text(encoding="utf-8").splitlines()

    findings = scan(terms)
    if findings:
        print(f"public-safe-Scan: {len(findings)} Fund(e) — dieses Repo ist ÖFFENTLICH:\n")
        for f in findings:
            print(f"  {f}")
        print(f"\nEcht? Entfernen. Fehlalarm? Zeile mit '{ALLOW_MARKER}' + Begründung markieren.")
        return 1
    print(f"public-safe-Scan: sauber ({len(iter_files())} Dateien"
          + (f", {len(terms)} Denylist-Begriffe)" if terms else ", ohne Denylist)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
