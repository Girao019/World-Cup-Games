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

# football-data nome (EN) -> pt-PT
TEAM_PT = {
    "Algeria": "Argélia", "Argentina": "Argentina", "Australia": "Austrália",
    "Austria": "Áustria", "Belgium": "Bélgica", "Bosnia-Herzegovina": "Bósnia e Herzegovina",
    "Brazil": "Brasil", "Canada": "Canadá", "Cape Verde Islands": "Cabo Verde",
    "Colombia": "Colômbia", "Congo DR": "RD Congo", "Croatia": "Croácia",
    "Curaçao": "Curaçau", "Czechia": "República Checa", "Ecuador": "Equador",
    "Egypt": "Egito", "England": "Inglaterra", "France": "França", "Germany": "Alemanha",
    "Ghana": "Gana", "Haiti": "Haiti", "Iran": "Irão", "Iraq": "Iraque",
    "Ivory Coast": "Costa do Marfim", "Japan": "Japão", "Jordan": "Jordânia",
    "Mexico": "México", "Morocco": "Marrocos", "Netherlands": "Países Baixos",
    "New Zealand": "Nova Zelândia", "Norway": "Noruega", "Panama": "Panamá",
    "Paraguay": "Paraguai", "Portugal": "Portugal", "Qatar": "Qatar",
    "Saudi Arabia": "Arábia Saudita", "Scotland": "Escócia", "Senegal": "Senegal",
    "South Africa": "África do Sul", "South Korea": "Coreia do Sul", "Spain": "Espanha",
    "Sweden": "Suécia", "Switzerland": "Suíça", "Tunisia": "Tunísia", "Turkey": "Turquia",
    "United States": "Estados Unidos", "Uruguay": "Uruguai", "Uzbekistan": "Uzbequistão",
}


def team_pt(name):
    return TEAM_PT.get(name, name) if name else None


# Pais: forma curta (descricao "nos EUA") e completa (campo LOCATION).
COUNTRY_SHORT = {"USA": "nos EUA", "Canada": "no Canadá", "Mexico": "no México"}
COUNTRY_FULL = {"USA": "Estados Unidos da América", "Canada": "Canadá", "Mexico": "México"}

# Bracket (abola): jogo -> (jogo feeder A, jogo feeder B). Vencedores.
FEEDERS = {
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
    101: (97, 98), 102: (99, 100),
    104: (101, 102),
}
# 3.o lugar: perdedores das meias-finais.
LOSER_FEEDERS = {103: (101, 102)}


def sides(m, game_no):
    # (home, away) em pt-PT. Se indefinido, "Vencedor/Perdedor do jogo X".
    names = [team_pt(m["homeTeam"]["name"]), team_pt(m["awayTeam"]["name"])]
    feeders, verb = FEEDERS.get(game_no), "Vencedor"
    if feeders is None:
        feeders, verb = LOSER_FEEDERS.get(game_no), "Perdedor"
    out = []
    for i, nm in enumerate(names):
        if nm:
            out.append(nm)
        elif feeders:
            out.append(f"{verb} do jogo {feeders[i]}")
        else:
            out.append("A definir")
    return out[0], out[1]


def join_pt(items):
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


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


def locations(ov, sched):
    # Devolve (campo_LOCATION, forma_curta_descricao). "" quando desconhecido.
    if ov.get("location"):
        return ov["location"], ov["location"]
    city, country = sched.get("city"), sched.get("country")
    if not city:
        return "", ""
    return f"{city}, {COUNTRY_FULL[country]}", f"{city}, {COUNTRY_SHORT[country]}"


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
        gno = game_no[m["id"]]
        home, away = sides(m, gno)
        start = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        end = start + timedelta(minutes=MATCH_MINUTES)
        hhmm = (start + timedelta(hours=1)).strftime("%H:%M")  # hora de Portugal (WEST, UTC+1)

        ov = overrides.get(match_key(m), {})
        sched = schedule.get(m["utcDate"], {})
        channels = DEFAULT_CHANNELS + sched.get("channels", []) + ov.get("channels", [])
        short, _ = stage_pt(m)
        gsuf = group_suffix(m)  # "" fora da fase de grupos
        loc_full, loc_short = locations(ov, sched)

        summary = f"⚽ {home} x {away} ({short}{gsuf})"
        # Template abola: Jogo N - HH:MM - T1 x T2 - Local - TV
        parts = [f"Jogo {gno}", hhmm, f"{home} x {away}"]
        if loc_short:
            parts.append(loc_short)
        parts.append("Transmitido na: " + join_pt(channels))
        desc = " - ".join(parts)
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
        if loc_full:
            ev.append("LOCATION:" + ics_escape(loc_full))
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
        # final (jogo 104) por decidir -> "Vencedor do jogo X"; NY/NJ; TV com "e"
        {"id": 999, "utcDate": "2026-07-19T19:00:00Z", "stage": "FINAL", "group": None,
         "homeTeam": {"name": None}, "awayTeam": {"name": None}},
    ]
    schedule = load_schedule()  # real schedule.json (game_no, cidade, canais)
    ics = build_ics(matches, {}, schedule, now).replace("\r\n ", "")  # unfold
    assert "SUMMARY:⚽ Espanha x Áustria (Dezasseis avos)" in ics, ics
    assert "DESCRIPTION:Jogo 84 - 20:00 - Espanha x Áustria - Los Angeles\\, nos EUA - Transmitido na: Sport TV" in ics, ics
    assert "LOCATION:Los Angeles\\, Estados Unidos da América" in ics, ics
    assert "SUMMARY:⚽ México x Poland (Fase de Grupos A)" in ics, ics  # Poland sem mapa -> igual
    assert "DESCRIPTION:Jogo 1 - 20:00 - México x Poland - Transmitido na: Sport TV" in ics, ics  # sem local
    assert ("DESCRIPTION:Jogo 104 - 20:00 - Vencedor do jogo 101 x Vencedor do jogo 102 - "
            "New York/New Jersey\\, nos EUA - Transmitido na: Sport TV\\, LiveModeTV e RTP") in ics, ics
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
