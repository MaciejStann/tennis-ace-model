"""
Porownuje wartosci K na TWOICH danych. Uruchom:  python compare_k.py

Sprawdza, czy K=800 jest lepsze od 400 na aktualnej bazie — MAE i kalibracja
prawdopodobienstw (log loss przy linii floor(mu)+0.5, czyli takiej, jaka
ustawilby bukmacher).
"""
import numpy as np
import pandas as pd
from scipy import optimize, stats

import build_db
from build_db import DATA

LINES = [2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 11.5, 13.5, 15.5]


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()


def ocen(K, train, test):
    build_db.SHRINK_SVPT = K
    P, M = build_db.build(train)
    D, sm, im = P.to_dict("index"), M["surface_mult"], M["indoor_mult"]

    def mu(r):
        p, o = D.get(r.player), D.get(r.opp)
        if p is None or np.isnan(p.get("ace_pct", np.nan)):
            return np.nan
        b = p.get(f"ace_{str(r.surface).lower()}")
        if b is None or np.isnan(b):
            b = p["ace_pct"] * sm.get(r.surface, 1.0)
        rm = o["ret_mult"] if o and not np.isnan(o.get("ret_mult", np.nan)) else 1.0
        return b * rm * (im if str(r.indoor).upper().startswith("I") else 1.0) * r.svpt

    t = test.copy()
    t["mu"] = t.apply(mu, axis=1)
    t = t.dropna(subset=["mu"])
    t["mu"] *= t.ace.sum() / t.mu.sum()          # kalibracja biasu

    def cal_err(r):
        return sum(((t.ace > L).mean()
                    - (1 - stats.nbinom.cdf(np.floor(L), r, r / (r + t.mu))).mean()) ** 2
                   for L in LINES)

    r = float(optimize.minimize_scalar(cal_err, bounds=(2, 80),
                                       method="bounded").x)
    line = np.floor(t.mu) + 0.5
    hit = (t.ace > line).astype(int)
    p = np.array([1 - stats.nbinom.cdf(np.floor(L), r, r / (r + m))
                  for L, m in zip(line, t.mu)])
    return {"MAE": (t.mu - t.ace).abs().mean(), "logloss": ll(p, hit),
            "nb_r": r, "n": len(t)}


if __name__ == "__main__":
    d = pd.read_csv(DATA / "matches_slim.csv")
    d["year"] = d.tourney_date // 10000
    split = d.year.max() - 1 if d.year.max() > d.year.min() + 2 else d.year.max()
    train, test = d[d.year < split], d[d.year >= split]
    print(f"trening: {len(train)} wystepow (do {split - 1})")
    print(f"test:    {len(test)} wystepow (od {split})\n")

    print(f"{'K':>6} {'MAE':>8} {'log loss':>10} {'nb_r':>7}")
    wyniki = {}
    for K in (200, 400, 800, 1600):
        w = ocen(K, train, test)
        wyniki[K] = w
        print(f"{K:>6} {w['MAE']:>8.3f} {w['logloss']:>10.4f} {w['nb_r']:>7.2f}")

    best_mae = min(wyniki, key=lambda k: wyniki[k]["MAE"])
    best_ll = min(wyniki, key=lambda k: wyniki[k]["logloss"])
    print(f"\nnajlepsze dla MAE:      K={best_mae}")
    print(f"najlepsze dla kalibracji: K={best_ll}")
    if best_ll != best_mae:
        d_mae = 100 * (wyniki[best_ll]["MAE"] - wyniki[best_mae]["MAE"]) / wyniki[best_mae]["MAE"]
        print(f"\nK={best_ll} pogarsza MAE o {d_mae:+.2f}% wzgledem K={best_mae}.")
        print("Jesli to wiecej niz 2% — zostan przy K optymalnym dla MAE.")
    build_db.SHRINK_SVPT = 800.0
