"""
Uczciwa walidacja formy: parametry dobrane na 2025, zmierzone na 2026.

Jesli efekt sie potwierdzi, skrypt zapisuje go do data/calib.json i model
zaczyna go uzywac. Jesli nie — zapisuje 0 i nic sie nie zmienia.

    python oos_check.py
"""
import json

import numpy as np
import pandas as pd

from build_db import DATA

SHRINK = 400.0
MIN_GAIN = 1.0        # % poprawy out-of-sample, ponizej ktorego uznajemy za szum


def build_frame(long: pd.DataFrame, metric: str) -> pd.DataFrame:
    tour = long[metric].sum() / long.svpt.sum()
    smult = {s: (g[metric].sum() / g.svpt.sum()) / tour
             for s, g in long.groupby("surface")}
    hist, hsurf, rows = {}, {}, []
    for r in long.itertuples():
        h, k = hist.get(r.player), hsurf.get((r.player, r.surface))
        if h and len(h) >= 15:
            a = np.array(h)
            base = (a[:, 0].sum() + SHRINK * tour) / (a[:, 1].sum() + SHRINK)
            prior = tour * smult.get(r.surface, 1.0)
            if k and len(k) >= 5:
                s_ = np.array(k)
                sb = (s_[:, 0].sum() + SHRINK * prior) / (s_[:, 1].sum() + SHRINK)
            else:
                sb = base * smult.get(r.surface, 1.0)
            rec = {n: ((a[-n:, 0].sum() + SHRINK * tour)
                       / (a[-n:, 1].sum() + SHRINK)) for n in (5, 10, 20, 40)}
            rows.append({"date": r.tourney_date, "svpt": r.svpt,
                         "y": getattr(r, metric), "base": sb,
                         **{f"r{n}": rec[n] for n in (5, 10, 20, 40)}})
        hist.setdefault(r.player, []).append((getattr(r, metric), r.svpt))
        hsurf.setdefault((r.player, r.surface), []).append(
            (getattr(r, metric), r.svpt))
    return pd.DataFrame(rows)


def evaluate(long, metric, label):
    d = build_frame(long, metric)
    train = d[(d.date >= 20250101) & (d.date < 20260101)]
    test = d[d.date >= 20260101]
    print(f"\n=== {label} ===")
    if len(test) < 500 or len(train) < 500:
        print(f"  za mala proba (train {len(train)}, test {len(test)}) — "
              "pomijam")
        return None

    def mae(t, rate):
        return ((rate * t.svpt) - t.y).abs().mean()

    best = (None, 9e9, None)
    for n in (5, 10, 20, 40):
        for w in np.arange(0.1, 0.85, 0.05):
            m = mae(train, w * train[f"r{n}"] + (1 - w) * train.base)
            if m < best[1]:
                best = (n, m, round(float(w), 2))
    n, _, w = best

    b = mae(test, test.base)
    f = mae(test, w * test[f"r{n}"] + (1 - w) * test.base)
    gain = 100 * (b - f) / b
    print(f"  strojenie na 2025 (n={len(train)}): okno {n}, waga {w}")
    print(f"  TEST na 2026 (n={len(test)}):")
    print(f"    bez formy  MAE {b:.4f}")
    print(f"    z forma    MAE {f:.4f}   ({gain:+.2f}%)")
    if gain >= MIN_GAIN:
        print(f"  >>> POTWIERDZONE (>{MIN_GAIN}%) — wlaczam w modelu")
        return {"window": int(n), "weight": float(w), "gain": round(gain, 2)}
    print(f"  >>> NIE potwierdzone (<{MIN_GAIN}%) — zostawiam wylaczone")
    return None


if __name__ == "__main__":
    long = pd.read_csv(DATA / "matches_slim.csv").sort_values("tourney_date")
    long = long[long.svpt > 0].reset_index(drop=True)
    print(f"Baza: {len(long)} wystepow, do {int(long.tourney_date.max())}")

    res = {"ace": evaluate(long, "ace", "ASY"),
           "df": evaluate(long, "df", "PODWOJNE BLEDY")}

    path = DATA / "calib.json"
    calib = {}
    if path.exists():
        try:
            calib = json.loads(path.read_text())
        except ValueError:
            calib = {}
    # NIE gubimy kluczy kalibracji rozkladu — dopisujemy tylko brakujace
    calib.setdefault("calib_c", 1.0)
    calib.setdefault("nb_r", 26.0)
    calib["form"] = {k: v for k, v in res.items() if v}
    path.write_text(json.dumps(calib, indent=2))

    print("\n--- zapisano do data/calib.json ---")
    if calib["form"]:
        for k, v in calib["form"].items():
            print(f"  {k}: okno {v['window']}, waga {v['weight']} "
                  f"(+{v['gain']}%)")
        print("\nUruchom ponownie aplikacje — forma bedzie uwzgledniana.")
    else:
        print("  brak potwierdzonych efektow — model bez zmian")
