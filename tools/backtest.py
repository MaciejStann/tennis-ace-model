"""
Walidacja out-of-sample: baza budowana na 2019-2024, testowana na 2025-2026.
Porownuje model z dwoma baseline'ami.
"""
import numpy as np
import pandas as pd

from build_db import to_long, build, DATA
import glob

raw = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(DATA / "tml*.csv")))],
                ignore_index=True)
long = to_long(raw)

print("indoor — rozklad wartosci:", long.indoor.value_counts(dropna=False).to_dict())

train = long[long.year <= 2024]
test = long[long.year >= 2025]
players, meta = build(train)
print(f"\ntrain: {len(train)//2} meczow | test: {len(test)//2} meczow")

tour_ace = meta["tour_ace_pct"]
surf_mult = meta["surface_mult"]

P = players.to_dict("index")


def predict(row):
    """Zwraca przewidywana liczbe asow zawodnika w tym meczu."""
    p = P.get(row.player)
    o = P.get(row.opp)
    if p is None or np.isnan(p.get("ace_pct", np.nan)):
        return np.nan
    surf = str(row.surface).lower()
    base = p.get(f"ace_{surf}")
    if base is None or np.isnan(base):
        base = p["ace_pct"] * surf_mult.get(row.surface, 1.0)
    ret_mult = o["ret_mult"] if o and not np.isnan(o.get("ret_mult", np.nan)) else 1.0
    return base * ret_mult * row.svpt


t = test.copy()
t["pred"] = t.apply(predict, axis=1)
t = t.dropna(subset=["pred"])

# baseline 1: srednia tourowa
t["base_tour"] = tour_ace * t.svpt
# baseline 2: wlasne ace% zawodnika bez korekt (nawierzchnia, returner)
t["base_player"] = t.player.map(lambda n: P.get(n, {}).get("ace_pct", tour_ace)) * t.svpt


def report(name, col):
    err = t[col] - t.ace
    print(f"{name:34s} MAE {err.abs().mean():5.2f}   RMSE {np.sqrt((err**2).mean()):5.2f}"
          f"   bias {err.mean():+5.2f}")


print(f"\nProb testowa: {len(t)} wystepow\n")
report("srednia tourowa (baseline)", "base_tour")
report("ace% zawodnika (baseline)", "base_player")
report("model (nawierzchnia + returner)", "pred")

# korelacja
print(f"\nkorelacja pred vs faktyczne: {t.pred.corr(t.ace):.3f}")
print(f"korelacja baseline gracza:    {t.base_player.corr(t.ace):.3f}")

# kalibracja: czy Poisson to dobry rozklad?
print(f"\nOverdyspersja (var/mean reszt wzgledem pred):")
resid_var = ((t.ace - t.pred) ** 2).mean()
print(f"  wariancja reszt {resid_var:.2f} vs srednia pred {t.pred.mean():.2f}"
      f"  ->  ratio {resid_var / t.pred.mean():.2f}")
