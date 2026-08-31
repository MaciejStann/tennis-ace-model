"""
Dopisuje kolumny tourney_name / round / score do matches_slim.csv.

Odtwarza je z plikow zrodlowych data/tml*.csv, zachowujac wiersze dociagniete
z API (dla nich pola zostana puste do nastepnej aktualizacji).

    python migrate_columns.py
"""
import glob

import pandas as pd

from build_db import DATA, to_long

NEW = ["tourney_name", "round", "score", "won"]
KEY = ["player", "opp", "tourney_date"]

slim_path = DATA / "matches_slim.csv"
slim = pd.read_csv(slim_path)
print(f"matches_slim.csv: {len(slim)} wierszy")

if all(c in slim.columns for c in NEW):
    print("Kolumny juz istnieja — nic do zrobienia.")
    raise SystemExit
print(f"dodaje: {[c for c in NEW if c not in slim.columns]}")

files = sorted(glob.glob(str(DATA / "tml*.csv")))
if not files:
    print("Brak plikow data/tml*.csv — uruchom najpierw `python build_db.py`.")
    raise SystemExit

raw = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
src = to_long(raw)[KEY + NEW].drop_duplicates(subset=KEY)
print(f"zrodlo TML: {len(src)} unikalnych wystepow")

# jesli czesc kolumn juz jest, nadpisujemy je swiezymi wartosciami
slim = slim.drop(columns=[c for c in NEW if c in slim.columns])
merged = slim.merge(src, on=KEY, how="left")
for c in NEW:
    merged[c] = merged[c].fillna("" if c != "won" else -1)

filled = (merged.tourney_name != "").sum()
print(f"uzupelniono: {filled} / {len(merged)} wierszy "
      f"({100 * filled / len(merged):.1f}%)")
print(f"puste (dane z API): {len(merged) - filled} — uzupelnia sie przy "
      "nastepnym `python update_db.py`")

merged.to_csv(slim_path, index=False)
print(f"\nZapisano. Kolumny: {list(merged.columns)}")
