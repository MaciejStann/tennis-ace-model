"""
Terminarz meczow z Tennis API (RapidAPI, host tennis-api-atp-wta-itf).

Endpoint: /tennis/v2/{atp|wta}/fixtures[/{data}[/{data_do}]]
Nie wymaga zadnych identyfikatorow zawodnikow — zwraca nazwiska, ktore
dopasowujemy do lokalnej bazy. To dlatego dziala tam, gdzie endpointy
statystyk (wymagajace numerycznych ID) zawodzily.

Klucz: api_key.txt z linia `RAPID_KEY=...` albo zmienna RAPID_KEY.
"""
from __future__ import annotations

import os
import pathlib
from datetime import date, timedelta

import requests

HOST = "tennis-api-atp-wta-itf.p.rapidapi.com"
BASE = f"https://{HOST}/tennis/v2"
HERE = pathlib.Path(__file__).parent


def get_key() -> str | None:
    """
    Kolejnosc szukania klucza:
      1. st.secrets  — Streamlit Community Cloud
      2. zmienna srodowiskowa
      3. plik lokalny (tylko na wlasnym komputerze; NIE commitowac)
    """
    try:                       # dziala tylko gdy aplikacja chodzi w Streamlit
        import streamlit as st
        for k in ("RAPID_KEY", "RAPIDAPI_KEY"):
            if k in st.secrets:
                return str(st.secrets[k]).strip()
    except Exception:
        pass
    for env in ("RAPID_KEY", "RAPIDAPI_KEY"):
        if os.environ.get(env):
            return os.environ[env].strip()
    for fname in ("api_key.txt", "api_keys.txt"):
        path = HERE / fname
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "RAPID" in line.upper() and "=" in line:
                return line.split("=", 1)[1].strip()
    return None


def _headers(key: str) -> dict:
    return {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}


def _dig(node, keys, depth=0):
    if depth > 6:
        return None
    if isinstance(node, dict):
        for k in keys:
            if k in node and node[k] not in (None, "", []):
                return node[k]
        for v in node.values():
            if isinstance(v, (dict, list)):
                got = _dig(v, keys, depth + 1)
                if got is not None:
                    return got
    elif isinstance(node, list):
        for v in node[:30]:
            got = _dig(v, keys, depth + 1)
            if got is not None:
                return got
    return None


def _pname(node) -> str:
    """Wyciaga nazwisko z obiektu zawodnika w dowolnym z mozliwych ksztaltow."""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    val = _dig(node, ["name", "fullName", "playerName", "displayName", "title"])
    if isinstance(val, dict):
        val = _dig(val, ["long", "full", "display", "short", "en"])
    return str(val or "").strip()


def _parse(payload, tour: str) -> list[dict]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    out = []
    for fx in rows:
        if not isinstance(fx, dict):
            continue
        p1 = _pname(fx.get("player1") or fx.get("p1") or fx.get("home"))
        p2 = _pname(fx.get("player2") or fx.get("p2") or fx.get("away"))
        if not p1 or not p2:
            continue

        tour_obj = fx.get("tournament") or {}
        tname = _pname(tour_obj) or str(_dig(fx, ["tournamentName"]) or "")
        court, rank_name, rank_id = "", "", None
        if isinstance(tour_obj, dict):
            court = _pname(tour_obj.get("court")) or ""
            rank_obj = tour_obj.get("rank") or {}
            rank_name = _pname(rank_obj) or ""
            if isinstance(rank_obj, dict):
                rid = _dig(rank_obj, ["id", "rankId"])
                rank_id = int(rid) if str(rid).isdigit() else None

        out.append({
            "id": str(fx.get("id") or fx.get("fixtureId") or f"{tour}|{p1}|{p2}"),
            "p1": p1,
            "p2": p2,
            "start": str(_dig(fx, ["date", "startDate", "startTime",
                                   "scheduled", "time"]) or ""),
            "league": tour.upper(),
            "tournament": tname,
            "court": court,
            "rank_name": rank_name,
            "rank_id": rank_id,
            "raw": fx,
        })
    return out


def fetch_events(days_ahead: int = 3, limit: int = 100,
                 tours: tuple[str, ...] = ("atp",),
                 debug: bool = False) -> tuple[list[dict], str]:
    """Zwraca (mecze, komunikat)."""
    key = get_key()
    if not key:
        return [], ("Brak klucza RapidAPI. Utworz `api_key.txt` z linia "
                    "`RAPID_KEY=twoj_klucz` albo ustaw zmienna RAPID_KEY.")

    today = date.today()
    end = today + timedelta(days=max(days_ahead, 1))
    events, log = [], []

    for tour in tours:
        # zakres dat, a jesli nie zadziala — sam dzisiejszy terminarz
        urls = [
            f"{BASE}/{tour}/fixtures/{today:%Y-%m-%d}/{end:%Y-%m-%d}",
            f"{BASE}/{tour}/fixtures",
        ]
        for url in urls:
            params = {"pageSize": limit, "pageNo": 1,
                      "include": "tournament,tournament.court,tournament.rank",
                      "filter": "PlayerGroup:singles"}
            try:
                resp = requests.get(url, headers=_headers(key),
                                    params=params, timeout=25)
            except requests.RequestException as exc:
                log.append(f"{url.split('/v2/')[1]}: blad sieci — {exc}")
                continue

            tag = url.split("/v2/")[1]
            if resp.status_code != 200:
                log.append(f"{tag}: HTTP {resp.status_code} — {resp.text[:120]}")
                continue
            try:
                payload = resp.json()
            except ValueError:
                log.append(f"{tag}: odpowiedz nie jest JSON-em")
                continue

            got = _parse(payload, tour)
            log.append(f"{tag}: HTTP 200 — {len(got)} meczow")
            if got:
                events.extend(got)
                break  # udalo sie dla tego touru

    if events:
        msg = f"Pobrano {len(events)} meczow."
        if debug:
            msg += "\n\nRaport:\n" + "\n".join(f"  · {x}" for x in log)
        return events, msg

    report = "\n".join(f"  · {x}" for x in log)
    hint = ""
    joined = " ".join(log)
    if "401" in joined:
        hint = ("\n\n**HTTP 401** — klucz nieprawidlowy albo brak subskrypcji "
                "tego produktu na RapidAPI.")
    elif "403" in joined:
        hint = ("\n\n**HTTP 403** — zly naglowek hosta albo endpoint poza "
                "twoim planem.")
    elif "429" in joined:
        hint = ("\n\n**HTTP 429** — limit zapytan. Jesli w komunikacie jest "
                "DAILY quota, odnowi sie o polnocy UTC (2:00 czasu polskiego). "
                "Aplikacja dziala bez terminarza — uzyj zakladki "
                "**Wybor reczny**, statystyki licza sie lokalnie.")
    elif "200" in joined:
        hint = ("\n\n API odpowiedzialo poprawnie, ale nie rozpoznalem "
                "struktury odpowiedzi. Wklej fragment JSON-a — dopasuje parser.")

    return [], f"Nie udalo sie pobrac terminarza.\n\nProby:\n{report}{hint}"
