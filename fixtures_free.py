"""
Terminarz z publicznego feedu Flashscore — bez klucza i bez limitu.

Dzieki temu 500 zapytan miesiecznych z RapidAPI zostaje w calosci na dane
statystyczne, a terminarz mozna odswiezac dowolnie czesto.

Format feedu jest wlasny: rekordy rozdzielone "~", pola "¬", kazde pole to
"KOD÷wartosc". Znaczenie kodow (odczytane z zywej odpowiedzi):

  ZA  naglowek turnieju, np. "ATP - SINGLES: US Open (USA), hard"
  AA  identyfikator meczu (poczatek rekordu meczu)
  AD  znacznik czasu rozpoczecia (unix)
  AB  status: 1 = zaplanowany, 2 = w trakcie, 3 = zakonczony
  AE / AF   nazwiska skrocone, np. "Blockx A."
  WU / WV   pelne nazwiska w formie "nazwisko-imie" — do dopasowania
  CA / CB   ranking zawodnika (bywa pusty)
"""
from __future__ import annotations

from datetime import datetime, timezone

import requests

BASE = "https://local-global.flashscore.ninja/2/x/feed"
FEEDY = ["f_2_0_3_pl_1", "f_2_1_3_pl_1", "f_2_2_3_pl_1"]  # dzis, jutro, wczoraj
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36"),
    "x-fsign": "SW9D1eZo",
    "Accept": "*/*",
    "Referer": "https://www.flashscore.pl/",
}
STATUS_ZAPLANOWANY = {"1"}


def _pola(rekord: str) -> dict:
    out = {}
    for kawalek in rekord.split("¬"):
        if "÷" in kawalek:
            k, v = kawalek.split("÷", 1)
            out[k] = v
    return out


def _z_slug(slug: str) -> str:
    """'barrios-vera-marcelo-tomas' -> 'Marcelo Tomas Barrios Vera'.

    Flashscore zapisuje slug jako nazwisko-imie. Nie wiemy, gdzie konczy sie
    nazwisko, wiec zwracamy oba warianty do dopasowania — model.match_name
    i tak sprawdza kazdy czlon.
    """
    czesci = [c.capitalize() for c in slug.split("-") if c]
    return " ".join(czesci)


def _naglowek(tekst: str) -> tuple[str, str, str]:
    """'ATP - SINGLES: US Open (USA), hard' -> (kategoria, turniej, kort)."""
    kat, _, reszta = tekst.partition(":")
    kort = ""
    nazwa = reszta.strip()
    if "," in nazwa:
        nazwa, _, kort = nazwa.rpartition(",")
        kort = kort.strip()
    if "(" in nazwa:
        nazwa = nazwa.split("(")[0]
    return kat.strip(), nazwa.strip(), kort


def fetch_events(days_ahead: int = 2, tours=("atp",),
                 debug: bool = False) -> tuple[list[dict], str]:
    """Zwraca (mecze, komunikat). Zgodne z sygnatura fixtures.fetch_events."""
    tylko_atp = "atp" in tours and "wta" not in tours
    events, log = [], []
    widziane = set()

    for feed in FEEDY[:max(1, min(days_ahead, len(FEEDY)))]:
        try:
            r = requests.get(f"{BASE}/{feed}", headers=HEADERS, timeout=25)
        except requests.RequestException as exc:
            log.append(f"{feed}: blad sieci — {exc}")
            continue
        if r.status_code != 200:
            log.append(f"{feed}: HTTP {r.status_code}")
            continue

        rekordy = r.text.split("~")
        kat = nazwa = kort = ""
        n_feed = 0
        for rek in rekordy:
            if rek.startswith("ZA÷"):
                kat, nazwa, kort = _naglowek(_pola(rek).get("ZA", ""))
                continue
            if not rek.startswith("AA÷"):
                continue
            if tylko_atp and not kat.upper().startswith("ATP"):
                continue
            p = _pola(rek)
            if p.get("AB") not in STATUS_ZAPLANOWANY:
                continue          # tylko mecze jeszcze nierozegrane
            mid = p.get("AA", "")
            if not mid or mid in widziane:
                continue
            widziane.add(mid)

            p1 = _z_slug(p.get("WU", "")) or p.get("AE", "")
            p2 = _z_slug(p.get("WV", "")) or p.get("AF", "")
            if not p1 or not p2:
                continue

            start = ""
            ts = p.get("AD")
            if ts and ts.isdigit():
                start = datetime.fromtimestamp(
                    int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")

            events.append({
                "id": mid, "p1": p1, "p2": p2, "start": start,
                "league": "ATP", "tournament": nazwa,
                "rank_name": "", "rank_id": None, "court": kort,
                "rank1": p.get("CA") or None, "rank2": p.get("CB") or None,
                "raw": p,
            })
            n_feed += 1
        log.append(f"{feed}: {n_feed} meczow")

    events.sort(key=lambda e: e["start"] or "9999")
    if events:
        msg = f"Pobrano {len(events)} meczow (Flashscore, bez limitu)."
        if debug:
            msg += "\n\nRaport:\n" + "\n".join(f"  · {x}" for x in log)
        return events, msg
    return [], ("Flashscore nie zwrocil meczow.\n\nProby:\n"
                + "\n".join(f"  · {x}" for x in log))
