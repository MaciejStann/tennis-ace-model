"""Male funkcje pomocnicze: daty, linie, wykrywanie formatu i nawierzchni."""
import re

import ui.stan as S

GRAND_SLAMS = ("us open", "australian open", "wimbledon",
               "roland garros", "french open")
ROUNDS = {"F": "Final", "SF": "Polfinal", "QF": "Cwiercfinal", "R16": "1/8",
          "R32": "1/16", "R64": "1/32", "R128": "1/64", "RR": "Grupa",
          "BR": "O 3. miejsce", "Q1": "Kwalifikacje", "Q2": "Kwalifikacje",
          "Q3": "Kwalifikacje"}


def infer_best_of(tournament: str, rank_name: str) -> tuple[int, str]:
    """Wielki Szlem = bo5. Interpunkcja z API bywa różna („U.S. Open")."""
    blob = re.sub(r"[^a-z0-9]+", " ", f"{tournament} {rank_name}".lower())
    compact = blob.replace(" ", "")
    if "grandslam" in compact:
        return 5, "ranga: Grand Slam"
    for gs in GRAND_SLAMS:
        if gs.replace(" ", "") in compact:
            return 5, f"turniej: {gs.title()}"
    if "daviscup" in compact:
        return 5, "Puchar Davisa"
    return 3, ""


def polowka(x: float) -> float:
    """Najblizsza polowka (x.5). Linie totali nigdy nie sa calkowite —
    przy calkowitej wynik rowny linii oznacza zwrot stawki, czego model
    nie liczy."""
    return round(float(x) - 0.5) + 0.5


def default_games(best_of: int, surface: str) -> float:
    table = S.META.get("avg_games", {}).get(str(best_of), {})
    v = float(table.get(surface) or table.get("_all")
              or (35.6 if best_of == 5 else 22.8))
    return polowka(v)


def surface_from_court(court: str) -> tuple[str | None, bool]:
    # Flashscore podaje np. "hard", "clay", "indoor hard"
    c = (court or "").lower()
    surf = next((s for w, s in (("clay", "Clay"), ("grass", "Grass"),
                                ("hard", "Hard"), ("carpet", "Hard"))
                 if w in c), None)
    return surf, ("indoor" in c or c.startswith("i."))


def surface_of(cfg: dict) -> str:
    return {"Hard": "hard", "Clay": "maczka", "Grass": "trawa"}.get(
        cfg["surface"], cfg["surface"].lower())
