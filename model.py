"""Rdzen modelu: estymacja asow i DF, H2H, dopasowanie nazwisk z terminarza."""
from __future__ import annotations


import json
import pathlib
import re
import unicodedata

import numpy as np
import pandas as pd
from scipy import stats

DATA = pathlib.Path(__file__).parent / "data"


def current_ranks(players) -> dict:
    """Ostatni znany ranking kazdego zawodnika (z bazy meczow)."""
    return {}


def load_point_rates(matches):
    """Stawki punktowe do modelu meczu. None, gdy brak kolumn serwisowych."""
    if matches is None or "sv_1won" not in matches.columns:
        return None, None
    try:
        import pointmodel as PM
        return PM.build_serve_rates(matches)
    except Exception:
        return None, None


def load():
    players = pd.read_csv(DATA / "players.csv", index_col=0)
    meta = json.loads((DATA / "meta.json").read_text())
    calib_path = DATA / "calib.json"
    calib = {}
    if calib_path.exists():
        try:
            calib = json.loads(calib_path.read_text())
        except ValueError:
            calib = {}
    # domyslne, gdy calibrate.py nie byl jeszcze uruchomiony
    calib.setdefault("calib_c", 1.0)
    calib.setdefault("calib_c_df", 1.0)
    calib.setdefault("nb_r", 26.0)
    calib.setdefault("form", {})
    matches_path = DATA / "matches_slim.csv"
    matches = pd.read_csv(matches_path) if matches_path.exists() else None
    return players, meta, calib, matches


# --------------------------------------------------------- nazwiska

def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().replace(".", " ").replace("-", " ").split())


def match_name(query: str, index: list[str], cache: dict) -> tuple[str | None, float]:
    """
    Dopasowuje nazwe z terminarza do bazy. Zwraca (nazwa, pewnosc 0-1).

    Zasady (kolejnosc ma znaczenie):
      1. Dokladne trafienie po normalizacji -> 1.0
      2. Kazdy znaczacy czlon zapytania musi wystepowac w nazwie kandydata.
         To blokuje "Taylor Townsend" -> "Taylor Fritz" (brak 'townsend').
      3. Zapytanie jednoczlonowe musi trafic w NAZWISKO (ostatni czlon),
         nigdy w imie. "Taylor" nie moze dac "Taylor Fritz".
      4. Niejednoznacznosc rozstrzygamy inicjalem ("Zverev A.").
      5. Zadnego dopasowania rozmytego — lepiej brak wyniku niz zly wynik.
    """
    if not cache:
        for n in index:
            cache[norm(n)] = n
    q = norm(query)
    if not q:
        return None, 0.0
    if q in cache:
        return cache[q], 1.0

    tokens = q.split()
    words = [t for t in tokens if len(t) > 1]        # znaczace czlony
    initials = {t[0] for t in tokens if len(t) <= 2}  # "B." -> {'b'}
    if not words:
        return None, 0.0

    hits: list[tuple[str, float]] = []
    for key, orig in cache.items():
        cand = key.split()
        if not cand:
            continue
        # (2) wszystkie znaczace czlony zapytania musza byc w kandydacie
        if not all(w in cand for w in words):
            # Niektore zrodla podaja pelne nazwisko z drugim czlonem
            # ("Alcaraz Garfia Carlos" = Carlos Alcaraz). Dopuszczamy
            # nadmiarowe czlony, o ile imie i pierwszy czlon nazwiska
            # sie zgadzaja i trafienie jest jednoznaczne.
            wspolne = [w for w in words if w in cand]
            if len(cand) >= 2 and len(wspolne) >= len(cand):
                hits.append((orig, 0.80))
            continue
        # (3) jeden czlon -> musi byc nazwiskiem kandydata
        if len(words) == 1 and words[0] != cand[-1]:
            continue
        # pelne pokrycie w obie strony = bardzo pewne
        score = 0.95 if len(words) >= len(cand) else 0.88
        hits.append((orig, score))

    if len(hits) == 1:
        return hits[0]
    if hits:
        strong = [h for h in hits if h[1] >= 0.95]
        if len(strong) == 1:
            return strong[0]
        # (4) rozstrzygniecie inicjalem imienia
        if initials:
            narrowed = [h for h in hits if norm(h[0]).split()[0][0] in initials]
            if len(narrowed) == 1:
                return narrowed[0][0], 0.85
    return None, 0.0


# --------------------------------------------------------- estymacja

def _int0(v) -> int:
    """NaN/None -> 0. Wielu zawodnikow nie ma ani jednego meczu na danej
    nawierzchni (55% nie gralo na trawie), wiec int(NaN) wywalalby aplikacje."""
    try:
        if v is None or pd.isna(v):
            return 0
        return int(v)
    except (TypeError, ValueError):
        return 0


def player_rates(players, meta, name: str, surface: str) -> dict:
    """Zwraca stawki zawodnika albo known=False bez zadnych liczb.

    Swiadomie NIE podstawiamy sredniej tourowej dla nieznanego zawodnika —
    to nie jest estymacja, tylko liczba udajaca estymacje. Brak danych
    ma wygladac jak brak danych.
    """
    if name not in players.index:
        return {"ace": None, "df": None, "n": 0, "n_surf": 0, "known": False,
                "ace_overall": None, "df_overall": None}
    row = players.loc[name]
    ace = row.get(f"ace_{surface.lower()}", np.nan)
    if pd.isna(ace):
        ace = row["ace_pct"] * meta["surface_mult"].get(surface, 1.0)
    return {
        "ace": float(ace), "df": float(row["df_pct"]),
        "n": int(row["matches"]),
        "n_surf": _int0(row.get(f"n_{surface.lower()}")),
        "known": True,
        "ace_overall": float(row["ace_pct"]),
        "df_overall": float(row["df_pct"]),
    }


def return_mult(players, name: str) -> tuple[float, int]:
    """Mnoznik returnera; 1.0 tylko jako neutralny brak korekty (nie estymacja)."""
    if name not in players.index:
        return 1.0, 0
    row = players.loc[name]
    rm = row.get("ret_mult", np.nan)
    if pd.isna(rm):
        return 1.0, 0
    return float(rm), int(row.get("ret_matches", 0) or 0)


SHRINK = 400.0


def recent_rate(matches, name: str, metric: str, n: int,
                prior: float) -> tuple[float | None, int, int | None]:
    """
    Stawka z ostatnich n meczow (bez podzialu na nawierzchnie — okno jest
    male, wiec dzielenie go dalej daje sam szum). Zwraca (stawka, liczba
    meczow, data najstarszego z okna).
    """
    if matches is None:
        return None, 0, None
    sub = matches[matches.player == name]
    if sub.empty:
        return None, 0, None
    sub = sub.sort_values("tourney_date").tail(n)
    made, att = sub[metric].sum(), sub.svpt.sum()
    if att <= 0:
        return None, 0, None
    rate = (made + SHRINK * prior) / (att + SHRINK)
    return float(rate), len(sub), int(sub.tourney_date.min())


def form_cfg(calib: dict, metric: str) -> dict | None:
    """Konfiguracja formy — obecna tylko jesli walidacja ja potwierdzila."""
    return (calib.get("form") or {}).get(metric)


def estimate(players, meta, calib, server: str, returner: str,
             surface: str, indoor: bool, svpt: float,
             matches=None) -> dict:
    s = player_rates(players, meta, server, surface)
    rm, rn = return_mult(players, returner)
    ind = meta["indoor_mult"] if indoor else 1.0
    if not s["known"]:
        # brak danych o serwujacym -> brak estymacji, kropka
        return {"mu_ace": None, "mu_df": None, "ret_mult": rm, "ret_n": rn,
                "indoor_mult": ind, "svpt": svpt, "ret_known": rn > 0, **s}
    ace_rate, df_rate = s["ace"], s["df"]
    form_info = {}

    for metric, base in (("ace", "ace"), ("df", "df")):
        cfg = form_cfg(calib, metric)
        if not cfg or matches is None:
            continue
        w, n = float(cfg["weight"]), int(cfg["window"])
        prior = meta["tour_ace_pct"] if metric == "ace" else meta["tour_df_pct"]
        rate, cnt, since = recent_rate(matches, server, metric, n, prior)
        if rate is None or cnt < max(3, n // 3):
            continue
        blended = w * rate + (1 - w) * (ace_rate if metric == "ace" else df_rate)
        if metric == "ace":
            ace_rate = blended
        else:
            df_rate = blended
        form_info[metric] = {"rate": rate, "n": cnt, "since": since,
                             "weight": w, "window": n}

    return {
        "ret_known": rn > 0,
        "mu_ace": ace_rate * rm * ind * svpt * calib["calib_c"],
        # DF zalezy od serwujacego, nie od returnera — returner nie wplywa
        # na to, czy przeciwnik wrzuci druga podanie w siatke.
        "mu_df": df_rate * svpt * calib.get("calib_c_df", 1.0),
        "ret_mult": rm, "ret_n": rn, "indoor_mult": ind, "svpt": svpt,
        "form": form_info, **s,
    }


# --------------------------------------------------------- rozklady

def nb(mu: float, r: float):
    mu = max(float(mu), 0.01)
    return r, r / (r + mu)


def p_over(line: float, mu: float, r: float) -> float:
    rr, p = nb(mu, r)
    return float(1 - stats.nbinom.cdf(np.floor(line), rr, p))


MAX_STAKE_FRACTION = 0.10   # nigdy wiecej niz 10% bankrolla na zaklad


def kelly(prob: float, odds: float, fraction: float) -> float:
    """
    Ulamkowy Kelly z twardym sufitem.

    Model nigdy nie jest pewny — p_over dla skrajnie niskich linii zwraca
    ~0.9999, co bez sufitu daje stawke rowna calemu ulamkowi bankrolla przy
    zerowej faktycznej przewadze. Sufit chroni przed bledem modelu, nie
    przed matematyka Kelly'ego.
    """
    if odds <= 1.0:
        return 0.0
    prob = min(max(float(prob), 0.0), 0.999)
    edge = prob * odds - 1
    if edge <= 0:
        return 0.0
    return min(fraction * edge / (odds - 1), MAX_STAKE_FRACTION)


# --------------------------------------------------------- H2H

def h2h(matches: pd.DataFrame | None, p1: str, p2: str) -> pd.DataFrame:
    if matches is None:
        return pd.DataFrame()
    sub = matches[((matches.player == p1) & (matches.opp == p2))
                  | ((matches.player == p2) & (matches.opp == p1))]
    if sub.empty:
        return sub
    return sub.sort_values("tourney_date", ascending=False)


def h2h_list(matches, p1: str, p2: str) -> list[dict]:
    """
    Lista spotkan, najnowsze pierwsze. Kazdy element to jeden mecz
    z danymi obu zawodnikow.

    Uwaga: w danych TML `tourney_date` to data ROZPOCZECIA turnieju, wiec
    dwa spotkania tej samej pary moga miec identyczna date — parujemy po
    (data, kolejnosc), zeby zadnego nie zgubic.
    """
    sub = h2h(matches, p1, p2)
    if sub.empty:
        return []

    a = sub[sub.player == p1].sort_values("tourney_date").copy()
    b = sub[sub.player == p2].sort_values("tourney_date").copy()
    a["k"] = a.groupby("tourney_date").cumcount()
    b["k"] = b.groupby("tourney_date").cumcount()
    a, b = a.set_index(["tourney_date", "k"]), b.set_index(["tourney_date", "k"])

    out = []
    for key in sorted(set(a.index) | set(b.index), reverse=True):
        ra = a.loc[key] if key in a.index else None
        rb = b.loc[key] if key in b.index else None
        src = ra if ra is not None else rb
        d = str(int(key[0]))
        def field(col):
            v = src.get(col, "") if hasattr(src, "get") else ""
            return "" if (v is None or (isinstance(v, float) and pd.isna(v))) \
                else str(v)

        entry = {
            "date": int(key[0]),
            "date_str": f"{d[6:]}.{d[4:6]}.{d[:4]}",
            "surface": str(src.surface),
            "indoor": str(src.indoor).upper().startswith("I"),
            "tournament": field("tourney_name"),
            "round": field("round"),
            "score": field("score"),
            "stats": {},
        }
        for name, r in ((p1, ra), (p2, rb)):
            if r is None:
                entry["stats"][name] = None
                continue
            svpt = float(r.svpt) or 1.0
            won = r.get("won", -1) if hasattr(r, "get") else -1
            entry["stats"][name] = {
                "ace": float(r.ace), "df": float(r["df"]),
                "svpt": svpt, "svgms": float(r.svgms),
                "ace_pct": 100 * float(r.ace) / svpt,
                "df_pct": 100 * float(r["df"]) / svpt,
                "won": None if won in (-1, "") or pd.isna(won) else bool(int(won)),
            }
        out.append(entry)
    return out


def flip_score(score: str) -> str:
    """
    Odwraca wynik: "6-3 7-6(2)" -> "3-6 6-7(2)".

    W danych wynik jest zawsze zapisany z perspektywy ZWYCIEZCY, wiec gdy
    wyswietlamy go przy zawodniku, ktory przegral, trzeba go odwrocic —
    inaczej sugeruje, ze to on wygral sety.
    """
    if not score:
        return score
    out = []
    for part in str(score).split():
        m = re.match(r"^(\d+)-(\d+)(\(\d+\))?$", part)
        if m:
            a, b, tb = m.group(1), m.group(2), m.group(3) or ""
            out.append(f"{b}-{a}{tb}")
        else:
            out.append(part)          # RET, W/O, itp. zostawiamy
    return " ".join(out)


def career_rate(matches, name: str, metric: str,
                surface: str | None = None) -> float | None:
    """Srednia zawodnika (na mecz) — punkt odniesienia dla pojedynczego meczu."""
    if matches is None:
        return None
    sub = matches[matches.player == name]
    if surface:
        sub = sub[sub.surface == surface]
    if len(sub) < 5:
        return None
    return float(sub[metric].mean())


def h2h_totals(matches, p1: str, p2: str) -> tuple[pd.DataFrame, int]:
    """Zbiorcze porownanie ze WSZYSTKICH wzajemnych meczow."""
    sub = h2h(matches, p1, p2)
    if sub.empty:
        return pd.DataFrame(), 0
    stats = {}
    for name in (p1, p2):
        g = sub[sub.player == name]
        if g.empty or g.svpt.sum() == 0:
            return pd.DataFrame(), 0
        stats[name] = {
            "Asy / mecz": g.ace.mean(),
            "ace%": 100 * g.ace.sum() / g.svpt.sum(),
            "DF / mecz": g["df"].mean(),
            "df%": 100 * g["df"].sum() / g.svpt.sum(),
        }
    n = int(max(len(sub[sub.player == p1]), len(sub[sub.player == p2])))
    f = pd.DataFrame(stats).round(2)
    f.index.name = "Metryka"
    return f.reset_index(), n


def last_results(matches, name: str, metric: str, n: int = 10,
                 surface: str | None = None) -> list[dict]:
    """
    Ostatnie n wystepow zawodnika z surowa wartoscia metryki.
    Sluzy do pokazania, jak czesto przekraczal zadana linie — element
    OPISOWY. Model tego nie uzywa: sprawdzono, ze serie pokryc nie
    przewiduja kolejnego meczu (efekt znika po kontroli na zawodnika).
    """
    if matches is None:
        return []
    sub = matches[matches.player == name]
    if surface:
        sub = sub[sub.surface == surface]
    if sub.empty:
        return []
    sub = sub.sort_values("tourney_date").tail(n)
    out = []
    for r in sub.itertuples():
        d = str(int(r.tourney_date))
        out.append({
            "date": int(r.tourney_date),
            "date_str": f"{d[6:]}.{d[4:6]}.{d[:4]}",
            "opp": str(r.opp),
            "surface": str(r.surface),
            "value": float(getattr(r, metric)),
            "svgms": float(r.svgms),
        })
    return list(reversed(out))


def total_games_history(matches, p1: str, p2: str, n: int = 10) -> list[dict]:
    """
    Laczna liczba gemow w ostatnich meczach obu zawodnikow (osobno).
    W formacie long gemy jednego zawodnika to polowa meczu, wiec laczna
    liczba wymaga sparowania z przeciwnikiem — robimy to po dacie i parze.
    """
    if matches is None:
        return []
    out = []
    for name in (p1, p2):
        sub = matches[matches.player == name].sort_values("tourney_date").tail(n)
        for r in sub.itertuples():
            opp_rows = matches[(matches.player == r.opp)
                               & (matches.opp == name)
                               & (matches.tourney_date == r.tourney_date)]
            if opp_rows.empty:
                continue
            d = str(int(r.tourney_date))
            out.append({
                "player": name, "opp": str(r.opp),
                "date": int(r.tourney_date),
                "date_str": f"{d[6:]}.{d[4:6]}.{d[:4]}",
                "total": float(r.svgms) + float(opp_rows.iloc[0].svgms),
            })
    return sorted(out, key=lambda x: x["date"], reverse=True)


def recent_form(matches, name: str, n: int = 10,
                surface: str | None = None) -> pd.DataFrame:
    if matches is None:
        return pd.DataFrame()
    sub = matches[matches.player == name]
    if surface:
        sub = sub[sub.surface == surface]
    return sub.sort_values("tourney_date", ascending=False).head(n)
