#!/usr/bin/env python3
"""Build an ICS feed + HTML page of Portuguese car-motorsport events, Porto emphasis.

Data source: motorsport.json (hand-curated; add events there). No API.

Types: circuit, rally, hillclimb, festival, classic, show, concours.
All-day VEVENTs (DATE value). 'TBC'-dated events are shown on the page but
kept off the .ics (a calendar entry needs a date).

Run:   python build_motorsport.py
Test:  python build_motorsport.py --selftest
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

DATA = "motorsport.json"
ICS_OUT = "motorsport-pt.ics"
HTML_OUT = "motorsport.html"

EMOJI = {
    "circuit": "🏁", "rally": "🏎️", "hillclimb": "⛰️",
    "festival": "🎪", "classic": "🚘", "show": "🏛️", "concours": "🏆",
    "moto": "🏍️", "karting": "🛞", "other": "🏳️",
}
TYPE_PT = {
    "circuit": "Circuito", "rally": "Rali", "hillclimb": "Rampa",
    "festival": "Festival", "classic": "Clássicos", "show": "Salão", "concours": "Concurso",
    "moto": "Motos", "karting": "Karting", "other": "Outros",
}
# FPAK discipline badge code -> our coarse type (for emoji/filter). Anything
# unmapped falls back to "other". The raw code is kept in the category text.
DISCIPLINE_TYPE = {
    "V Ex": "circuit", "CPV": "circuit", "CPVC": "circuit", "C1ECup": "circuit",
    "G1P": "circuit", "FJTV": "circuit", "CT": "circuit",
    "CPR": "rally", "CProR": "rally", "CNR 2RM": "rally", "CRCM": "rally", "CAR": "rally",
    "CCR": "rally", "CSR": "rally", "RSERIES": "rally", "FM": "rally", "R Ex": "rally",
    "RR": "rally", "PER Ex": "rally", "CPRx": "rally", "RxKx Ex": "rally", "FWRX": "rally",
    "RESRx": "rally", "TPRxKx": "rally", "CPTT": "rally", "CPT 4x4": "rally",
    "CISET 4x4": "rally", "W2RC": "rally", "PExTT": "rally", "CPNE": "rally",
    "CPK": "karting", "TPK": "karting", "K Ex": "karting",
    "CPM": "hillclimb", "TPM": "hillclimb", "IHE": "hillclimb", "CPRH": "hillclimb",
    "REG H": "classic", "REG S": "classic", "REGEx": "classic", "TRRAMAK": "classic",
    "TRRHAMAK": "classic", "TFRAIANO": "classic", "CatMI": "classic",
}
# Default ticket note per type when an event has no explicit "tickets" entry.
TICKET_DEFAULT = {
    "rally": "Troços à beira da estrada gratuitos; bancadas/paddock pagos.",
    "hillclimb": "Beira-estrada geralmente gratuita (algumas rampas cobram acesso).",
    "circuit": "Bilhetes na bilheteira do autódromo.",
    "festival": "Bilhete pago, ver site oficial.",
    "classic": "Ver site oficial.",
    "show": "Bilhete pago à entrada / online, ver site.",
    "concours": "Ver site oficial.",
    "moto": "Bilhetes no site oficial / bilheteira.",
    "karting": "Entrada geralmente livre no kartódromo.",
    "other": "Ver página da FPAK.",
}
FPAK_FILE = "fpak-calendar.json"


def ticket_info(e):
    # (note, url_or_None). Explicit event["tickets"] overrides the per-type default.
    t = e.get("tickets")
    if t:
        return t.get("note", TICKET_DEFAULT.get(e["type"], "")), t.get("url")
    return TICKET_DEFAULT.get(e["type"], ""), None


def maps_url(e):
    base = ", ".join(b for b in (e.get("venue"), e.get("city")) if b) or e["name"]
    q = (base + ", Portugal").replace(" ", "+").replace(",", "%2C")
    return "https://www.google.com/maps/search/?api=1&query=" + q


def ics_location(e):
    return ", ".join(b for b in (e.get("venue"), e.get("city"), e.get("region")) if b)


def place_line(e):
    bits = [b for b in (e.get("venue"), e.get("city")) if b]
    head = ", ".join(bits) if bits else e.get("region", "Portugal")
    tail = e.get("region", "")
    return head + (" · " + tail if tail and tail != head else "")


def merge_fpak(curated):
    # Everything in the FPAK feed that is NOT already in the curated list,
    # as lightweight events (no venue/porto/tickets, link back to FPAK).
    if not os.path.exists(FPAK_FILE):
        return []
    fp = json.load(open(FPAK_FILE, encoding="utf-8")).get("events", [])
    from scrape_fpak import not_in_curated
    out = []
    for e in not_in_curated(fp, [c["name"] for c in curated]):
        code = e.get("discipline", "")
        out.append({
            "name": e["name"], "type": DISCIPLINE_TYPE.get(code, "other"),
            "category": ("FPAK · " + code) if code else "FPAK",
            "venue": "", "city": "", "region": "Portugal", "porto": False,
            "start": e["start"], "end": e["end"], "url": e["url"],
            "notes": "Calendário nacional FPAK; detalhes e regulamento no link.",
            "fpak": True,
        })
    return out


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)["events"]


def ics_escape(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


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


def dated(events):
    return [e for e in events if e["start"] != "TBC"]


def build_ics(events, now):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//worldcup-2026-calendar//motorsport-pt//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Automobilismo em Portugal (Porto)",
        "X-WR-TIMEZONE:Europe/Lisbon",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for i, e in enumerate(dated(events)):
        start = date.fromisoformat(e["start"])
        end = date.fromisoformat(e["end"])
        dtend = end + timedelta(days=1)  # DTEND is non-inclusive for all-day
        star = "⭐ " if e.get("porto") else ""
        summary = f"{star}{EMOJI[e['type']]} {e['name']}"
        desc_parts = [e["category"], "Onde: " + place_line(e)]
        if e.get("notes"):
            desc_parts.append(e["notes"])
        tnote, turl = ticket_info(e)
        desc_parts.append("Bilhetes: " + tnote + (" " + turl if turl else ""))
        desc_parts.append(e["url"])
        uid = f"ms-{start.isoformat()}-{i}@worldcup-2026-calendar"
        lines += [
            "BEGIN:VEVENT",
            "UID:" + ics_escape(uid),
            "DTSTAMP:" + now.strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART;VALUE=DATE:" + start.strftime("%Y%m%d"),
            "DTEND;VALUE=DATE:" + dtend.strftime("%Y%m%d"),
            "SUMMARY:" + ics_escape(summary),
            "DESCRIPTION:" + ics_escape("\n".join(desc_parts)),
            "LOCATION:" + ics_escape(ics_location(e)),
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    folded = []
    for ln in lines:
        folded += fold(ln)
    return "\r\n".join(folded) + "\r\n"


def fmt_range(e):
    if e["start"] == "TBC":
        return "Data por confirmar"
    s, en = date.fromisoformat(e["start"]), date.fromisoformat(e["end"])
    months = ["", "jan", "fev", "mar", "abr", "mai", "jun",
              "jul", "ago", "set", "out", "nov", "dez"]
    if s == en:
        return f"{s.day} {months[s.month]}"
    if s.month == en.month:
        return f"{s.day}-{en.day} {months[s.month]}"
    return f"{s.day} {months[s.month]} - {en.day} {months[en.month]}"


def build_html(events, today):
    def sort_key(e):
        # upcoming first (by date), then TBC, then past (most recent first)
        if e["start"] == "TBC":
            return (1, "")
        d = date.fromisoformat(e["start"])
        return (0, d.isoformat()) if d >= today else (2, "")

    ordered = sorted(events, key=sort_key)
    cards = []
    for e in ordered:
        is_tbc = e["start"] == "TBC"
        past = not is_tbc and date.fromisoformat(e["end"]) < today
        star = '<span class="star" title="Área do Porto">⭐</span>' if e.get("porto") else ""
        badge = f'<span class="badge t-{e["type"]}">{EMOJI[e["type"]]} {TYPE_PT[e["type"]]}</span>'
        state = '<span class="past">terminado</span>' if past else (
            '<span class="tbc">a confirmar</span>' if is_tbc else '<span class="up">a caminho</span>')
        tnote, turl = ticket_info(e)
        tlink = f' <a href="{turl}" target="_blank" rel="noopener">bilhetes &rarr;</a>' if turl else ""
        cards.append(f'''    <article class="card{' is-past' if past else ''}" data-type="{e['type']}" data-porto="{str(e.get('porto', False)).lower()}">
      <div class="row1">{badge}{star}<span class="date">{fmt_range(e)}</span>{state}</div>
      <h3><a href="{e['url']}" target="_blank" rel="noopener">{e['name']}</a></h3>
      <p class="cat">{e['category']}</p>
      <p class="where">📍 {place_line(e)} · <a href="{maps_url(e)}" target="_blank" rel="noopener">mapa</a></p>
      <p class="notes">{e.get('notes', '')}</p>
      <p class="tickets">🎟️ {tnote}{tlink}</p>
    </article>''')

    return TEMPLATE.replace("{{CARDS}}", "\n".join(cards)).replace(
        "{{COUNT}}", str(len(events))).replace(
        "{{PORTO}}", str(sum(1 for e in events if e.get("porto")))).replace(
        "{{UPDATED}}", today.isoformat())


TEMPLATE = """<!doctype html>
<html lang="pt-PT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Automobilismo em Portugal · foco no Porto</title>
<style>
  :root { color-scheme: light dark; --bg:#0f1115; --card:#1a1d24; --fg:#e8eaed; --mut:#9aa0aa; --acc:#e63946; --porto:#ffd23f; --line:#2a2e37; }
  @media (prefers-color-scheme: light) { :root { --bg:#f4f5f7; --card:#fff; --fg:#1a1d24; --mut:#5a6069; --line:#e2e5ea; } }
  * { box-sizing: border-box; }
  body { margin:0; font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:var(--bg); color:var(--fg); }
  header { padding:2rem 1.2rem 1rem; max-width:900px; margin:0 auto; }
  h1 { margin:0 0 .3rem; font-size:1.7rem; }
  .sub { color:var(--mut); margin:0 0 1rem; }
  .sub b { color:var(--porto); }
  .subscribe { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.8rem 1rem; margin:1rem 0; }
  .subscribe code { background:rgba(128,128,128,.15); padding:.15rem .4rem; border-radius:5px; font-size:.85em; word-break:break-all; }
  .fbtn { background:var(--acc); color:#fff; border:0; padding:.3rem .7rem; border-radius:6px; cursor:pointer; font:inherit; font-size:.8rem; margin:.3rem 0; }
  .filters { display:flex; flex-wrap:wrap; gap:.4rem; max-width:900px; margin:0 auto; padding:.5rem 1.2rem; position:sticky; top:0; background:var(--bg); z-index:2; }
  .filters button { border:1px solid var(--line); background:var(--card); color:var(--fg); padding:.4rem .8rem; border-radius:20px; cursor:pointer; font-size:.85rem; }
  .filters button.on { background:var(--acc); color:#fff; border-color:var(--acc); }
  .filters button.porto.on { background:var(--porto); color:#1a1d24; border-color:var(--porto); }
  main { max-width:900px; margin:0 auto; padding:.5rem 1.2rem 3rem; display:grid; gap:.8rem; }
  .card { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--acc); border-radius:10px; padding:.9rem 1.1rem; }
  .card[data-porto="true"] { border-left-color:var(--porto); }
  .card.is-past { opacity:.55; }
  .row1 { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; margin-bottom:.4rem; }
  .badge { font-size:.75rem; padding:.15rem .5rem; border-radius:6px; background:rgba(128,128,128,.18); white-space:nowrap; }
  .star { font-size:1rem; }
  .date { font-weight:700; margin-left:auto; }
  .up { font-size:.7rem; color:#2ecc71; text-transform:uppercase; letter-spacing:.05em; }
  .tbc { font-size:.7rem; color:var(--porto); text-transform:uppercase; letter-spacing:.05em; }
  .past { font-size:.7rem; color:var(--mut); text-transform:uppercase; letter-spacing:.05em; }
  h3 { margin:.1rem 0 .3rem; font-size:1.1rem; }
  h3 a { color:var(--fg); text-decoration:none; }
  h3 a:hover { color:var(--acc); text-decoration:underline; }
  .cat { margin:.1rem 0; color:var(--fg); font-size:.9rem; }
  .where { margin:.2rem 0; color:var(--mut); font-size:.88rem; }
  .notes { margin:.3rem 0 0; color:var(--mut); font-size:.83rem; }
  .tickets { margin:.4rem 0 0; font-size:.83rem; }
  .tickets a { color:var(--acc); font-weight:600; text-decoration:none; white-space:nowrap; }
  .where a { color:var(--mut); }
  footer { text-align:center; color:var(--mut); font-size:.8rem; padding:1rem; }
</style>
</head>
<body>
<header>
  <h1>🏁 Automobilismo em Portugal</h1>
  <p class="sub"><b>⭐ Foco no Porto e Norte.</b> Circuito, ralis, rampas, clássicos e mais. {{COUNT}} eventos, {{PORTO}} na área do Porto. Destaques curados + calendário nacional FPAK (🏳️) automático.</p>
  <div class="subscribe">
    📅 <strong>Subscreve o calendário</strong> (atualiza sozinho no telemóvel/Google Calendar).<br>
    Google Calendar: "Outros calendários" &rarr; <b>+</b> &rarr; <b>A partir do URL</b>, colar:<br>
    <code id="feed">https://girao019.github.io/World-Cup-Games/motorsport-pt.ics</code>
    <button class="fbtn" id="copy" type="button">Copiar</button><br>
    <small>Telemóvel/Apple: <a href="webcal://girao019.github.io/World-Cup-Games/motorsport-pt.ics">clicar para subscrever</a>. Ou <a href="motorsport-pt.ics">descarregar .ics</a>.</small>
  </div>
</header>
<div class="filters" id="filters">
  <button data-f="all" class="on">Todos</button>
  <button data-f="porto" class="porto">⭐ Porto</button>
  <button data-f="rally">🏎️ Ralis</button>
  <button data-f="hillclimb">⛰️ Rampas</button>
  <button data-f="circuit">🏁 Circuito</button>
  <button data-f="moto">🏍️ Motos</button>
  <button data-f="karting">🛞 Karting</button>
  <button data-f="festival">🎪 Festivais</button>
  <button data-f="classic">🚘 Clássicos</button>
  <button data-f="show">🏛️ Salões</button>
  <button data-f="other">🏳️ Outros</button>
</div>
<main id="list">
{{CARDS}}
</main>
<footer>Dados curados de fpak.pt, wrc.com, exponor e calendários oficiais · atualizado {{UPDATED}}</footer>
<script>
  const cp = document.getElementById('copy');
  if (cp) cp.onclick = () => navigator.clipboard.writeText(document.getElementById('feed').textContent)
    .then(() => { cp.textContent = 'Copiado!'; setTimeout(() => cp.textContent = 'Copiar', 1500); });
  const btns = document.querySelectorAll('#filters button');
  const cards = document.querySelectorAll('#list .card');
  btns.forEach(b => b.onclick = () => {
    btns.forEach(x => x.classList.remove('on'));
    b.classList.add('on');
    const f = b.dataset.f;
    cards.forEach(c => {
      const show = f === 'all' || (f === 'porto' ? c.dataset.porto === 'true' : c.dataset.type === f);
      c.style.display = show ? '' : 'none';
    });
  });
</script>
</body>
</html>
"""


def selftest():
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    events = [
        {"name": "Test Porto Rampa", "type": "hillclimb", "category": "CPM", "venue": "X",
         "city": "Braga", "region": "Norte", "porto": True, "start": "2026-05-15",
         "end": "2026-05-17", "url": "https://x", "notes": "n"},
        {"name": "Test TBC", "type": "classic", "category": "C", "venue": "Y", "city": "Porto",
         "region": "Norte", "porto": True, "start": "TBC", "end": "TBC", "url": "https://y"},
        {"name": "Test Paid", "type": "festival", "category": "F", "venue": "Z", "city": "Braga",
         "region": "Norte", "porto": False, "start": "2026-09-01", "end": "2026-09-02",
         "url": "https://z", "tickets": {"url": "https://buy", "note": "10€"}},
        {"name": "Rali Teste FPAK", "type": "other", "category": "FPAK · CPR", "venue": "",
         "city": "", "region": "Portugal", "porto": False, "start": "2026-08-10",
         "end": "2026-08-11", "url": "https://fpak", "notes": "n", "fpak": True},
    ]
    ics = build_ics(events, now).replace("\r\n ", "")  # unfold
    assert "SUMMARY:⭐ ⛰️ Test Porto Rampa" in ics, ics
    assert "DTSTART;VALUE=DATE:20260515" in ics, ics
    assert "DTEND;VALUE=DATE:20260518" in ics, ics  # end +1 day, non-inclusive
    assert "LOCATION:X\\, Braga\\, Norte" in ics, ics
    assert "SUMMARY:🏳️ Rali Teste FPAK" in ics, ics  # FPAK event, no star
    assert "LOCATION:Portugal" in ics, ics  # empty venue/city falls back to region
    assert ics.count("BEGIN:VEVENT") == 3, "TBC event must NOT be in ICS"
    assert "Bilhetes: Beira-estrada" in ics, ics  # per-type default note
    assert "Bilhetes: 10€ https://buy" in ics, ics  # explicit ticket override + url
    html = build_html(events, date(2026, 7, 13))
    assert 'data-porto="true"' in html
    assert "Data por confirmar" in html  # TBC rendered on page
    assert "terminado" in html  # past event state rendered
    assert 'href="https://buy"' in html and "bilhetes &rarr;" in html  # buy link
    assert "google.com/maps" in html  # maps link
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    now = datetime.now(timezone.utc)
    events = load()
    fpak = merge_fpak(events)
    events += fpak
    with open(ICS_OUT, "w", encoding="utf-8") as f:
        f.write(build_ics(events, now))
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(build_html(events, now.date()))
    print(f"Wrote {ICS_OUT} ({len(dated(events))} dated) and {HTML_OUT} "
          f"({len(events)} total: {len(events) - len(fpak)} curados + {len(fpak)} FPAK)")


if __name__ == "__main__":
    main()
