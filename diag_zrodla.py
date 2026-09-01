"""
Testuje kilka darmowych zrodel terminarza. Nie zuzywa zapytan RapidAPI.

    python diag_zrodla.py

Kazde zrodlo dostaje jedno zapytanie. Skrypt pokazuje kod HTTP i poczatek
odpowiedzi, zebysmy wiedzieli, ktore da sie sparsowac.
"""
from datetime import date

import requests

H = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}
dzis = date.today()
d1 = f"{dzis:%Y-%m-%d}"
d2 = f"{dzis:%Y%m%d}"

ZRODLA = [
    # Flashscore — feed uzywany przez ich strone
    ("flashscore feed",
     f"https://local-global.flashscore.ninja/2/x/feed/f_2_0_3_pl_1",
     {"x-fsign": "SW9D1eZo"}),
    ("flashscore f_2_1",
     "https://local-global.flashscore.ninja/2/x/feed/f_2_1_3_pl_1",
     {"x-fsign": "SW9D1eZo"}),
    # ATP Tour — oficjalne API strony
    ("atptour scores",
     f"https://www.atptour.com/en/-/www/scores/live", {}),
    ("atptour daily",
     f"https://www.atptour.com/en/-/www/scores/grid/{d2}", {}),
    # Tennis Abstract — statyczne pliki
    ("tennisabstract today",
     "https://www.tennisabstract.com/reports/atp_elo_ratings.html", {}),
    # ESPN — publiczne API
    ("espn scoreboard",
     f"https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"
     f"?dates={d2}", {}),
    # TheSportsDB — darmowy klucz testowy "3"
    ("thesportsdb",
     f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php"
     f"?d={d1}&s=Tennis", {}),
]

for lab, url, extra in ZRODLA:
    hdr = dict(H)
    hdr.update(extra)
    try:
        r = requests.get(url, headers=hdr, timeout=20)
        txt = r.text[:160].replace("\n", " ")
        print(f"{lab:22} HTTP {r.status_code:>3}  {len(r.content):>7} B  {txt}")
    except Exception as e:
        print(f"{lab:22} BLAD  {type(e).__name__}: {str(e)[:70]}")
