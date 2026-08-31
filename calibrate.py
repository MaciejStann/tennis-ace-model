"""
Kalibracja rozkladu: mnoznik biasu (c) i dyspersja rozkladu ujemnego
dwumianowego (r). Zapisuje wynik do data/calib.json.

    python calibrate.py

Uruchom po kazdej wiekszej aktualizacji bazy. Skrypt NIE nadpisuje innych
kluczy w calib.json (np. konfiguracji formy z oos_check.py).
"""
import json

import numpy as np
import pandas as pd
from scipy import optimize, stats

from build_db import DATA, build

SPLIT_YEAR = 2025
LINES = [2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 11.5, 13.5, 15.5]


def main():
    long = pd.read_csv(DATA / "matches_slim.csv")
    long["year"] = long.tourney_date // 10000
    train, test = long[long.year < SPLIT_YEAR], long[long.year >= SPLIT_YEAR]
    players, meta = build(train)
    D, sm = players.to_dict("index"), meta["surface_mult"]
    im = meta["indoor_mult"]

    def mu(row):
        p, o = D.get(row.player), D.get(row.opp)
        if p is None or np.isnan(p.get("ace_pct", np.nan)):
            return np.nan
        b = p.get(f"ace_{str(row.surface).lower()}")
        if b is None or np.isnan(b):
            b = p["ace_pct"] * sm.get(row.surface, 1.0)
        rm = o["ret_mult"] if o and not np.isnan(o.get("ret_mult", np.nan)) else 1.0
        i = im if str(row.indoor).upper().startswith("I") else 1.0
        return b * rm * i * row.svpt

    t = test.copy()
    t["pred"] = t.apply(mu, axis=1)
    t = t.dropna(subset=["pred"])
    print(f"Proba testowa: {len(t)} wystepow (od {SPLIT_YEAR})")

    c = t.ace.sum() / t.pred.sum()
    t["mu"] = t.pred * c
    print(f"Mnoznik kalibracyjny c = {c:.4f}")

    def cal_err(r):
        e = 0.0
        for L in LINES:
            act = (t.ace > L).mean()
            p = r / (r + t.mu)
            prd = (1 - stats.nbinom.cdf(np.floor(L), r, p)).mean()
            e += (act - prd) ** 2
        return e

    r = float(optimize.minimize_scalar(cal_err, bounds=(2, 80),
                                       method="bounded").x)
    pois = sum(((t.ace > L).mean()
                - (1 - stats.poisson.cdf(np.floor(L), t.mu)).mean()) ** 2
               for L in LINES)
    print(f"Dyspersja NB r = {r:.2f}  "
          f"(blad kalibracji {cal_err(r):.5f} vs Poisson {pois:.5f})")

    print(f"\n{'linia':>6} {'fakt':>7} {'NB':>7} {'Poisson':>8}")
    for L in LINES:
        act = (t.ace > L).mean()
        p = r / (r + t.mu)
        nb = (1 - stats.nbinom.cdf(np.floor(L), r, p)).mean()
        po = (1 - stats.poisson.cdf(np.floor(L), t.mu)).mean()
        print(f"{L:>6} {act:>7.3f} {nb:>7.3f} {po:>8.3f}")

    err = t.mu - t.ace
    print(f"\nMAE {err.abs().mean():.3f}  bias {err.mean():+.3f}")

    # --- zapis, bez gubienia innych kluczy ---
    path = DATA / "calib.json"
    calib = {}
    if path.exists():
        try:
            calib = json.loads(path.read_text())
        except ValueError:
            calib = {}
    calib["calib_c"] = round(float(c), 4)
    calib["nb_r"] = round(r, 2)
    calib.setdefault("form", {})
    path.write_text(json.dumps(calib, indent=2))
    print(f"\nZapisano do {path}:")
    print(f"  calib_c = {calib['calib_c']}, nb_r = {calib['nb_r']}")
    if calib["form"]:
        print(f"  zachowano konfiguracje formy: {list(calib['form'])}")


if __name__ == "__main__":
    main()
