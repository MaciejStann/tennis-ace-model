"""
Naprawia kolumne `won` w wierszach, gdzie jest nieznana (-1 lub puste).

Skad blad: migrate_columns.py wypelnial braki wartoscia -1 jako znacznik
"nieznane", a update_db.py ustawia won z pola match_winner, ktore API nie
zawsze zwraca. Efekt: wiersze z won = -1 trafialy do modelu jako etykieta,
odwracajac kalibracje.

Naprawa: zwyciezce wnioskujemy z kolumny `score`, ktora ZAWSZE jest zapisana
z perspektywy zwyciezcy — kto wygral wiecej setow w zapisie, ten wygral mecz.

    python fix_won.py
"""
import re

import pandas as pd

from build_db import DATA

path = DATA / "matches_slim.csv"
d = pd.read_csv(path)
print(f"wierszy: {len(d)}")

zle = ~d.won.isin([0, 1])
print(f"z nieprawidlowym `won`: {zle.sum()} "
      f"({100 * zle.sum() / len(d):.1f}%)")
if zle.sum() == 0:
    print("Nic do naprawy.")
    raise SystemExit


def sety_z_zapisu(score: str):
    """Ile setow wygral ten, z ktorego perspektywy zapisano wynik."""
    if not isinstance(score, str) or not score.strip():
        return None
    a = b = 0
    for part in score.split():
        m = re.match(r"^(\d+)-(\d+)", part)
        if not m:
            continue
        x, y = int(m.group(1)), int(m.group(2))
        if x > y:
            a += 1
        elif y > x:
            b += 1
    if a == b:
        return None
    return a > b


# W parze (player, opp, data) score kazdego wiersza jest z perspektywy
# ZWYCIEZCY meczu, wiec dla przegranego zapis jest "odwrocony" i sety
# wychodza na jego niekorzysc.
def z_zapisu(s):
    r = sety_z_zapisu(s)
    return float("nan") if r is None else float(r)


# kolumna jest typu float, wiec brak oznaczamy NaN (pd.NA rzuca blad
# w pandas 3)
d["won"] = d.won.astype(float)
d.loc[zle, "won"] = d.loc[zle, "score"].map(z_zapisu).values

nadal = ~d.won.isin([0.0, 1.0])
print(f"naprawiono: {zle.sum() - nadal.sum()}")
print(f"nie da sie ustalic (krecze, walkowery): {nadal.sum()}")

d = d[~nadal].copy()
d["won"] = d.won.astype(int)
print(f"\npo naprawie: {len(d)} wierszy, odsetek wygranych "
      f"{d.won.mean():.3f}  (ma byc ~0.500)")

d.to_csv(path, index=False)
print("Zapisano.")
