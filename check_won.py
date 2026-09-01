"""Kontrola spojnosci kolumny `won` — czy odsetek wygranych to ~50%."""
import pandas as pd
from build_db import DATA

d = pd.read_csv(DATA / "matches_slim.csv")
d["year"] = d.tourney_date // 10000
print(f"wierszy: {len(d)}\n")

print("=== odsetek wygranych wg roku (powinno byc ~0.50) ===")
for y, g in d.groupby("year"):
    if len(g) < 100:
        continue
    flag = "  <-- PODEJRZANE" if not 0.45 < g.won.mean() < 0.55 else ""
    print(f"  {y}: {g.won.mean():.3f}  (n={len(g)}){flag}")

print("\n=== TML (ma runde) vs API (nie ma) ===")
has_round = d["round"].notna() & (d["round"].astype(str) != "")
for lab, g in (("TML", d[has_round]), ("API", d[~has_round])):
    if len(g) == 0:
        continue
    print(f"  {lab}: n={len(g)}  won={g.won.mean():.3f}  "
          f"zakres dat {int(g.tourney_date.min())}-{int(g.tourney_date.max())}")

print("\n=== czy w parze jest dokladnie jeden zwyciezca? ===")
pair = d.groupby(["tourney_date", "player", "opp"]).won.first().reset_index()
pair["klucz"] = pair.apply(
    lambda r: (r.tourney_date, *sorted([r.player, r.opp])), axis=1)
g = pair.groupby("klucz").won.agg(["sum", "size"])
pelne = g[g["size"] == 2]
print(f"  par kompletnych: {len(pelne)}")
print(f"  z jednym zwyciezca (poprawne): {(pelne['sum'] == 1).mean():.3f}")
print(f"  z dwoma zwyciezcami:  {(pelne['sum'] == 2).sum()}")
print(f"  bez zwyciezcy:        {(pelne['sum'] == 0).sum()}")

print("\n=== spojnosc `won` z kolumna score ===")
s = d.dropna(subset=["score"])
s = s[s.score.astype(str).str.match(r"^\d+-\d+")]
def wiodacy(x):
    try:
        a, b = str(x).split()[0].split("-")[:2]
        return int(a.split("(")[0]) > int(b.split("(")[0])
    except Exception:
        return None
s = s.copy()
s["pierwszy_set_wygrany"] = s.score.map(wiodacy)
s = s.dropna(subset=["pierwszy_set_wygrany"])
zgodne = (s.pierwszy_set_wygrany == (s.won == 1)).mean()
print(f"  wygral pierwszy set = wygral mecz: {zgodne:.3f}")
print("  (score jest z perspektywy ZWYCIEZCY, wiec dla won=1 powinno byc")
print("   blisko 1.0, a dla won=0 blisko 0.0 — laczna zgodnosc ~0.8+)")
