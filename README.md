# Mundial FIFA 2026 - Calendário (pt-PT)

Auto-updated Google Calendar feed of every FIFA World Cup 2026 match, with the
Portuguese (pt-PT) TV channels and YouTube channel broadcasting each game.

- **Sport TV** shows all games (added to every event automatically).
- **LiveModeTV, RTP, SIC, TVI** and YouTube links are per-game, set in `overrides.json`.

## How it works

1. GitHub Actions runs daily (`.github/workflows/update.yml`), fetches fixtures
   from [football-data.org](https://www.football-data.org), merges broadcaster
   info, writes `worldcup.ics`, and publishes it via GitHub Pages.
2. You subscribe to that `.ics` URL once in Google Calendar. It refreshes itself.

## Setup (once)

1. Get a free API key at football-data.org, add repo secret `FOOTBALL_DATA_TOKEN`.
2. Repo Settings → Pages → Source = **GitHub Actions**.
3. Run the workflow (Actions tab → Run workflow), or wait for the daily cron.
4. Feed URL: `https://<user>.github.io/<repo>/worldcup.ics`

## Subscribe in Google Calendar

Google Calendar → **Other calendars** → **+** → **From URL** → paste the feed URL.
(Google polls the URL periodically, so new games/channels appear automatically.)

## Editing broadcasters

Edit `overrides.json`. Key = `HomeTeam-AwayTeam` exactly as football-data.org
names the teams (English, e.g. `Spain-Austria`). Only list EXTRA channels
beyond Sport TV. `location` is free text (the free API does not provide the
venue, so set it per game if you want a location on the event):

```json
{
  "Spain-Austria": {
    "location": "Los Angeles, Estados Unidos da América",
    "channels": ["SIC", "LiveModeTV"],
    "youtube": "https://youtube.com/@livemodetv"
  }
}
```

Event format:

```
SUMMARY:     ⚽ Spain x Austria (Dezasseis avos)
LOCATION:    Los Angeles, Estados Unidos da América
DESCRIPTION: Mundial FIFA 2026 — Dezasseis avos de final (jogo 84). Transmissão: Sport TV.
```

### Locations, official game numbers, extra channels

`schedule.json` holds per-game location, the official `jogo N` and extra
broadcasters (LiveModeTV, RTP), sourced from
[abola.pt](https://www.abola.pt) and keyed by UTC kickoff time. It is matched
to the live fixtures by kickoff time. Edit the `ROWS` table in
`generate_schedule.py` and run `python generate_schedule.py` to regenerate it.

Games not in `schedule.json` (most group-stage games) get no location and a
fallback `jogo N` derived from kickoff order.

## Local run / test

```bash
python build_calendar.py --selftest        # no network, asserts output
FOOTBALL_DATA_TOKEN=xxx python build_calendar.py   # writes worldcup.ics
```

