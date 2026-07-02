#!/usr/bin/env python3
"""Build an ICS feed of FIFA World Cup 2026 matches with pt-PT broadcasters.

Data source: football-data.org v4 (free tier). Set env FOOTBALL_DATA_TOKEN.
Broadcasters: Sport TV shows every game (default). Extra channels
(LiveModeTV, RTP, SIC, TVI) and YouTube links come from overrides.json.

Run:  FOOTBALL_DATA_TOKEN=xxx python build_calendar.py
Test: python build_calendar.py --selftest
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.football-data.org/v4/competitions/WC/matches"
OVERRIDES_FILE = "overrides.json"
OUT = "worldcup.ics"
MATCH_MINUTES = 120  # kickoff -> ~final whistle
DEFAULT_CHANNELS = ["Sport TV"]  # transmite todos os jogos

STAGE_PT = {
    "GROUP_STAGE": "Fase de Grupos",
    "LAST_16": "Oitavos de Final",
    "ROUND_OF_16": "Oitavos de Final",
    "QUARTER_FINALS": "Quartos de Final",
    "SEMI_FINALS": "Meias-Finais",
    "THIRD_PLACE": "Disputa do 3.o Lugar",
    "FINAL": "Final",
}


def fetch_matches():
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        sys.exit("Missing FOOTBALL_DATA_TOKEN env var (free key: football-data.org).")
    req = urllib.request.Request(API, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["matches"]


def load_overrides():
    # ponytail: JSON not YAML so no dep. Keyed by "HOME-AWAY" (as returned by API).
    if not os.path.exists(OVERRIDES_FILE):
        return {}
    with open(OVERRIDES_FILE, encoding="utf-8") as f:
        return json.load(f)


def match_key(m):
    return f"{m['homeTeam']['name']}-{m['awayTeam']['name']}"


def stage_line(m):
    stage = STAGE_PT.get(m.get("stage", ""), m.get("stage", "").title())
    grp = m.get("group")
    if grp:  # "GROUP_K" -> "Grupo K"
        stage += ", Grupo " + grp.split("_")[-1]
    return stage


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def fold(line):
    # RFC5545: lines <=75 octets; naive char fold is fine for our content.
    out = []
    while len(line.encode("utf-8")) > 74:
        cut = 74
        while len(line[:cut].encode("utf-8")) > 74:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return out


def build_ics(matches, overrides, now):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//worldcup-2026-calendar//PT//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Mundial FIFA 2026 (pt-PT)",
        "X-WR-TIMEZONE:Europe/Lisbon",
    ]
    for m in matches:
        home = m["homeTeam"]["name"] or "A definir"
        away = m["awayTeam"]["name"] or "A definir"
        start = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        end = start + timedelta(minutes=MATCH_MINUTES)

        ov = overrides.get(match_key(m), {})
        channels = DEFAULT_CHANNELS + ov.get("channels", [])
        desc = stage_line(m) + "\nTransmissao: " + ", ".join(channels)
        if ov.get("youtube"):
            desc += "\nYouTube: " + ov["youtube"]

        summary = f"⚽ {home} x {away} (Mundial 2026)"
        lines += [
            "BEGIN:VEVENT",
            "UID:" + ics_escape(f"wc2026-{m['id']}@worldcup-2026-calendar"),
            "DTSTAMP:" + fmt(now),
            "DTSTART:" + fmt(start),
            "DTEND:" + fmt(end),
            "SUMMARY:" + ics_escape(summary),
            "DESCRIPTION:" + ics_escape(desc),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    folded = []
    for ln in lines:
        folded += fold(ln)
    return "\r\n".join(folded) + "\r\n"


def selftest():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
    matches = [{
        "id": 1, "utcDate": "2026-06-20T19:00:00Z", "stage": "GROUP_STAGE",
        "group": "GROUP_K",
        "homeTeam": {"name": "Portugal"}, "awayTeam": {"name": "Brasil"},
    }]
    overrides = {"Portugal-Brasil": {"channels": ["SIC", "LiveModeTV"],
                                     "youtube": "https://youtube.com/@livemodetv"}}
    ics = build_ics(matches, overrides, now)
    unfolded = ics.replace("\r\n ", "")  # reverse RFC5545 line folding
    assert "SUMMARY:⚽ Portugal x Brasil (Mundial 2026)" in unfolded
    assert "Transmissao: Sport TV\\, SIC\\, LiveModeTV" in unfolded
    assert "Grupo K" in unfolded
    assert "DTSTART:20260620T190000Z" in unfolded
    assert "DTEND:20260620T210000Z" in unfolded
    assert "YouTube: https://youtube.com/@livemodetv" in unfolded
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    now = datetime.now(timezone.utc)
    matches = fetch_matches()
    ics = build_ics(matches, load_overrides(), now)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"Wrote {OUT}: {len(matches)} matches")


if __name__ == "__main__":
    main()
