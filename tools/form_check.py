"""
Czy forma biezaca poprawia prognoze? Test na AKTUALNYCH danych.

Poprzedni test szedl na bazie konczacej sie w styczniu 2026 — brakowalo
calego sezonu na maczce i trawie. Ten skrypt powtarza go na tym, co masz
teraz, i sprawdza osobno asy oraz podwojne bledy.

    python form_check.py
"""
import numpy as np
import pandas as pd

from build_db import DATA

SHRINK = 400.0
TEST_FROM = 20250101   # od kiedy liczymy blad (wczesniejsze = tylko historia)


def run(metric: str, label: str):
    long = pd.read_csv(DATA / "matches_slim.csv").sort_values("tourney_date")
    long = long[long.svpt > 0].reset_index(drop=True)
    tour = long[metric].sum() / long.svpt.sum()
    smult = {s: (g[metric].sum() / g.svpt.sum()) / tour
             for s, g in long.groupby("surface")}

    hist, hsurf, rows = {}, {}, []
    for r in long.itertuples():
        h = hist.get(r.player)
        hs = hsurf.get((r.player, r.surface))
        if h and len(h) >= 15:
            a = np.array(h)
            base = (a[:, 0].sum() + SHRINK * tour) / (a[:, 1].sum() + SHRINK)
            prior = tour * smult.get(r.surface, 1.0)
            if hs and len(hs) >= 5:
                sarr = np.array(hs)
                surf_base = ((sarr[:, 0].sum() + SHRINK * prior)
                             / (sarr[:, 1].sum() + SHRINK))
            else:
                surf_base = base * smult.get(r.surface, 1.0)
            rec = {}
            for n in (5, 10, 20, 40):
                w = a[-n:]
                rec[n] = (w[:, 0].sum() + SHRINK * tour) / (w[:, 1].sum() + SHRINK)
            rows.append({"date": r.tourney_date, "svpt": r.svpt,
                         "y": getattr(r, metric), "base": surf_base,
                         "n_hist": len(h),
                         **{f"r{n}": rec[n] for n in (5, 10, 20, 40)}})
        hist.setdefault(r.player, []).append((getattr(r, metric), r.svpt))
        hsurf.setdefault((r.player, r.surface), []).append(
            (getattr(r, metric), r.svpt))

    t = pd.DataFrame(rows)
    t = t[t.date >= TEST_FROM]
    if len(t) < 500:
        print(f"{label}: za mala proba testowa ({len(t)})")
        return

    def mae(rate):
        return ((rate * t.svpt) - t.y).abs().mean()

    b = mae(t.base)
    print(f"\n=== {label} ===")
    print(f"proba: {len(t)} wystepow, do {int(t.date.max())}")
    print(f"{'baza (obecny model)':<34} MAE {b:.3f}")
    for n in (5, 10, 20, 40):
        print(f"{f'tylko ostatnie {n}':<34} MAE {mae(t[f'r{n}']):.3f}")

    best = (None, 9, 0)
    print("\nmieszanka w*forma + (1-w)*baza:")
    for n in (5, 10, 20, 40):
        line = f"  okno {n:>2}: "
        for w in (0.2, 0.3, 0.4, 0.5, 0.7):
            m = mae(w * t[f"r{n}"] + (1 - w) * t.base)
            line += f"w={w} {m:.3f}  "
            if m < best[1]:
                best = (n, m, w)
        print(line)

    gain = 100 * (b - best[1]) / b
    print(f"\nnajlepsza: okno {best[0]}, w={best[2]}, MAE {best[1]:.3f} "
          f"({gain:+.2f}% vs baza)")
    if gain < 0.5:
        print(">>> WNIOSEK: forma NIE pomaga w istotny sposob.")
    elif gain < 2:
        print(">>> WNIOSEK: forma pomaga nieznacznie. Warta wdrozenia "
              "tylko jesli wynik powtorzy sie na kolejnym sezonie.")
    else:
        print(">>> WNIOSEK: forma pomaga wyraznie — warto wdrozyc.")
    return best, gain


if __name__ == "__main__":
    run("ace", "ASY")
    run("df", "PODWOJNE BLEDY")
    print("\nUwaga: parametry dobrane na tej samej probie, na ktorej mierzymy "
          "\nblad, sa lekko optymistyczne. Traktuj poprawe < 1% jako szum.")
