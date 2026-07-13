#!/usr/bin/env python3
"""Scrape the FPAK national calendar into a normalized JSON feed.

FPAK (Portuguese motorsport federation) publishes the full national calendar
at https://www.fpak.pt/calendario as server-rendered Drupal HTML. No API/iCal.
Each event carries a `data-date="<startTS> - <endTS>"` (unix seconds), a
discipline badge (e.g. "V Ex", "Karting", "Ralis"), and a link with the name.

We take only FACTS (date, name, discipline, link) and attribute back to FPAK.
This is the raw feed; the curated motorsport.json stays hand-maintained. The
weekly workflow re-runs this and opens a PR when fpak-calendar.json changes,
so a human folds real new events into motorsport.json.

Run:    python scrape_fpak.py            # fetch live -> fpak-calendar.json
Report: python scrape_fpak.py --report   # + list FPAK events not in motorsport.json
Test:   python scrape_fpak.py --selftest  # offline parser check
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

URL = "https://www.fpak.pt/calendario"
BASE = "https://www.fpak.pt"
OUT = "fpak-calendar.json"
CURATED = "motorsport.json"

ROW_RE = re.compile(r'views-row.*?</a>', re.DOTALL)
DATE_RE = re.compile(r'data-date="(\d+)\s*-\s*(\d+)"')
BADGE_RE = re.compile(r'badge[^>]*>\s*([^<]+?)\s*</span>')
LINK_RE = re.compile(r'href="(/calendario/[^"]+)"[^>]*>\s*([^<]+?)\s*</a>')


def ts_to_date(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")


def parse(html):
    events = []
    for row in ROW_RE.findall(html):
        d = DATE_RE.search(row)
        link = LINK_RE.search(row)
        if not d or not link:
            continue
        badge = BADGE_RE.search(row)
        events.append({
            "start": ts_to_date(d.group(1)),
            "end": ts_to_date(d.group(2)),
            "discipline": badge.group(1).strip() if badge else "",
            "name": re.sub(r"\s+", " ", link.group(2)).strip(),
            "url": BASE + link.group(1),
        })
    # stable order: by date then name
    events.sort(key=lambda e: (e["start"], e["name"]))
    return events


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": "worldcup-2026-calendar/fpak-scrape (+github pages)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def load_curated_names():
    if not os.path.exists(CURATED):
        return []
    events = json.load(open(CURATED, encoding="utf-8"))["events"]
    return [e["name"].lower() for e in events]


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def not_in_curated(fpak_events, curated_names):
    # crude token-overlap match: FPAK event is "new" if no curated name shares
    # a distinctive word (>4 chars) with it. Good enough to flag candidates.
    cur_tokens = [set(norm(n).split()) for n in curated_names]
    new = []
    for e in fpak_events:
        toks = {t for t in norm(e["name"]).split() if len(t) > 4}
        if not any(toks & c for c in cur_tokens):
            new.append(e)
    return new


def selftest():
    sample = '''
    <div class="views-row">
      <div class="date hidden" data-date="1768651200 - 1768737600">x</div>
      <div class="small"><span class="badge badge-success">V Ex</span></div>
      <div><a href="/calendario/2026-01-17-gt-winter-series" hreflang="zxx">GT Winter Series</a></div>
    </div>
    <div class="views-row">
      <div class="date hidden" data-date="1778112000 - 1778371200">y</div>
      <div class="small"><span class="badge badge-danger">Ralis</span></div>
      <div><a href="/calendario/2026-05-07-rally-de-portugal">Vodafone   Rally de Portugal</a></div>
    </div>'''
    ev = parse(sample)
    assert len(ev) == 2, ev
    assert ev[0] == {"start": "2026-01-17", "end": "2026-01-18", "discipline": "V Ex",
                     "name": "GT Winter Series", "url": BASE + "/calendario/2026-01-17-gt-winter-series"}, ev[0]
    assert ev[1]["name"] == "Vodafone Rally de Portugal", ev[1]  # whitespace collapsed
    assert ev[1]["discipline"] == "Ralis"
    # matcher: "Rally de Portugal" is in curated -> not flagged; "GT Winter Series" is new
    new = not_in_curated(ev, ["Vodafone Rally de Portugal (WRC)"])
    assert [e["name"] for e in new] == ["GT Winter Series"], new
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    events = parse(fetch())
    if not events:
        sys.exit("Parsed 0 events; FPAK markup likely changed. Check scrape_fpak.py regexes.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": URL, "scraped_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                   "count": len(events), "events": events}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {OUT}: {len(events)} events")
    if "--report" in sys.argv:
        new = not_in_curated(events, load_curated_names())
        print(f"\n{len(new)} FPAK events not obviously in {CURATED}:")
        for e in new:
            print(f"  {e['start']}  [{e['discipline']}]  {e['name']}")


if __name__ == "__main__":
    main()
