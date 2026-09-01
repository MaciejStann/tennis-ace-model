"""
Dopisuje kolumny potrzebne do modelu punktowego:
  sv_1in, sv_1won, sv_2won  — punkty przy serwisie
  bp_saved, bp_faced        — break pointy
  rank, opp_rank            — ranking w momencie meczu

Odtwarza je z data/tml*.csv, zachowując wiersze dociągnięte z API
(dla nich pola zostaną puste do następnej aktualizacji).

    python migrate_serve.py
"""
import glob

import pandas as pd

from build_db import DATA, to_long

NEW = ["sv_1in", "sv_1won", "sv_2won", "bp_saved", "bp_faced",
       "rank", "opp_rank"]
KEY = ["player", "opp", "tourney_date"]

path = DATA / "matches_slim.csv"
slim = pd.read_csv(path)
print(f"matches_slim.csv: {len(slim)} wierszy")

brak = [c for c in NEW if c not in slim.columns]
if not brak:
    print("Kolumny już istnieją — nic do zrobienia.")
    raise SystemExit
print(f"dodaję: {brak}")

files = sorted(glob.glob(str(DATA / "tml*.csv")))
if not files:
    print("Brak data/tml*.csv — uruchom najpierw `python build_db.py`.")
    raise SystemExit

raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
src = to_long(raw)[KEY + NEW].drop_duplicates(subset=KEY)
print(f"źródło TML: {len(src)} unikalnych wystąpień")

slim = slim.drop(columns=[c for c in NEW if c in slim.columns])
merged = slim.merge(src, on=KEY, how="left")

filled = merged.sv_1won.notna().sum()
print(f"uzupełniono: {filled} / {len(merged)} ({100 * filled / len(merged):.1f}%)")
print(f"puste (dane z API): {len(merged) - filled} — uzupełnią się przy "
      "następnym `python update_db.py`")

# kontrola sensowności: p_serve musi mieścić się w rozsądnym zakresie
ok = merged.dropna(subset=["sv_1won", "sv_2won", "svpt"])
ok = ok[ok.svpt > 0]
p = (ok.sv_1won + ok.sv_2won) / ok.svpt
print(f"\np_serve: średnia {p.mean():.3f}, zakres "
      f"{p.quantile(.01):.3f}–{p.quantile(.99):.3f}")
poza = ((p < 0.3) | (p > 0.95)).sum()
print(f"wartości poza sensownym zakresem 0,30–0,95: {poza} "
      f"({100 * poza / len(p):.2f}%)")

merged.to_csv(path, index=False)
print(f"\nZapisano. Kolumn: {len(merged.columns)}")
