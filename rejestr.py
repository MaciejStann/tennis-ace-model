"""
Rejestr zakladow — zapis prognozy w momencie obstawiania i rozliczenie
po meczu.

Po co: cala walidacja modelu mierzy dokladnosc wobec RZECZYWISTOSCI
(MAE 2,62 asa, log loss 0,638), nigdy wobec KURSOW. To dwa rozne pytania.
Model trafiajacy w 80% na faworytach przy kursie 1,20 traci pieniadze.
Bez zapisu realnych zakladow nie da sie stwierdzic, czy przewaga istnieje.

Format: jeden wiersz na zaklad, dopisywanie na koncu. Bez bazy danych —
CSV wystarczy przy kilkuset pozycjach i da sie go otworzyc w arkuszu.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pandas as pd

PLIK = Path(__file__).parent / "data" / "zaklady.csv"
KOLUMNY = [
    "data_zapisu", "data_meczu", "p1", "p2", "nawierzchnia", "rynek",
    "strona", "linia", "kurs", "p_model", "ev", "stawka",
    "wynik", "zysk", "notatka",
]


def wczytaj() -> pd.DataFrame:
    if not PLIK.exists():
        return pd.DataFrame(columns=KOLUMNY)
    try:
        # Kolumny tekstowe wymuszamy jawnie — pusta kolumna `wynik`
        # wczytywalaby sie jako float i nie przyjmowalaby "W"/"P".
        d = pd.read_csv(PLIK, dtype={"wynik": "object", "notatka": "object",
                                     "strona": "object", "rynek": "object"})
        for k in KOLUMNY:
            if k not in d.columns:
                d[k] = ""
        return d[KOLUMNY]
    except Exception:
        return pd.DataFrame(columns=KOLUMNY)


def dopisz(**pola) -> None:
    """Dopisuje zaklad. Brakujace pola zostaja puste."""
    PLIK.parent.mkdir(parents=True, exist_ok=True)
    nowy = not PLIK.exists()
    wiersz = {k: pola.get(k, "") for k in KOLUMNY}
    wiersz["data_zapisu"] = date.today().strftime("%Y-%m-%d")
    with PLIK.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLUMNY)
        if nowy:
            w.writeheader()
        w.writerow(wiersz)


def rozlicz(indeks: int, wygrany: bool) -> bool:
    """Ustawia wynik i przelicza zysk. False, gdy indeks poza zakresem."""
    d = wczytaj()
    if indeks not in d.index:
        return False
    kurs = float(d.at[indeks, "kurs"] or 0)
    stawka = float(d.at[indeks, "stawka"] or 0)
    d.at[indeks, "wynik"] = "W" if wygrany else "P"
    d.at[indeks, "zysk"] = round(stawka * (kurs - 1) if wygrany else -stawka, 2)
    d.to_csv(PLIK, index=False)
    return True


def usun(indeks: int) -> bool:
    d = wczytaj()
    if indeks not in d.index:
        return False
    d.drop(index=indeks).to_csv(PLIK, index=False)
    return True


def podsumowanie(d: pd.DataFrame | None = None) -> dict:
    """
    Skumulowany wynik. Liczy TYLKO rozliczone zaklady — otwarte pozycje
    nie moga poprawiac ani psuc bilansu.
    """
    d = wczytaj() if d is None else d
    r = d[d.wynik.isin(["W", "P"])].copy()
    if r.empty:
        return {"n": 0, "otwarte": int((~d.wynik.isin(["W", "P"])).sum())}
    r["stawka"] = pd.to_numeric(r.stawka, errors="coerce").fillna(0)
    r["zysk"] = pd.to_numeric(r.zysk, errors="coerce").fillna(0)
    r["ev"] = pd.to_numeric(r.ev, errors="coerce")
    obrot = r.stawka.sum()
    return {
        "n": len(r),
        "otwarte": int((~d.wynik.isin(["W", "P"])).sum()),
        "trafione": int((r.wynik == "W").sum()),
        "skutecznosc": (r.wynik == "W").mean(),
        "obrot": obrot,
        "zysk": r.zysk.sum(),
        "roi": r.zysk.sum() / obrot if obrot else 0.0,
        "ev_oczekiwany": (r.ev * r.stawka).sum() / obrot if obrot else 0.0,
    }


def kalibracja(d: pd.DataFrame | None = None, koszy: int = 4):
    """
    Czy prawdopodobienstwa modelu sa prawdziwe: w koszykach p_model
    porownuje deklarowane z faktycznym odsetkiem trafien.
    """
    d = wczytaj() if d is None else d
    r = d[d.wynik.isin(["W", "P"])].copy()
    r["p_model"] = pd.to_numeric(r.p_model, errors="coerce")
    r = r.dropna(subset=["p_model"])
    if len(r) < koszy * 5:
        return None
    r["kosz"] = pd.qcut(r.p_model, koszy, duplicates="drop")
    out = []
    for b, g in r.groupby("kosz", observed=True):
        out.append({"zakres": str(b), "n": len(g),
                    "model": g.p_model.mean(),
                    "fakt": (g.wynik == "W").mean()})
    return out
