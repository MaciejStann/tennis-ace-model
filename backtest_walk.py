"""
Backtest krocz-przez-czas dla modelu punktowego.

Model NIE widzi kursow ani wynikow przyszlych meczow. Dla kazdego sezonu
testowego przelicza stawki wylacznie z meczow WCZESNIEJSZYCH, typuje, a
dopiero potem porownuje z faktem. To najostrzejszy uczciwy test.

    python backtest_walk.py

Szuka tez, GDZIE model jest slaby — po to, zeby bylo co poprawiac.
"""
import numpy as np
import pandas as pd

import pointmodel as PM
from build_db import DATA


def ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()


def dopasuj_blend(rates, meta, tr):
    """
    Uczy wag laczenia modelu z rankingiem WYLACZNIE na danych treningowych.
    Bez tego mielibysmy przeciek — wagi znalyby przyszlosc.
    """
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6)
                          / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    prob = przewiduj(rates, meta, tr.sample(min(len(tr), 6000), random_state=0))
    prob = prob.dropna(subset=["rank", "opp_rank"])
    if len(prob) < 500:
        return None
    X = np.column_stack([
        np.ones(len(prob)), lg(prob.p.values),
        np.log(prob["rank"].clip(1, 2000)) - np.log(prob.opp_rank.clip(1, 2000)),
    ])
    y = prob.won.values.astype(float)
    b = np.zeros(3)
    for _ in range(200):
        z = np.clip(X @ b, -30, 30)
        pr = 1 / (1 + np.exp(-z))
        W = np.clip(pr * (1 - pr), 1e-9, None)
        try:
            b = b + np.linalg.solve(X.T @ (X * W[:, None]) + 1e-4 * np.eye(3),
                                    X.T @ (y - pr))
        except np.linalg.LinAlgError:
            return None
    return b


def zastosuj_blend(t, b):
    if b is None:
        t["p_blend"] = t.p
        return t
    lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6)
                          / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    dr = (np.log(t["rank"].clip(1, 2000))
          - np.log(t.opp_rank.clip(1, 2000)))
    z = b[0] + b[1] * lg(t.p.values) + b[2] * dr.fillna(0).values
    t["p_blend"] = np.where(t["rank"].isna() | t.opp_rank.isna(), t.p,
                            1 / (1 + np.exp(-np.clip(z, -30, 30))))
    return t


def przewiduj(rates, meta, df):
    out = []
    for r in df.itertuples():
        a = PM.effective_p_serve(rates, meta, r.player, r.opp, r.surface)
        b = PM.effective_p_serve(rates, meta, r.opp, r.player, r.surface)
        if a is None or b is None:
            continue
        o = PM.match_outcome(a, b, int(r.best_of))
        out.append({
            "p": o["p_win"], "won": r.won, "surface": r.surface,
            "bo": r.best_of, "year": r.year,
            "rank": r.rank, "opp_rank": r.opp_rank,
            "n_hist": 0, "exp_games": o["exp_games"], "svgms": r.svgms,
        })
    return pd.DataFrame(out)


def main():
    d = pd.read_csv(DATA / "matches_slim.csv")
    d["year"] = d.tourney_date // 10000
    d = d[d.won.isin([0, 1])]
    lata = sorted(d.year.unique())
    start = lata[3] if len(lata) > 4 else lata[-1]

    print("Backtest krocz-przez-czas")
    print("Kazdy sezon typowany wylacznie z danych WCZESNIEJSZYCH.\n")
    print(f"{'':13}{'model punktowy':>19}{'ranking':>19}{'polaczone':>19}")
    print(f"{'sezon':>6} {'n':>6} {'log loss':>9} {'trafn.':>9} "
          f"{'log loss':>9} {'trafn.':>9} {'log loss':>9} {'trafn.':>9}")

    wszystko = []
    for rok in [r for r in lata if r >= start]:
        tr, te = d[d.year < rok], d[d.year == rok]
        if len(tr) < 3000 or len(te) < 200:
            continue
        rates, meta = PM.build_serve_rates(tr)
        t = przewiduj(rates, meta, te)
        if len(t) < 100:
            continue
        t["year"] = rok
        t = zastosuj_blend(t, dopasuj_blend(rates, meta, tr))
        # ranking jako samodzielna poprzeczka
        t["p_rank"] = np.where(
            t["rank"].isna() | t.opp_rank.isna(), 0.5,
            1 / (1 + np.exp(np.clip(
                1.0 * (np.log(t["rank"].clip(1, 2000))
                       - np.log(t.opp_rank.clip(1, 2000))), -30, 30))))
        wszystko.append(t)
        print(f"{rok:>6} {len(t):>6} {ll(t.p, t.won):>9.4f} "
              f"{((t.p > .5) == t.won).mean():>9.3f} "
              f"{ll(t.p_rank, t.won):>9.4f} "
              f"{((t.p_rank > .5) == t.won).mean():>9.3f} "
              f"{ll(t.p_blend, t.won):>9.4f} "
              f"{((t.p_blend > .5) == t.won).mean():>9.3f}")

    if not wszystko:
        print("\nZa malo danych na backtest.")
        return
    a = pd.concat(wszystko, ignore_index=True)
    print(f"\nRAZEM n={len(a)}")
    for lab, col in (("model punktowy", "p"), ("ranking", "p_rank"),
                     ("polaczone", "p_blend")):
        print(f"  {lab:18} log loss {ll(a[col], a.won):.4f}  "
              f"trafnosc {((a[col] > .5) == a.won).mean():.3f}")
    zm = (a.p_rank > .5) != (a.p_blend > .5)
    if zm.sum() > 50:
        z = a[zm]
        print(f"\n  Model zmienia typ rankingu w {zm.sum()} meczach "
              f"({100 * zm.mean():.1f}%):")
        print(f"    ranking mial racje:   {((z.p_rank > .5) == z.won).mean():.3f}")
        print(f"    po zmianie racje ma:  {((z.p_blend > .5) == z.won).mean():.3f}")

    print("\n=== GDZIE MODEL JEST SLABY ===")

    print("\n1. Wg pewnosci prognozy")
    a["pewnosc"] = (a.p_blend - 0.5).abs()
    a["kosz"] = pd.qcut(a.pewnosc, 4, duplicates="drop")
    for b, g in a.groupby("kosz", observed=True):
        print(f"   {str(b):16} n={len(g):>5}  log loss {ll(g.p_blend, g.won):.4f}"
              f"  trafnosc {((g.p_blend > .5) == g.won).mean():.3f}")

    print("\n2. Wg nawierzchni")
    for v, g in a.groupby("surface"):
        if len(g) > 200:
            print(f"   {v:8} n={len(g):>5}  log loss {ll(g.p, g.won):.4f}")

    print("\n3. Wg formatu")
    for v, g in a.groupby("bo"):
        if len(g) > 200:
            print(f"   bo{v}     n={len(g):>5}  log loss {ll(g.p, g.won):.4f}")

    print("\n4. Faworyt wg rankingu vs prognoza modelu")
    r = a.dropna(subset=["rank", "opp_rank"])
    if len(r) > 500:
        r = r.copy()
        r["fav_rank"] = r["rank"] < r.opp_rank
        r["fav_model"] = r.p > 0.5
        zgoda = r[r.fav_rank == r.fav_model]
        spor = r[r.fav_rank != r.fav_model]
        print(f"   zgodne z rankingiem: n={len(zgoda):>5}  "
              f"log loss {ll(zgoda.p, zgoda.won):.4f}  "
              f"trafnosc {((zgoda.p > .5) == zgoda.won).mean():.3f}")
        print(f"   model przeciw rank.: n={len(spor):>5}  "
              f"log loss {ll(spor.p, spor.won):.4f}  "
              f"trafnosc {((spor.p > .5) == spor.won).mean():.3f}")
        print("   (drugi wiersz mowi, czy warto sluchac modelu, gdy klóci")
        print("    sie z rankingiem — to jego wartosc dodana)")

    print("\n5. Liczba gemow")
    g = a.dropna(subset=["exp_games", "svgms"])
    print(f"   MAE {(g.exp_games - 2 * g.svgms).abs().mean():.2f} gema, "
          f"korelacja {g.exp_games.corr(2 * g.svgms):.3f}")


if __name__ == "__main__":
    main()
