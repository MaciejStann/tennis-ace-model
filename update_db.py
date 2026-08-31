"""
Aktualizacja bazy o swieze mecze z Tennis API (RapidAPI).

TML-Database jest zamrozona (styczen 2026). Ten skrypt dociaga brakujace
mecze przez endpoint past-matches z per-meczowymi statystykami serwisu
i dopisuje je do lokalnej bazy w tym samym formacie co TML.

Uzycie:
    python update_db.py --inspect "Daniil Medvedev"   # podglad surowej odpowiedzi
    python update_db.py --top 150                     # aktualizuj top 150 rankingu
    python update_db.py --years 2026                  # tylko wybrane sezony

Klucz: api_key.txt z linia RAPID_KEY=... albo zmienna RAPID_KEY.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

import pandas as pd
import requests
from datetime import date, timedelta
from urllib.parse import quote

from fixtures import HOST, get_key

BASE = f"https://{HOST}/tennis/v2"
DATA = pathlib.Path(__file__).parent / "data"
RATE_SLEEP = 0.7          # ~85 zapytan/min, limit API to 100/min
DEBUG = False

# Encja Stat uzywa pol z SUFIKSEM numeru zawodnika (1 lub 2) oraz wzorca
# ulamkowego: pole bazowe = osiagniete, pole z "Of" = mozliwe.
# Np. firstServe1 / firstServeOf1 = procent pierwszego serwisu player1,
# a firstServeOf1 to zarazem liczba punktow serwisowych player1.
ACE_KEYS = ("aces", "ace", "serviceAces", "acesGm")
DF_KEYS = ("doubleFaults", "doubleFault", "df", "dfs")
# kolejnosc ma znaczenie — pierwszy trafiony wygrywa
SVPT_KEYS = ("servicePointsOf", "servicePoints", "firstServeOf",
             "totalServicePoints", "servicePointsPlayed")
SVGM_KEYS = ("serviceGamesOf", "serviceGames", "gamesServed",
             "serviceGamesPlayed")


def pick(stat: dict, keys, suffix: str):
    """Szuka pola z sufiksem zawodnika, potem bez sufiksu."""
    if not isinstance(stat, dict):
        return None
    lower = {k.lower(): v for k, v in stat.items()}
    for k in keys:
        for cand in (f"{k}{suffix}", k):
            v = lower.get(cand.lower())
            if v not in (None, "", []):
                return num(v)
    return None


class QuotaExhausted(Exception):
    """Miesieczna kwota RapidAPI wyczerpana — czekanie nic nie da."""


class Api:
    def __init__(self, key: str):
        self.h = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": HOST}
        self.calls = 0
        self._waited = 0

    def get(self, path: str, **params):
        url = f"{BASE}{path}"
        r = requests.get(url, headers=self.h, params=params, timeout=30)
        self.calls += 1
        time.sleep(RATE_SLEEP)
        if r.status_code in (429, 403):
            body = (r.text or "").lower()
            # "quota" = kwota miesieczna; czekanie nie pomoze
            if "quota" in body or "exceeded the" in body or "monthly" in body:
                raise QuotaExhausted(r.text[:200])
            if r.status_code == 429:
                self._waited += 1
                print(f"  429 (proba {self._waited}/2): {r.text[:160]}")
                if self._waited > 2:
                    raise QuotaExhausted("powtarzajace sie 429 — przerywam")
                print("  czekam 30 s...")
                time.sleep(30)
                return self.get(path, **params)
        self._waited = 0
        if r.status_code != 200:
            return {"_error": f"HTTP {r.status_code}", "_body": r.text[:300]}
        try:
            return r.json()
        except ValueError:
            return {"_error": "nie-JSON", "_body": r.text[:300]}


def dig(node, keys, depth=0):
    """Pierwsza niepusta wartosc dla ktoregokolwiek z kluczy."""
    if depth > 5:
        return None
    if isinstance(node, dict):
        for k in keys:
            if k in node and node[k] not in (None, "", []):
                return node[k]
        for v in node.values():
            if isinstance(v, (dict, list)):
                got = dig(v, keys, depth + 1)
                if got is not None:
                    return got
    elif isinstance(node, list):
        for v in node[:20]:
            got = dig(v, keys, depth + 1)
            if got is not None:
                return got
    return None


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


ID_FIELDS = ("id", "playerId", "playerID", "player_id", "atpId", "wtaId")


def search_name(api: Api, name: str, tour="atp") -> str | None:
    """
    Endpoint search zwraca LISTE STRINGOW z nazwami (bez ID).
    Sluzy wiec tylko do potwierdzenia dokladnego zapisu nazwy.
    """
    for q in (name, name.split()[-1]):
        d = api.get(f"/profile/search/{quote(q)}/{tour}")
        if "_error" in d:
            continue
        rows = d.get("data") if isinstance(d, dict) else d
        if isinstance(rows, dict):
            rows = rows.get("result") or rows.get("players") or []
        if not isinstance(rows, list) or not rows:
            continue
        names = [r if isinstance(r, str) else
                 (r.get("name") or r.get("fullName") or "")
                 for r in rows]
        names = [n for n in names if n]
        for n in names:
            if n.strip().lower() == name.strip().lower():
                return n
        # nie ma dokladnego — sprobuj po nazwisku + inicjale imienia
        first = name.split()[0].lower()
        for n in names:
            if n.split()[0].lower() == first:
                return n
    return None


# Profil nie ma pola "id", ale ID siedzi w sciezce zdjecia:
#   "/tennis/api2/uploads/Photo/atp/22807.jpg"  ->  22807
IMG_ID = re.compile(r"/Photo/(?:atp|wta)/(\d+)\.", re.I)


def deep_id(node, depth=0):
    """Szuka numerycznego ID: najpierw w polach, potem w sciezce zdjecia."""
    if depth > 5:
        return None
    if isinstance(node, dict):
        for k in ID_FIELDS:
            v = node.get(k)
            if str(v).isdigit() and int(v) > 0:
                return int(v)
        for v in node.values():
            if isinstance(v, str):
                m = IMG_ID.search(v)
                if m:
                    return int(m.group(1))
            elif isinstance(v, (dict, list)):
                got = deep_id(v, depth + 1)
                if got:
                    return got
    elif isinstance(node, list):
        for v in node[:20]:
            got = deep_id(v, depth + 1)
            if got:
                return got
    return None


def id_via_country(api: Api, name: str, country: str, tour="atp") -> int | None:
    """
    Zapasowa droga: lista zawodnikow zawezona filtrem kraju (z profilu).
    Zamiast tysiecy rekordow przegladamy kilkadziesiat.
    """
    if not country:
        return None
    page, size = 1, 200
    while page <= 5:
        d = api.get(f"/{tour}/player", pageSize=size, pageNo=page,
                    filter=f"PlayerCountry:{country}")
        if "_error" in d:
            return None
        rows = d.get("data") if isinstance(d, dict) else d
        if not isinstance(rows, list) or not rows:
            return None
        for r in rows:
            if not isinstance(r, dict):
                continue
            if str(r.get("name", "")).strip().lower() == name.strip().lower():
                pid = r.get("id")
                if str(pid).isdigit():
                    return int(pid)
        if len(rows) < size:
            return None
        page += 1
    return None


ID_CACHE = DATA / "player_ids.json"


def load_cache() -> dict:
    if ID_CACHE.exists():
        try:
            return json.loads(ID_CACHE.read_text())
        except ValueError:
            return {}
    return {}


def save_cache(c: dict):
    ID_CACHE.write_text(json.dumps(c, indent=1, ensure_ascii=False))


def find_id(api: Api, name: str, tour="atp") -> tuple[int | None, str | None]:
    """
    1) search  -> potwierdza dokladny zapis nazwy (zwraca same stringi)
    2) profile -> z niego wyciagamy numeryczne ID
    """
    exact = search_name(api, name, tour) or name
    prof = api.get(f"/profile/{quote(exact)}")
    if "_error" in prof:
        return None, exact

    pid = deep_id(prof)
    if pid:
        return pid, exact

    country = ""
    c = prof.get("country") if isinstance(prof, dict) else None
    if isinstance(c, dict):
        country = str(c.get("acronym") or "")
    pid = id_via_country(api, exact, country, tour)
    return pid, exact


def all_players(api: Api, tour="atp", max_pages=40) -> dict[str, int]:
    """Mapa nazwa -> id. Nie polega na hasNextPage — idzie do pustej strony."""
    out, page, size = {}, 1, 200
    while page <= max_pages:
        d = api.get(f"/{tour}/player", pageSize=size, pageNo=page)
        if "_error" in d:
            print(f"  blad listy: {d['_error']} {d.get('_body','')}")
            break
        rows = d.get("data") if isinstance(d, dict) else d
        if not isinstance(rows, list) or not rows:
            break
        for p in rows:
            n, pid = p.get("name"), p.get("id")
            if n and pid:
                out[str(n)] = int(pid)
        if len(rows) < size:
            break
        page += 1
    return out


def games_from_score(result: str) -> tuple[int, int] | None:
    """
    "7-5 6-3" -> (13, 9) gemy player1/player2. Tiebreaki w nawiasach ignorujemy.
    Daje prawdziwa liczbe gemow zamiast szacunku svpt/6.4.
    """
    if not result:
        return None
    g1 = g2 = 0
    for setpart in str(result).split():
        m = re.match(r"(\d+)-(\d+)", setpart)
        if not m:
            continue
        g1 += int(m.group(1))
        g2 += int(m.group(2))
    return (g1, g2) if (g1 + g2) > 0 else None


def parse_matches(payload, player: str, pid: int | None = None) -> list[dict]:
    """
    Zamienia past-matches na wiersze w formacie TML (long).

    Struktura zwracana przez API:
      stats: { duration, player1: {...}, player2: {...} }
    gdzie kazdy obiekt zawiera aces, doubleFaults, firstServe, firstServeOf.
    firstServeOf = liczba punktow serwisowych (= winningOnFirstServeOf
    + winningOnSecondServeOf).
    """
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    out = []
    for m in rows:
        if not isinstance(m, dict):
            continue
        stats = m.get("stats") or m.get("stat") or {}
        if not isinstance(stats, dict):
            continue

        # ktorym zawodnikiem jest nasz gracz
        p1, p2 = m.get("player1") or {}, m.get("player2") or {}
        if pid is not None and m.get("player1Id") == pid:
            me, opp_obj, idx = "player1", p2, 0
        elif pid is not None and m.get("player2Id") == pid:
            me, opp_obj, idx = "player2", p1, 1
        elif str(p1.get("name", "")) == player:
            me, opp_obj, idx = "player1", p2, 0
        elif str(p2.get("name", "")) == player:
            me, opp_obj, idx = "player2", p1, 1
        else:
            continue

        mine = stats.get(me) or {}
        if not isinstance(mine, dict):
            continue
        ace = num(mine.get("aces"))
        dfs = num(mine.get("doubleFaults"))
        svpt = num(mine.get("firstServeOf"))
        if svpt in (None, 0):
            w1 = num(mine.get("winningOnFirstServeOf")) or 0
            w2 = num(mine.get("winningOnSecondServeOf")) or 0
            svpt = (w1 + w2) or None
        if ace is None or not svpt:
            continue

        # gemy serwisowe z wyniku meczu
        games = games_from_score(m.get("result", ""))
        svgms = games[idx] if games else max(round(svpt / 6.4), 1)

        tour_obj = m.get("tournament") or {}
        court = ""
        c = tour_obj.get("court")
        if isinstance(c, dict):
            court = str(c.get("name") or "")
        elif isinstance(c, str):
            court = c
        cl = court.lower()
        surface = ("Clay" if "clay" in cl else
                   "Grass" if "grass" in cl else "Hard")
        indoor = "I" if ("indoor" in cl or "i.hard" in cl or
                         cl.startswith("i.")) else "O"

        rank_name = ""
        r = tour_obj.get("rank")
        if isinstance(r, dict):
            rank_name = str(r.get("name") or "")
        best_of = m.get("best_of")
        if not best_of:
            best_of = 5 if "grand slam" in rank_name.lower() else 3

        date = str(m.get("date") or "")[:10].replace("-", "")
        if len(date) != 8:
            continue

        out.append({
            "player": player,
            "opp": str(opp_obj.get("name") or "?"),
            "surface": surface, "indoor": indoor,
            "tourney_date": int(date), "best_of": int(best_of),
            "ace": ace, "df": dfs if dfs is not None else 0.0,
            "svpt": svpt, "svgms": float(svgms),
            "tourney_name": str(tour_obj.get("name") or ""),
            "round": "",
            "score": str(m.get("result") or ""),
            "won": 1 if (pid is not None
                         and m.get("match_winner") == pid) else 0,
            "rank_name": rank_name,
        })
    return out


def inspect(api: Api, name: str, tour="atp"):
    print(f"\n=== Podglad danych dla: {name} ===\n")

    # 1) szukanie po nazwisku (1 zapytanie)
    pid, found = find_id(api, name, tour)
    if pid:
        print(f"search: {name} -> id {pid} ({found})")
    else:
        print(f"Nie udalo sie wyciagnac ID (nazwa rozpoznana jako: {found})")
        prof = api.get(f"/profile/{quote(found or name)}")
        print("\n--- surowa odpowiedz /profile (szukamy numerycznego id) ---")
        print(json.dumps(prof, ensure_ascii=False, indent=2)[:2500])
        print("\nWklej powyzsze w rozmowie — wskaze pole z ID.")
        return
    name = found or name
    print()

    d = api.get(f"/{tour}/player/past-matches/{pid}",
                include="tournament,tournament.court,tournament.rank,stat",
                pageSize=3, pageNo=1)
    rows = d.get("data") if isinstance(d, dict) else d
    if isinstance(rows, list) and rows:
        st = rows[0].get("stat") or rows[0].get("stats") or {}
        if isinstance(st, list) and st:
            st = st[0]
        if isinstance(st, dict):
            print("--- KLUCZE w obiekcie stat (najwazniejsze) ---")
            keys = sorted(st.keys())
            for k in keys:
                print(f"  {k} = {st[k]}")
            print()
        else:
            print("!! Brak obiektu stat w odpowiedzi — sprawdz include=stat\n")
    print("--- surowa odpowiedz (skrocona) ---")
    print(json.dumps(d, indent=2, ensure_ascii=False)[:3000])
    print("\n--- co udalo sie sparsowac ---")
    parsed = parse_matches(d, name, pid)
    if parsed:
        print(pd.DataFrame(parsed).to_string(index=False))
    else:
        print("NIC. Nazwy pol statystyk sa inne niz zakladane.")
        print("Wklej powyzszy JSON w rozmowie — dopasuje parser.")


def flush(new_rows: list[dict]) -> int:
    """Dopisuje zebrane mecze do matches_slim.csv. Zwraca liczbe nowych."""
    if not new_rows:
        return 0
    new = pd.DataFrame(new_rows)
    if "rank_name" in new.columns:
        low = new.rank_name.str.lower().fillna("")
        new = new[~low.str.contains("challenger|itf|futures|satellite")]
        new = new.drop(columns=["rank_name"])
    if new.empty:
        return 0
    path = DATA / "matches_slim.csv"
    old = pd.read_csv(path)
    # UWAGA: (player, opp, tourney_date) NIE jest unikalne — w TML
    # tourney_date to data rozpoczecia turnieju, wiec dwa spotkania tej samej
    # pary w jednym turnieju maja ten sam klucz. Dokladamy wynik i rundy,
    # inaczej deduplikacja skasowalaby prawdziwy mecz.
    key = [c for c in ["player", "opp", "tourney_date", "score", "round"]
           if c in old.columns and c in new.columns]
    # ile z pobranych meczow to faktycznie NOWE wiersze
    existing = set(map(tuple, old[key].astype(str).values))
    fresh = sum(1 for r in new[key].astype(str).values
                if tuple(r) not in existing)
    merged = (pd.concat([old, new], ignore_index=True)
              .drop_duplicates(subset=key, keep="last"))
    merged.to_csv(path, index=False)
    return fresh


def update(api: Api, top: int, years: list[int], tour="atp",
           active_days: int = 400):
    existing = pd.read_csv(DATA / "players.csv", index_col=0)

    # Odsiewamy zawodnikow, ktorzy dawno nie grali. Sortowanie po liczbie
    # meczow stawia wysoko emerytow (Nadal, Thiem, Schwartzman) — maja setki
    # wystepow w historii, ale nie zagraja juz nigdy, wiec kazde zapytanie
    # o nich to zmarnowana kwota.
    slim = pd.read_csv(DATA / "matches_slim.csv")
    last_seen = slim.groupby("player").tourney_date.max()
    cutoff = int((date.today() - timedelta(days=active_days)).strftime("%Y%m%d"))
    existing["last_match"] = last_seen
    active = existing[existing.last_match.fillna(0) >= cutoff]
    dropped = len(existing) - len(active)

    targets = list(active.sort_values("matches", ascending=False).index[:top])
    print(f"Pomijam {dropped} zawodnikow bez meczu od {cutoff} "
          f"(ostatnie {active_days} dni)")
    if dropped and len(existing) - len(active) < 40:
        skipped = existing[existing.last_match.fillna(0) < cutoff]
        print("  np.: " + ", ".join(list(skipped.index[:5])))
    print(f"Aktualizuje {len(targets)} zawodnikow\n")

    cache = load_cache()
    done_path = DATA / "updated.json"
    done = set(json.loads(done_path.read_text())) if done_path.exists() else set()
    if done:
        print(f"Wznawiam — {len(done)} zawodnikow juz zaktualizowanych "
              "(usun data/updated.json zeby zaczac od nowa)\n")
    targets = [t for t in targets if t not in done]

    new_rows, missing, added = [], [], 0
    try:
        for i, name in enumerate(targets, 1):
            if name in cache:
                pid = int(cache[name])
            else:
                pid, _ = find_id(api, name, tour)
                if pid:
                    cache[name] = pid
                    save_cache(cache)
            if not pid:
                missing.append(name)
                print(f"  [{i}/{len(targets)}] {name}: brak ID")
                continue
            # Bez filtra GameYear — endpoint zwraca najnowsze mecze pierwsze,
            # a filtrowanie po roku robimy lokalnie. Filtr serwerowy potrafil
            # zwracac pustke, a to i tak jedno zapytanie zamiast kilku.
            d = api.get(
                f"/{tour}/player/past-matches/{pid}",
                include="tournament,tournament.court,tournament.rank,stat",
                pageSize=100, pageNo=1)
            allm = parse_matches(d, name, pid)
            got = [m for m in allm if m["tourney_date"] // 10000 in years]
            if allm and not got:
                yrs = sorted({m["tourney_date"] // 10000 for m in allm})
                print(f"      (pobrano {len(allm)} meczow, ale z lat {yrs})")
            if not allm and DEBUG:
                print("      --- surowa odpowiedz (nic nie sparsowano) ---")
                print("      " + json.dumps(d, ensure_ascii=False)[:800])
            new_rows += got
            done.add(name)
            print(f"  [{i}/{len(targets)}] {name}: +{len(got)} meczow "
                  f"({api.calls} zapytan)")

            # CHECKPOINT co 10 zawodnikow — kwota moze skonczyc sie w kazdej chwili
            if i % 10 == 0:
                added += flush(new_rows)
                new_rows = []
                done_path.write_text(json.dumps(sorted(done)))
                print(f"    [zapisano; lacznie +{added} meczow]")

    except QuotaExhausted as e:
        print(f"\n!! KWOTA WYCZERPANA: {str(e)[:120]}")
        print("   Zapisuje to, co zdazylem pobrac...")
    except KeyboardInterrupt:
        print("\nPrzerwano — zapisuje...")

    added += flush(new_rows)
    done_path.write_text(json.dumps(sorted(done)))

    if missing:
        print(f"\nBez ID: {len(missing)} zawodnikow, np. {missing[:5]}")

    if not added:
        print("\nZero nowych meczow zapisanych.")
        return

    merged = pd.read_csv(DATA / "matches_slim.csv")
    print(f"\nDopisano {added} meczow. Razem: {len(merged)} wierszy")
    print(f"Najnowszy mecz: {int(merged.tourney_date.max())}")
    print(f"Zuzyto {api.calls} zapytan. Zaktualizowano {len(done)} zawodnikow.")
    print("\nTeraz przelicz baze:  python rebuild_from_slim.py")
    print("Kolejny przebieg pominie juz zrobionych (data/updated.json).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", metavar="NAME")
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--years", default="2026")
    ap.add_argument("--active-days", type=int, default=400,
                    help="pomin zawodnikow bez meczu od tylu dni "
                         "(domyslnie 400 — odsiewa emerytow)")
    ap.add_argument("--debug", action="store_true",
                    help="pokaz surowa odpowiedz gdy nic nie sparsowano")
    args = ap.parse_args()
    DEBUG = args.debug

    key = get_key()
    if not key:
        sys.exit("Brak klucza. Utworz api_key.txt z linia RAPID_KEY=...")
    api = Api(key)

    globals()["DEBUG"] = args.debug
    if args.inspect:
        inspect(api, args.inspect)
    else:
        update(api, args.top, [int(y) for y in args.years.split(",")],
               active_days=args.active_days)
