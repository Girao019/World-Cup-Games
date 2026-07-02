#!/usr/bin/env python3
"""Generate schedule.json from the abola.pt WC 2026 table.

Source: https://www.abola.pt/noticias/mundial-2026-...-onde-ver-...
Gives per-game official number, location and extra pt-PT broadcasters.
Times are Portugal local (UTC+1 in Jun/Jul, no DST change), so utcDate = PT - 1h.
Only games with a known city are listed (group-stage bare-country rows skipped).

Run once after editing the table:  python generate_schedule.py
"""
import json
from datetime import datetime, timedelta

COUNTRY_PT = {"USA": "Estados Unidos da América", "Canada": "Canadá", "Mexico": "México"}

# (game_no, "DD.MM.YYYY HH:MM" Portugal local, city, country, [extra channels])
ROWS = [
    (69, "28.06.2026 00:30", "Miami", "USA", []),
    (73, "28.06.2026 20:00", "Los Angeles", "USA", []),
    (74, "29.06.2026 21:30", "Boston", "USA", []),
    (75, "30.06.2026 02:00", "Monterrey", "Mexico", []),
    (76, "29.06.2026 18:00", "Houston", "USA", []),
    (79, "01.07.2026 02:00", "Mexico City", "Mexico", []),
    (80, "01.07.2026 17:00", "Atlanta", "USA", []),
    (81, "02.07.2026 01:00", "Santa Clara", "USA", []),
    (82, "01.07.2026 21:00", "Seattle", "USA", []),
    (83, "03.07.2026 00:00", "Toronto", "Canada", ["LiveModeTV"]),
    (84, "02.07.2026 20:00", "Los Angeles", "USA", []),
    (85, "03.07.2026 04:00", "Vancouver", "Canada", []),
    (86, "03.07.2026 23:00", "Miami", "USA", ["LiveModeTV"]),
    (87, "04.07.2026 02:30", "Kansas City", "USA", []),
    (88, "03.07.2026 19:00", "Arlington", "USA", []),
    (89, "04.07.2026 22:00", "Philadelphia", "USA", []),
    (90, "04.07.2026 18:00", "Houston", "USA", []),
    (91, "05.07.2026 21:00", "New York/New Jersey", "USA", []),
    (92, "06.07.2026 01:00", "Mexico City", "Mexico", []),
    (93, "06.07.2026 20:00", "Dallas", "USA", []),
    (94, "07.07.2026 01:00", "Seattle", "USA", []),
    (95, "07.07.2026 17:00", "Atlanta", "USA", []),
    (96, "07.07.2026 21:00", "Vancouver", "Canada", []),
    (97, "09.07.2026 21:00", "Boston", "USA", []),
    (98, "10.07.2026 20:00", "Los Angeles", "USA", []),
    (99, "12.07.2026 22:00", "Miami", "USA", []),
    (100, "13.07.2026 02:00", "Kansas City", "USA", []),
    (101, "14.07.2026 20:00", "Dallas", "USA", ["LiveModeTV"]),
    (102, "15.07.2026 20:00", "Atlanta", "USA", ["LiveModeTV"]),
    (103, "18.07.2026 22:00", "Miami", "USA", []),
    (104, "19.07.2026 20:00", "New York/New Jersey", "USA", ["LiveModeTV", "RTP"]),
]


def utc_key(pt_str):
    pt = datetime.strptime(pt_str, "%d.%m.%Y %H:%M")
    return (pt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    out = {}
    for game_no, pt, city, country, extra in ROWS:
        out[utc_key(pt)] = {
            "game_no": game_no,
            "location": f"{city}, {COUNTRY_PT[country]}",
            "channels": extra,
        }
    assert len(out) == len(ROWS), "duplicate utcDate key collision"
    with open("schedule.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"Wrote schedule.json: {len(out)} games")
    # sanity: jogo 84 -> Los Angeles at 19:00Z on 2026-07-02
    assert out["2026-07-02T19:00:00Z"]["location"] == "Los Angeles, Estados Unidos da América"
    assert out["2026-07-02T19:00:00Z"]["game_no"] == 84
    print("sanity OK")


if __name__ == "__main__":
    main()
