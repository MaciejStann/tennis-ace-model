"""
Model punktowy: od prawdopodobienstwa punktu do wyniku meczu.

Z p_serve obu zawodnikow liczymy analitycznie prawdopodobienstwo gema,
tie-breaka, seta i meczu. Z jednego rachunku wypada wszystko naraz:
zwyciezca, wynik w setach, szansa na tie-break, rozklad liczby gemow.

Zalozenie: punkty sa niezalezne. To przyblizenie — punkty wazne rozgrywane
sa inaczej — ale standardowe i wystarczajace.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

# Sciaganie do sredniej tourowej, w punktach serwisowych.
# Mediana zawodnika to ~7750 pkt, wiec K=2000 to umiarkowana korekta.
SHRINK_PTS = 2000.0
SHRINK_SURF = 1000.0

# --- kalibracja, dobrana out-of-sample (validate_point.py) ---
# Model punktowy jest ZBYT PEWNY: zaklada niezaleznosc punktow, a w
# rzeczywistosci slabszy zawodnik czesciej "kradnie" seta. Skalowanie
# logitu ponizej 1 sciaga prognozy do srodka.
#   bez korekty  log loss 0.6579
#   ze skalowaniem 0.75: 0.6542  (+0.56%)
PROB_SCALE = 0.75

# Model przeszacowuje dlugosc meczu (28.2 vs 25.3 gema w danych), bo nie
# uwzglednia krotszych meczow konczonych przewaga jednej strony.
#   MAE przed korekta 6.43 gema, po: 5.60
GAMES_SCALE = 0.90


# --------------------------------------------------------- gem

@lru_cache(maxsize=4096)
def game_prob(p: float) -> float:
    """Prawdopodobienstwo wygrania gema przy p na punkt (z deuce)."""
    p = min(max(p, 0.01), 0.99)
    q = 1 - p
    # wygrana do 0, 15, 30
    out = p**4 + 4 * p**4 * q + 10 * p**4 * q**2
    # deuce: 20 * p^3 q^3, potem p^2/(p^2+q^2)
    deuce = 20 * p**3 * q**3
    out += deuce * p**2 / (p**2 + q**2)
    return out


@lru_cache(maxsize=4096)
def tiebreak_prob(ps: float, pr: float) -> float:
    """
    Prawdopodobienstwo wygrania tie-breaka do 7 (przewaga 2).

    ps — punkt przy wlasnym serwisie, pr — przy returnie.
    Kolejnosc serwisu: pierwszy punkt serwuje gracz A, potem po dwa na
    zmiane. Numer punktu n (liczac od 0) serwuje A wtedy, gdy
    ((n + 1) // 2) jest parzyste.
    """
    ps = min(max(ps, 0.01), 0.99)
    pr = min(max(pr, 0.01), 0.99)

    memo: dict[tuple[int, int], float] = {}

    def f(a: int, b: int) -> float:
        if a >= 7 and a - b >= 2:
            return 1.0
        if b >= 7 and b - a >= 2:
            return 0.0
        if a >= 6 and b >= 6:
            # po 6:6 sekwencja jest cykliczna — wzor zamkniety na
            # "wygrac 2 punkty z rzedu przy naprzemiennym serwisie"
            if (a, b) in memo:
                return memo[(a, b)]
            if a == b:
                # nastepne dwa punkty: jeden swoj serwis, jeden returnowy
                pa = ps * pr                       # oba wygrane
                pb = (1 - ps) * (1 - pr)           # oba przegrane
                memo[(a, b)] = pa / (pa + pb) if (pa + pb) > 0 else 0.5
            else:
                memo[(a, b)] = 1.0 if a > b else 0.0
            return memo[(a, b)]
        key = (a, b)
        if key in memo:
            return memo[key]
        n = a + b
        serves_a = ((n + 1) // 2) % 2 == 0
        p = ps if serves_a else pr
        memo[key] = p * f(a + 1, b) + (1 - p) * f(a, b + 1)
        return memo[key]

    return f(0, 0)


# --------------------------------------------------------- set

def set_distribution(g_serve: float, g_break: float,
                     tb: float) -> dict[tuple[int, int], float]:
    """
    Rozklad wyniku seta przy naprzemiennym serwisie.

    g_serve — szansa utrzymania wlasnego podania,
    g_break — szansa przelamania przeciwnika,
    tb — szansa wygrania tie-breaka.

    Zwraca slownik {(gemy_A, gemy_B): prawdopodobienstwo}, sumujacy sie do 1.
    """
    dist: dict[tuple[int, int], float] = {}
    # stan: (gemy A, gemy B, kto serwuje), prawdopodobienstwo
    stack = [(0, 0, 1, 1.0)]
    while stack:
        a, b, srv, prob = stack.pop()
        if prob < 1e-12:
            continue
        if a >= 6 and a - b >= 2:
            dist[(a, b)] = dist.get((a, b), 0.0) + prob
            continue
        if b >= 6 and b - a >= 2:
            dist[(a, b)] = dist.get((a, b), 0.0) + prob
            continue
        if a == 6 and b == 6:
            dist[(7, 6)] = dist.get((7, 6), 0.0) + prob * tb
            dist[(6, 7)] = dist.get((6, 7), 0.0) + prob * (1 - tb)
            continue
        p = g_serve if srv else g_break     # szansa, ze gem bierze A
        stack.append((a + 1, b, 1 - srv, prob * p))
        stack.append((a, b + 1, 1 - srv, prob * (1 - p)))
    return dist


# --------------------------------------------------------- mecz

def match_outcome(p1_serve: float, p2_serve: float,
                  best_of: int = 3) -> dict:
    """
    Pelny rozklad wyniku meczu.

    p1_serve / p2_serve — prawdopodobienstwo wygrania punktu przy wlasnym
    serwisie. Zwraca prawdopodobienstwo wygranej, rozklad setow, szanse
    tie-breaka i oczekiwana liczbe gemow.
    """
    g1 = game_prob(p1_serve)              # p1 utrzymuje podanie
    g2 = game_prob(p2_serve)              # p2 utrzymuje podanie
    tb1 = tiebreak_prob(p1_serve, 1 - p2_serve)

    sd = set_distribution(g1, 1 - g2, tb1)
    p_set = sum(v for (a, b), v in sd.items() if a > b)
    exp_games_set = sum((a + b) * v for (a, b), v in sd.items())
    p_tb_set = sum(v for (a, b), v in sd.items() if {a, b} == {6, 7})

    need = 2 if best_of == 3 else 3
    # rozklad wynikow setowych
    sets = {}
    def rec(w, l, prob):
        if w == need:
            sets[(w, l)] = sets.get((w, l), 0) + prob
            return
        if l == need:
            sets[(w, l)] = sets.get((w, l), 0) + prob
            return
        rec(w + 1, l, prob * p_set)
        rec(w, l + 1, prob * (1 - p_set))
    rec(0, 0, 1.0)

    p_match = sum(v for (w, l), v in sets.items() if w == need)
    exp_sets = sum((w + l) * v for (w, l), v in sets.items())

    # kalibracja: sciagniecie do srodka na skali logitowej
    lo = np.log(min(max(p_match, 1e-9), 1 - 1e-9)
                / (1 - min(max(p_match, 1e-9), 1 - 1e-9)))
    p_cal = 1 / (1 + np.exp(-lo * PROB_SCALE))

    return {
        "p_win": float(p_cal),
        "p_win_raw": p_match,
        "p_set": p_set,
        "sets": dict(sorted(sets.items(), key=lambda kv: -kv[1])),
        "exp_sets": exp_sets,
        "exp_games": exp_games_set * exp_sets * GAMES_SCALE,
        "p_tiebreak_set": p_tb_set,
        "p_any_tiebreak": 1 - (1 - p_tb_set) ** exp_sets,
        "hold1": g1, "hold2": g2,
    }


# --------------------------------------------------------- stawki graczy

def build_serve_rates(matches: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """p_serve i p_return kazdego zawodnika, z podzialem na nawierzchnie."""
    d = matches.dropna(subset=["sv_1won", "sv_2won", "svpt"])
    d = d[d.svpt > 0].copy()
    d["won_pts"] = d.sv_1won + d.sv_2won
    tour = d.won_pts.sum() / d.svpt.sum()

    surf_mult = {}
    for s, g in d.groupby("surface"):
        surf_mult[s] = float((g.won_pts.sum() / g.svpt.sum()) / tour)

    srv = d.groupby("player").agg(w=("won_pts", "sum"), v=("svpt", "sum"),
                                  n=("svpt", "size"))
    srv["p_serve"] = (srv.w + SHRINK_PTS * tour) / (srv.v + SHRINK_PTS)

    # return: ile punktow oddaje przeciwnikom przy ICH serwisie
    ret = d.groupby("opp").agg(w=("won_pts", "sum"), v=("svpt", "sum"),
                               n=("svpt", "size"))
    ret["p_conceded"] = (ret.w + SHRINK_PTS * tour) / (ret.v + SHRINK_PTS)
    ret.index.name = "player"

    out = srv[["n", "p_serve"]].join(ret[["p_conceded"]], how="outer")

    for s in ("Hard", "Clay", "Grass"):
        sub = d[d.surface == s].groupby("player").agg(
            w=("won_pts", "sum"), v=("svpt", "sum"))
        prior = tour * surf_mult.get(s, 1.0)
        out[f"p_serve_{s.lower()}"] = ((sub.w + SHRINK_SURF * prior)
                                       / (sub.v + SHRINK_SURF))
        sub2 = d[d.surface == s].groupby("opp").agg(
            w=("won_pts", "sum"), v=("svpt", "sum"))
        out[f"p_conc_{s.lower()}"] = ((sub2.w + SHRINK_SURF * prior)
                                      / (sub2.v + SHRINK_SURF))

    meta = {"tour_p_serve": float(tour), "surf_mult": surf_mult}
    return out, meta


def effective_p_serve(rates: pd.DataFrame, meta: dict, server: str,
                      returner: str, surface: str) -> float | None:
    """
    Korekta ADDYTYWNA, nie multiplikatywna.

    Przy p_serve ~0,64 mnoznik 1,2 dalby 0,77 i przy mocnym serwisie wynik
    uciekalby poza sensowny zakres. Uzywamy schematu Barnetta-Clarke'a:
        p_eff = p_serve(A) + p_oddane(B) - srednia_tourowa
    """
    if server not in rates.index or returner not in rates.index:
        return None
    s = surface.lower()
    ps = rates.loc[server, f"p_serve_{s}"]
    if pd.isna(ps):
        ps = rates.loc[server, "p_serve"] * meta["surf_mult"].get(surface, 1.0)
    pc = rates.loc[returner, f"p_conc_{s}"]
    if pd.isna(pc):
        pc = rates.loc[returner, "p_conceded"]
    if pd.isna(ps) or pd.isna(pc):
        return None
    tour = meta["tour_p_serve"] * meta["surf_mult"].get(surface, 1.0)
    return float(min(max(ps + pc - tour, 0.35), 0.90))
