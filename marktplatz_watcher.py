#!/usr/bin/env python3
"""Meldet neue Inserate auf https://www.rudern.de/marktplatz per Push (ntfy).
Läuft per GitHub Actions. Das ntfy-Topic kommt aus dem Secret NTFY_TOPIC."""
import json
import os
import pathlib
import sys

import requests
from bs4 import BeautifulSoup

URL = "https://www.rudern.de/marktplatz"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATE_FILE = pathlib.Path(__file__).with_name("seen.json")

# Nur diese Rubrik melden: "Biete", "Suche" oder None für beide
KATEGORIE = None

# Optional: nur melden, wenn der Titel eines dieser Wörter enthält
# (Kleinschreibung). Leer lassen = alles melden.
STICHWORTE = []  # z. B. ["gig", "vierer", "4x", "4+", "achter"]


def hole_inserate():
    r = requests.get(URL, timeout=30, headers={"User-Agent": "marktplatz-watcher/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    inserate = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/service/marktplatz/" not in href or href.rstrip("/").endswith("/neu"):
            continue
        link = requests.compat.urljoin(URL, href)
        kontext = a.parent.get_text(" ", strip=True) if a.parent else ""
        kat = "Biete" if "Biete" in kontext else "Suche" if "Suche" in kontext else "?"
        inserate[link] = {"titel": a.get_text(strip=True), "kategorie": kat}
    return inserate


def sende_push(titel, link):
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=titel.encode("utf-8"),
        headers={"Title": "Neues Inserat Marktplatz", "Click": link, "Tags": "rowboat"},
        timeout=30,
    ).raise_for_status()


def passt(inserat):
    if KATEGORIE and inserat["kategorie"] != KATEGORIE:
        return False
    if STICHWORTE:
        return any(w in inserat["titel"].lower() for w in STICHWORTE)
    return True


def main():
    if not NTFY_TOPIC:
        sys.exit("NTFY_TOPIC ist nicht gesetzt (GitHub Secret anlegen).")

    aktuell = hole_inserate()
    if not aktuell:
        sys.exit("Keine Inserate gefunden - hat sich die Seitenstruktur geändert?")

    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(sorted(aktuell), indent=0))
        print(f"Erster Lauf: {len(aktuell)} Inserate gemerkt.")
        return

    gesehen = set(json.loads(STATE_FILE.read_text()))
    for link, inserat in aktuell.items():
        if link not in gesehen and passt(inserat):
            sende_push(inserat["titel"], link)
            print("Gemeldet:", inserat["titel"])

    STATE_FILE.write_text(json.dumps(sorted(gesehen | set(aktuell)), indent=0))


if __name__ == "__main__":
    main()
