#!/usr/bin/env python3
"""Build an ICS feed of FIFA World Cup 2026 matches, in pt-PT, with pt-PT
broadcasters.

Data source: football-data.org v4 (free tier). Set env FOOTBALL_DATA_TOKEN.
Broadcasters: Sport TV shows every game (default). Extra channels
(LiveModeTV, RTP, SIC, TVI), YouTube links and per-game location come from
overrides.json.

Event format (pt-PT):
  SUMMARY:     ⚽ Spain x Austria (Dezasseis avos)
  LOCATION:    Los Angeles, Estados Unidos da América
  DESCRIPTION: Mundial FIFA 2026 — Dezasseis avos de final (jogo 84). Transmissão: Sport TV.

Run:   FOOTBALL_DATA_TOKEN=xxx python build_calendar.py
Test:  python build_calendar.py --selftest
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.football-data.org/v4/competitions/WC/matches"
OVERRIDES_FILE = "overrides.json"
SCHEDULE_FILE = "schedule.json"
OUT = "worldcup.ics"
MATCH_MINUTES = 120  # kickoff -> ~final whistle
DEFAULT_CHANNELS = ["Sport TV"]  # transmite todos os jogos

# (curto para titulo, longo para descricao). Cobre varios nomes de stage
# possiveis do football-data para o formato de 48 equipas.
STAGE_PT = {
    "GROUP_STAGE": ("Fase de Grupos", "Fase de Grupos"),
    "LAST_32": ("Dezasseis avos", "Dezasseis avos de final"),
    "ROUND_OF_32": ("Dezasseis avos", "Dezasseis avos de final"),
    "LAST_16": ("Oitavos", "Oitavos de final"),
    "ROUND_OF_16": ("Oitavos", "Oitavos de final"),
    "QUARTER_FINALS": ("Quartos", "Quartos de final"),
    "SEMI_FINALS": ("Meias-finais", "Meias-finais"),
    "THIRD_PLACE": ("3.o lugar", "Disputa do 3.o lugar"),
    "FINAL": ("Final", "Final"),
}

def fetch_matches():
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        sys.exit("Missing FOOTBALL_DATA_TOKEN env var (free key: football-data.org).")
    req = urllib.request.Request(API, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["matches"]


def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_overrides():
    return load_json(OVERRIDES_FILE)


def load_schedule():
    # utcDate -> {game_no, location, channels(extra)}, from abola.pt (generate_schedule.py)
    return load_json(SCHEDULE_FILE)


def match_key(m):
    return f"{m['homeTeam']['name']}-{m['awayTeam']['name']}"


def stage_pt(m):
    return STAGE_PT.get(m.get("stage", ""), (m.get("stage", ""), m.get("stage", "")))


def group_suffix(m):
    grp = m.get("group")
    return " " + grp.split("_")[-1] if grp else ""  # "GROUP_K" -> " K"


def location_pt(ov, sched):
    # football-data free tier nao devolve o estadio; localizacao vem do
    # schedule.json (abola.pt), com override manual em overrides.json.
    return ov.get("location") or sched.get("location", "")


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def fold(line):
    out = []
    while len(line.encode("utf-8")) > 74:
        cut = 74
        while len(line[:cut].encode("utf-8")) > 74:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return out


def build_ics(matches, overrides, schedule, now):
    # jogo N: numero oficial do schedule.json (abola). Fallback: ordem por data.
    ordered = sorted(matches, key=lambda m: (m["utcDate"], m["id"]))
    game_no = {m["id"]: i + 1 for i, m in enumerate(ordered)}
    for m in matches:
        sched = schedule.get(m["utcDate"])
        if sched and sched.get("game_no"):
            game_no[m["id"]] = sched["game_no"]

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
        sched = schedule.get(m["utcDate"], {})
        channels = DEFAULT_CHANNELS + sched.get("channels", []) + ov.get("channels", [])
        short, long = stage_pt(m)
        gsuf = group_suffix(m)  # "" fora da fase de grupos

        summary = f"⚽ {home} x {away} ({short}{gsuf})"
        desc = (f"Mundial FIFA 2026 — {long}{gsuf} (jogo {game_no[m['id']]}). "
                f"Transmissão: {', '.join(channels)}.")
        if ov.get("youtube"):
            desc += "\nYouTube: " + ov["youtube"]

        ev = [
            "BEGIN:VEVENT",
            "UID:" + ics_escape(f"wc2026-{m['id']}@worldcup-2026-calendar"),
            "DTSTAMP:" + fmt(now),
            "DTSTART:" + fmt(start),
            "DTEND:" + fmt(end),
            "SUMMARY:" + ics_escape(summary),
            "DESCRIPTION:" + ics_escape(desc),
        ]
        loc = location_pt(ov, sched)
        if loc:
            ev.append("LOCATION:" + ics_escape(loc))
        ev.append("END:VEVENT")
        lines += ev
    lines.append("END:VCALENDAR")
    folded = []
    for ln in lines:
        folded += fold(ln)
    return "\r\n".join(folded) + "\r\n"


def selftest():
    now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
    matches = [
        # jogo 84 real: Espanha x Austria, 02.07 20:00 PT = 19:00Z, Los Angeles
        {"id": 500, "utcDate": "2026-07-02T19:00:00Z", "stage": "LAST_32", "group": None,
         "homeTeam": {"name": "Spain"}, "awayTeam": {"name": "Austria"}},
        {"id": 1, "utcDate": "2026-06-11T19:00:00Z", "stage": "GROUP_STAGE", "group": "GROUP_A",
         "homeTeam": {"name": "Mexico"}, "awayTeam": {"name": "Poland"}},
    ]
    schedule = load_schedule()  # real schedule.json (game_no 84, LA)
    ics = build_ics(matches, {}, schedule, now).replace("\r\n ", "")  # unfold
    assert "SUMMARY:⚽ Spain x Austria (Dezasseis avos)" in ics, ics
    assert "DESCRIPTION:Mundial FIFA 2026 — Dezasseis avos de final (jogo 84). Transmissão: Sport TV." in ics, ics
    assert "LOCATION:Los Angeles\\, Estados Unidos da América" in ics, ics
    assert "SUMMARY:⚽ Mexico x Poland (Fase de Grupos A)" in ics
    assert "(jogo 1)" in ics  # sem entrada no schedule -> fallback ordem por data
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    now = datetime.now(timezone.utc)
    matches = fetch_matches()
    ics = build_ics(matches, load_overrides(), load_schedule(), now)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(ics)
    print(f"Wrote {OUT}: {len(matches)} matches")


if __name__ == "__main__":
    main()
