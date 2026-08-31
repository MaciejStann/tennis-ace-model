"""Przelicza players.csv i meta.json z matches_slim.csv (bez pobierania)."""
import json, pandas as pd
from build_db import DATA, build

long = pd.read_csv(DATA / "matches_slim.csv")
long["year"] = long.tourney_date // 10000
players, meta = build(long)
meta["last_match_date"] = int(long.tourney_date.max())
players.to_csv(DATA / "players.csv")
(DATA / "meta.json").write_text(json.dumps(meta, indent=2))
print(f"Zawodnikow: {len(players)} | meczow: {meta['n_matches']}")
print(f"Najnowszy mecz: {meta['last_match_date']}")
print(f"Srednia tourowa ace%: {100*meta['tour_ace_pct']:.2f}")
print("Mnozniki:", ", ".join(f"{k} {v:.2f}" for k,v in meta["surface_mult"].items()))
