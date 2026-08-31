"""
Diagnostyka modelu: wklad skladnikow, serie, trendy, zaleznosci czasowe.

    python analysis.py

Uruchamia sie na lokalnej bazie, nie zuzywa API.
"""
import numpy as np
import pandas as pd

from build_db import DATA, build

SPLIT_YEAR = 2025   # trening: wczesniej, test: od tego roku


def load():
    long = pd.read_csv(DATA / "matches_slim.csv")
    long["year"] = long.tourney_date // 10000
    return long.sort_values("tourney_date").reset_index(drop=True)


def make_predictor(train):
    players, meta = build(train)
    D, sm = players.to_dict("index"), meta["surface_mult"]
    im = meta["indoor_mult"]

    def mu(row, ret=True, surf=True, ind=True):
        p, o = D.get(row.player), D.get(row.opp)
        if p is None or np.isnan(p.get("ace_pct", np.nan)):
            return np.nan
        if surf:
            b = p.get(f"ace_{str(row.surface).lower()}")
            if b is None or np.isnan(b):
                b = p["ace_pct"] * sm.get(row.surface, 1.0)
        else:
            b = p["ace_pct"]
        rm = 1.0
        if ret and o and not np.isnan(o.get("ret_mult", np.nan)):
            rm = o["ret_mult"]
        i = im if (ind and str(row.indoor).upper().startswith("I")) else 1.0
        return b * rm * i * row.svpt
    return mu, meta


def main():
    long = load()
    train, test = long[long.year < SPLIT_YEAR], long[long.year >= SPLIT_YEAR]
    print(f"Baza: {len(long)} wystepow, do {int(long.tourney_date.max())}")
    print(f"Trening: {len(train)}  Test: {len(test)}\n")
    mu_fn, meta = make_predictor(train)

    t = test.copy()
    print("=== 1. WKLAD SKLADNIKOW MODELU (MAE, nizej = lepiej) ===")
    for lab, kw in [("samo ace% zawodnika", dict(ret=0, surf=0, ind=0)),
                    ("+ nawierzchnia", dict(ret=0, surf=1, ind=0)),
                    ("+ returner", dict(ret=1, surf=1, ind=0)),
                    ("+ hala (pelny model)", dict(ret=1, surf=1, ind=1))]:
        t["p"] = t.apply(lambda r: mu_fn(r, **kw), axis=1)
        s = t.dropna(subset=["p"])
        print(f"  {lab:26} {(s.p - s.ace).abs().mean():.4f}")
    print(f"  mnoznik hali w bazie: {meta['indoor_mult']:.3f}")

    t["mu"] = t.apply(mu_fn, axis=1)
    t = t.dropna(subset=["mu"])
    t["z"] = (t.ace - t.mu) / np.sqrt(t.mu.clip(lower=0.5))
    t = t.sort_values(["player", "tourney_date"])
    cnt = t.groupby("player").size()
    t = t[t.player.isin(cnt[cnt >= 15].index)]
    # odjecie sredniej zawodnika oddziela prawdziwe serie od bledu modelu
    t["zd"] = t.z - t.groupby("player").z.transform("mean")

    print("\n=== 2. HOT HAND (autokorelacja reszt) ===")
    for col, lab in (("z", "surowa"), ("zd", "po odjeciu sredniej gracza")):
        t["prev"] = t.groupby("player")[col].shift(1)
        s = t.dropna(subset=["prev"])
        print(f"  {lab:30} r = {s[col].corr(s.prev):+.4f}")
    print("  Roznica pokazuje, ile 'serii' to tak naprawde staly blad modelu.")

    print("\n=== 3. SERIE ===")
    t["above"] = (t.zd > 0).astype(int)
    t["streak"] = t.groupby("player").above.transform(
        lambda x: x.shift(1).rolling(3, min_periods=3).sum())
    for k in (0, 1, 2, 3):
        g = t[t.streak == k]
        if len(g) > 150:
            print(f"  po {k}/3 powyzej wlasnej sredniej: "
                  f"{g.zd.mean():+.4f} sd (n={len(g)})")

    print("\n=== 4. ODPOCZYNEK / GLEBOKOSC TURNIEJU ===")
    t["prev_d"] = t.groupby("player").tourney_date.shift(1)

    def days(a, b):
        try:
            return (pd.to_datetime(str(int(a)), format="%Y%m%d")
                    - pd.to_datetime(str(int(b)), format="%Y%m%d")).days
        except Exception:
            return np.nan
    t["rest"] = [days(a, b) if not pd.isna(b) else np.nan
                 for a, b in zip(t.tourney_date, t.prev_d)]
    for lo, hi, lab in [(0, 2, "0-2 dni (kolejna runda)"), (3, 7, "3-7 dni"),
                        (8, 21, "8-21 dni"), (22, 400, "22+ dni")]:
        g = t[(t.rest >= lo) & (t.rest <= hi)]
        if len(g) > 150:
            print(f"  {lab:26} {g.zd.mean():+.4f} sd (n={len(g)})")

    print("\n=== 5. STABILNOSC ace% MIEDZY OKRESAMI ===")
    a = train.groupby("player").apply(lambda g: g.ace.sum() / g.svpt.sum())
    b = test.groupby("player").apply(lambda g: g.ace.sum() / g.svpt.sum())
    big = test.groupby("player").size()
    both = pd.concat([a.rename("old"), b.rename("new")], axis=1).dropna()
    both = both[both.index.isin(big[big >= 25].index)]
    if len(both) > 20:
        print(f"  zawodnikow z >=25 meczami w tescie: {len(both)}")
        print(f"  korelacja ace% miedzy okresami: {both.old.corr(both.new):.3f}")
        ch = (both.new - both.old) * 100
        print(f"  najwieksze wzrosty: "
              f"{ch.sort_values(ascending=False).head(3).round(2).to_dict()}")
        print(f"  najwieksze spadki:  "
              f"{ch.sort_values().head(3).round(2).to_dict()}")
        print("  Wysoka korelacja = ace% to cecha trwala, nie 'forma'.")


if __name__ == "__main__":
    main()
