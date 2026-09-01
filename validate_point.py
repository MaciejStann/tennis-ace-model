"""
Walidacja modelu punktowego. Trening na wczesniejszych sezonach,
test na najnowszych.

    python validate_point.py
"""
import numpy as np
import pandas as pd

import pointmodel as PM
from build_db import DATA


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()


def main():
    d = pd.read_csv(DATA / "matches_slim.csv")
    d["year"] = d.tourney_date // 10000
    split = d.year.max() - 1 if d.year.max() > d.year.min() + 2 else d.year.max()
    tr, te = d[d.year < split], d[d.year >= split]
    print(f"trening: {len(tr)} wystapien (do {split - 1})")
    print(f"test:    {len(te)} wystapien (od {split})\n")

    rates, meta = PM.build_serve_rates(tr)
    print(f"srednia tourowa p_serve: {meta['tour_p_serve']:.4f}")
    print("mnozniki nawierzchni: "
          + ", ".join(f"{k} {v:.3f}" for k, v in meta["surf_mult"].items()))

    rows = []
    for r in te.itertuples():
        p1 = PM.effective_p_serve(rates, meta, r.player, r.opp, r.surface)
        p2 = PM.effective_p_serve(rates, meta, r.opp, r.player, r.surface)
        if p1 is None or p2 is None:
            continue
        out = PM.match_outcome(p1, p2, int(r.best_of))
        rows.append({"p": out["p_win"], "won": r.won,
                     "exp_games": out["exp_games"], "svgms": r.svgms,
                     "rank": r.rank, "opp_rank": r.opp_rank,
                     "surface": r.surface, "bo": r.best_of})
    t = pd.DataFrame(rows).dropna(subset=["p", "won"])
    print(f"\nprob testowa: {len(t)} wystapien\n")

    base_ll = ll(t.p, t.won)
    print(f"{'model':32} log loss {base_ll:.4f}  traf. {((t.p > .5) == t.won).mean():.3f}")
    print(f"{'rzut moneta':32} log loss {ll(np.full(len(t), .5), t.won):.4f}  traf. 0.500")

    rk = t.dropna(subset=["rank", "opp_rank"])
    if len(rk) > 100:
        pred = (rk["rank"] < rk.opp_rank).astype(float) * .78 + .11
        print(f"{'wyzej notowany wygrywa':32} log loss {ll(pred, rk.won):.4f}"
              f"  traf. {((rk['rank'] < rk.opp_rank) == rk.won).mean():.3f}")

    print("\n=== kalibracja ===")
    t["b"] = pd.cut(t.p, [0, .2, .35, .5, .65, .8, 1])
    for b, g in t.groupby("b", observed=True):
        print(f"  {str(b):14} n={len(g):>5}  model {g.p.mean():.3f}  "
              f"fakt {g.won.mean():.3f}  roznica {g.won.mean() - g.p.mean():+.3f}")

    print("\n=== wg nawierzchni i formatu ===")
    for col in ("surface", "bo"):
        for v, g in t.groupby(col, observed=True):
            if len(g) > 200:
                print(f"  {col}={v}: n={len(g):>5} log loss {ll(g.p, g.won):.4f}")

    print("\n=== przewidywana liczba gemow ===")
    tg = t.dropna(subset=["exp_games", "svgms"])
    print(f"  model przewiduje srednio {tg.exp_games.mean():.1f} gemow")
    print(f"  faktyczna srednia (x2 svgms) {2 * tg.svgms.mean():.1f}")
    print(f"  korelacja: {tg.exp_games.corr(2 * tg.svgms):.3f}")


if __name__ == "__main__":
    main()
