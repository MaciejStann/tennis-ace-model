"""
Diagnostyka terminarza — pokazuje dokladnie, co zwraca API.

    python diag_fixtures.py

Zuzywa maksymalnie kilka zapytan.
"""
import json
from datetime import date, timedelta

import requests

from fixtures import BASE, HOST, get_key

key = get_key()
if not key:
    raise SystemExit("Brak klucza. Utworz api_key.txt z linia RAPID_KEY=...")

H = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}
dzis = date.today()

warianty = [
    ("dzis + 2 dni", f"/atp/fixtures/{dzis:%Y-%m-%d}/{dzis + timedelta(days=2):%Y-%m-%d}"),
    ("bez dat", "/atp/fixtures"),
    ("tylko dzis", f"/atp/fixtures/{dzis:%Y-%m-%d}"),
]

for lab, sciezka in warianty:
    print(f"\n{'=' * 60}\n{lab}: {sciezka}")
    try:
        r = requests.get(f"{BASE}{sciezka}", headers=H, timeout=25,
                         params={"pageSize": 5, "pageNo": 1,
                                 "include": "tournament,tournament.court,"
                                            "tournament.rank"})
    except Exception as e:
        print(f"  blad sieci: {e}")
        continue
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"  tresc: {r.text[:300]}")
        continue
    try:
        d = r.json()
    except ValueError:
        print(f"  nie-JSON: {r.text[:200]}")
        continue
    rows = d.get("data") if isinstance(d, dict) else d
    print(f"  typ odpowiedzi: {type(d).__name__}, "
          f"klucze: {list(d)[:6] if isinstance(d, dict) else '-'}")
    print(f"  meczow: {len(rows) if isinstance(rows, list) else 'brak listy'}")
    if isinstance(rows, list) and rows:
        print("\n  --- pierwszy mecz (surowy) ---")
        print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:1200])
        break
