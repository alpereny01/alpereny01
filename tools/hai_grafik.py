#!/usr/bin/env python3
"""Hai-Grafik: ein Drahtgitter-Hai frisst die Contributions der letzten 12 Monate.

Aufruf:
  GH_TOKEN=... python3 tools/hai_grafik.py assets/hai-grafik.svg [--login NAME] [--json kalender.json]

Läuft ohne Abhängigkeiten (nur Standardbibliothek), damit die GitHub Action nichts installieren muss.
"""
import argparse
import datetime
import json
import math
import os
import urllib.request

AKZENT = "#4d7cff"
VIGNETTE = ("#10142a", "#080b17", "#030409")
LINIE = "#8b949e"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

B, H = 1200, 290
ZELLE, LUECKE = 14, 4
GITTER_Y = 98
STUFEN = {"NONE": 0, "FIRST_QUARTILE": 0.35, "SECOND_QUARTILE": 0.55, "THIRD_QUARTILE": 0.78, "FOURTH_QUARTILE": 1}
MONATE = ["JAN", "FEB", "MÄR", "APR", "MAI", "JUN", "JUL", "AUG", "SEP", "OKT", "NOV", "DEZ"]
NACHWACHSEN = 3.0    # Sekunden, bis die Zellen wieder da sind
SCHLAG = 0.6         # Schwanzschlag

ABFRAGE = """query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{
totalContributions weeks{contributionDays{date contributionCount contributionLevel weekday}}}}}}"""


def kalender_laden(login, datei):
    if datei:
        daten = json.load(open(datei, encoding="utf-8"))
    else:
        anfrage = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": ABFRAGE, "variables": {"login": login}}).encode(),
            headers={"Authorization": f"bearer {os.environ['GH_TOKEN']}", "Content-Type": "application/json"},
        )
        daten = json.load(urllib.request.urlopen(anfrage))
    return daten["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def zahl(v):
    t = f"{v:.1f}"
    return t[:-2] if t.endswith(".0") else t


def hai_form(winkel):
    """Hai von oben, Schnauze nach +x, etwa 56 px lang. winkel = Schwanzausschlag in Grad."""
    def schwanz(x, y):
        # alles hinter x = -6 schwingt um den Schwanzstiel mit
        if x >= -6:
            return x, y
        w = math.radians(winkel) * (-6 - x) / 22
        return -6 + (x + 6) * math.cos(w) - y * math.sin(w), (x + 6) * math.sin(w) + y * math.cos(w)
    umriss = [(28, 0), (22, -4.5), (12, -7), (4, -7), (-2, -19), (-6, -18), (-4, -6), (-14, -4), (-24, -2),
              (-28, -1), (-38, -9), (-34, 0), (-38, 9), (-28, 1), (-24, 2), (-14, 4), (-4, 6), (-6, 18),
              (-2, 19), (4, 7), (12, 7), (22, 4.5), (28, 0)]
    mitte = [(26, 0), (-30, 0)]
    rippen = [[(12, -7), (12, 7)], [(0, -6.5), (0, 6.5)], [(-12, -4.2), (-12, 4.2)]]
    linien = [umriss, mitte] + rippen
    return "".join("M" + " ".join(f"{zahl(x)} {zahl(y)}" for x, y in (schwanz(*p) for p in l)) for l in linien)


def kurve(punkte):
    """Catmull-Rom durch alle Punkte als kubische Bézierkurve; liefert Pfad und Bogenlänge bis zu jedem Punkt."""
    d = f"M{zahl(punkte[0][0])} {zahl(punkte[0][1])}"
    laengen, gesamt = [0.0], 0.0
    for i in range(len(punkte) - 1):
        p0, p1, p2 = punkte[max(i - 1, 0)], punkte[i], punkte[i + 1]
        p3 = punkte[min(i + 2, len(punkte) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{zahl(c1[0])} {zahl(c1[1])} {zahl(c2[0])} {zahl(c2[1])} {zahl(p2[0])} {zahl(p2[1])}"
        alt = p1
        for s in range(1, 25):
            t = s / 24
            x = (1 - t) ** 3 * p1[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t * t * c2[0] + t ** 3 * p2[0]
            y = (1 - t) ** 3 * p1[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t * t * c2[1] + t ** 3 * p2[1]
            gesamt += math.hypot(x - alt[0], y - alt[1])
            alt = (x, y)
        laengen.append(gesamt)
    return d, laengen


def svg_bauen(kal, login):
    wochen = kal["weeks"]
    breite = len(wochen) * (ZELLE + LUECKE) - LUECKE
    x0 = (B - breite) / 2
    mitte_y = GITTER_Y + (7 * (ZELLE + LUECKE) - LUECKE) / 2

    zellen, ziele, monate, letzter_monat = [], [], [], None
    for w, woche in enumerate(wochen):
        for tag in woche["contributionDays"]:
            x, y = x0 + w * (ZELLE + LUECKE), GITTER_Y + tag["weekday"] * (ZELLE + LUECKE)
            stufe = STUFEN.get(tag["contributionLevel"], 0)
            zellen.append((x, y, stufe))
            if stufe:
                ziele.append((x + ZELLE / 2, y + ZELLE / 2, len(zellen) - 1))
        monat = int(woche["contributionDays"][0]["date"][5:7])
        if monat != letzter_monat:
            monate.append((w, MONATE[monat - 1]))
            letzter_monat = monat
    # Beschriftung nur, wenn bis zum nächsten Monat Platz ist
    monate = [(x0 + w * (ZELLE + LUECKE), m) for i, (w, m) in enumerate(monate)
              if (monate[i + 1][0] if i + 1 < len(monate) else len(wochen)) - w >= 3]

    start, ende = (-70, mitte_y), (B + 70, mitte_y)
    punkte = [start] + [(x, y) for x, y, _ in ziele] + [ende]
    pfad, laengen = kurve(punkte)
    schwimmen = max(8.0, laengen[-1] / 150)
    dauer = schwimmen + NACHWACHSEN

    def k(t):
        return f"{min(max(t / dauer, 0), 1):.4f}"

    teile = []
    gefressen = {i: laengen[n + 1] / laengen[-1] * schwimmen for n, (_, _, i) in enumerate(ziele)}
    for i, (x, y, stufe) in enumerate(zellen):
        teile.append(f'<rect x="{zahl(x)}" y="{zahl(y)}" width="{ZELLE}" height="{ZELLE}" rx="3" fill="none" '
                     f'stroke="{LINIE}" stroke-opacity=".14"/>')
        if not stufe:
            continue
        te = gefressen[i]
        teile.append(
            f'<rect x="{zahl(x)}" y="{zahl(y)}" width="{ZELLE}" height="{ZELLE}" rx="3" fill="{AKZENT}" opacity="{stufe}">'
            f'<animate attributeName="opacity" values="{stufe};{stufe};0;0;{stufe};{stufe}" '
            f'keyTimes="0;{k(te - 0.05)};{k(te + 0.1)};{k(schwimmen + 0.4)};{k(dauer - 0.3)};1" dur="{zahl(dauer)}s" '
            f'repeatCount="indefinite"/></rect>'
            f'<circle cx="{zahl(x + ZELLE / 2)}" cy="{zahl(y + ZELLE / 2)}" r="4" fill="none" stroke="{AKZENT}" opacity="0">'
            f'<animate attributeName="r" values="4;4;18;18" keyTimes="0;{k(te)};{k(te + 0.45)};1" dur="{zahl(dauer)}s" '
            f'repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;.9;0;0" keyTimes="0;{k(te - 0.01)};{k(te)};{k(te + 0.45)};1" '
            f'dur="{zahl(dauer)}s" repeatCount="indefinite"/></circle>')

    formen = [hai_form(w) for w in (-12, 0, 12, 0, -12)]
    hai = (
        f'<g><animateMotion path="{pfad}" keyPoints="0;1;1" keyTimes="0;{k(schwimmen)};1" calcMode="linear" '
        f'rotate="auto" dur="{zahl(dauer)}s" repeatCount="indefinite"/><g transform="scale(1.25)">'
        f'<ellipse rx="34" ry="18" fill="url(#haiLicht)"/>'
        f'<path d="{formen[0]}" fill="none" stroke="#c9d1d9" stroke-width="1.1" stroke-linejoin="round" stroke-opacity=".9">'
        f'<animate attributeName="d" values="{";".join(formen)}" dur="{SCHLAG}s" repeatCount="indefinite"/></path>'
        f'<circle cx="17" cy="-4" r="1.5" fill="{AKZENT}"/><circle cx="17" cy="4" r="1.5" fill="{AKZENT}"/></g></g>'
    )

    stand = datetime.date.fromisoformat(wochen[-1]["contributionDays"][-1]["date"])
    monat_text = "".join(f'<text x="{zahl(x)}" y="{GITTER_Y - 12}">{m}</text>' for x, m in monate)
    gesamt = kal["totalContributions"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {B} {H}" width="{B}" height="{H}" role="img" aria-label="{gesamt} Contributions von {login} in den letzten 12 Monaten, ein Hai frisst sie">
<title>{gesamt} Contributions in 12 Monaten</title>
<defs>
  <radialGradient id="vignette" cx="0.5" cy="0.5" r="0.8"><stop offset="0" stop-color="{VIGNETTE[0]}"/><stop offset="0.6" stop-color="{VIGNETTE[1]}"/><stop offset="1" stop-color="{VIGNETTE[2]}"/></radialGradient>
  <radialGradient id="haiLicht"><stop offset="0" stop-color="{AKZENT}" stop-opacity=".35"/><stop offset="1" stop-color="{AKZENT}" stop-opacity="0"/></radialGradient>
  <filter id="korn"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="5"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0"/></filter>
  <clipPath id="karte"><rect width="{B}" height="{H}" rx="18"/></clipPath>
</defs>
<style>.blink{{animation:blink 1.1s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}</style>
<g clip-path="url(#karte)">
  <rect width="{B}" height="{H}" fill="url(#vignette)"/>
  <g font-family="{MONO}" font-size="10" letter-spacing="2" fill="{LINIE}" opacity=".8">{monat_text}</g>
  <g>{"".join(teile)}</g>
  {hai}
  <g fill="none" stroke="#c9d1d9" stroke-width="1.5" opacity=".35"><path d="M26 54V26H54"/><path d="M{B - 26} 54V26H{B - 54}"/><path d="M26 {H - 54}V{H - 26}H54"/><path d="M{B - 26} {H - 54}V{H - 26}H{B - 54}"/></g>
  <g font-family="{MONO}" font-size="11" fill="{LINIE}" letter-spacing="2">
    <circle class="blink" cx="40" cy="46" r="4" fill="{AKZENT}"/>
    <text x="52" y="50">CONTRIBUTIONS · 12 MONATE</text>
    <text x="{B - 40}" y="50" text-anchor="end">{gesamt} BEITRÄGE</text>
    <text x="40" y="{H - 40}">hai frisst commits<tspan class="blink" fill="{AKZENT}">_</tspan></text>
    <text x="{B - 40}" y="{H - 40}" text-anchor="end">STAND {stand:%d.%m.%Y}</text>
  </g>
  <rect width="{B}" height="{H}" filter="url(#korn)" opacity=".05"/>
</g>
</svg>
'''


def main():
    teiler = argparse.ArgumentParser()
    teiler.add_argument("ausgabe")
    teiler.add_argument("--login", default=os.environ.get("GH_USER", "alpereny01"))
    teiler.add_argument("--json")
    args = teiler.parse_args()
    svg = svg_bauen(kalender_laden(args.login, args.json), args.login)
    open(args.ausgabe, "w", encoding="utf-8").write(svg)
    print(f"{args.ausgabe}: {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
