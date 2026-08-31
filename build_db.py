"""
Buduje lokalna baze statystyk serwisowych z TML-Database (ATP).
Uruchom raz na jakis czas:  python build_db.py
Zapisuje: data/players.csv, data/matches.csv, data/meta.json
"""
import json
import pathlib

import pandas as pd
import requests

BASE = "https://raw.githubusercontent.com/Tennismylife/TML-Database/master"
YEARS = range(2019, 2027)
DATA = pathlib.Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)

# Ile punktow serwisowych "sztucznych" dociagamy do sredniej tourowej.
# Wieksze K = mocniejsze sciaganie malych prob do sredniej.
#
# K=800 dobrane pod KALIBRACJE prawdopodobienstw (log loss), nie pod MAE.
# Test out-of-sample (trening <2025, test >=2025), linia floor(mu)+0.5:
#   K=400: log loss 0.6878, MAE 2.644   <- poprzednia wartosc
#   K=800: log loss 0.6843, MAE 2.648   <- obecna
#   K=3200: log loss 0.6838, MAE 2.755  <- log loss stoi, MAE sie psuje
# Powyzej 800 zysk w kalibracji znika, a blad punktowy rosnie.
SHRINK_SVPT = 800.0


def download() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        path = DATA / f"tml{year}.csv"
        if not path.exists():
            resp = requests.get(f"{BASE}/{year}.csv", timeout=60)
            if resp.status_code != 200:
                print(f"  {year}: HTTP {resp.status_code} — pomijam")
                continue
            path.write_bytes(resp.content)
        frames.append(pd.read_csv(path))
        print(f"  {year}: ok")
    return pd.concat(frames, ignore_index=True)


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Jeden wiersz = wystep jednego zawodnika w jednym meczu."""
    need = ["w_ace", "w_df", "w_svpt", "w_SvGms", "l_ace", "l_df", "l_svpt", "l_SvGms"]
    df = df.dropna(subset=need)

    cols = ["surface", "indoor", "tourney_date", "best_of",
            "tourney_name", "round", "score"]
    win = df.rename(columns={
        "winner_name": "player", "loser_name": "opp",
        "w_ace": "ace", "w_df": "df", "w_svpt": "svpt", "w_SvGms": "svgms",
    })[["player", "opp", "ace", "df", "svpt", "svgms"] + cols]
    win["won"] = 1
    los = df.rename(columns={
        "loser_name": "player", "winner_name": "opp",
        "l_ace": "ace", "l_df": "df", "l_svpt": "svpt", "l_SvGms": "svgms",
    })[["player", "opp", "ace", "df", "svpt", "svgms"] + cols]
    los["won"] = 0

    long = pd.concat([win, los], ignore_index=True)
    long = long[(long.svpt > 0) & (long.svgms > 0)]
    long["year"] = long.tourney_date // 10000
    return long


def shrink(made: pd.Series, attempts: pd.Series, prior: float) -> pd.Series:
    """Empiryczny Bayes: male proby sciagane do sredniej tourowej."""
    return (made + SHRINK_SVPT * prior) / (attempts + SHRINK_SVPT)


def build(long: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    tour_ace = long.ace.sum() / long.svpt.sum()
    tour_df = long["df"].sum() / long.svpt.sum()
    pts_per_gm = long.svpt.sum() / long.svgms.sum()

    # mnozniki nawierzchni na poziomie touru (fallback dla malych prob)
    surf_mult = {}
    for surface, grp in long.groupby("surface"):
        surf_mult[surface] = float((grp.ace.sum() / grp.svpt.sum()) / tour_ace)

    # UWAGA: mnoznik hali liczymy TYLKO w obrebie twardych kortow.
    # Globalnie 99% meczow w hali to hard, a na otwartych tylko ~52%
    # (reszta to maczka o niskim ace%), wiec mnoznik liczony bez podzialu
    # mierzyl "hala = hard court" i dublowal korekte nawierzchni.
    # Efekt pozorny: 1.20. Efekt prawdziwy w obrebie hardu: ~1.05.
    indoor_mult = 1.0
    if long.indoor.notna().any():
        hard = long[long.surface == "Hard"]
        ind = hard[hard.indoor.astype(str).str.upper().str.startswith("I")]
        out = hard[hard.indoor.astype(str).str.upper().str.startswith("O")]
        if len(ind) > 200 and len(out) > 200:
            indoor_mult = float(
                (ind.ace.sum() / ind.svpt.sum()) / (out.ace.sum() / out.svpt.sum())
            )

    # --- statystyki przy serwisie ---
    srv = long.groupby("player").agg(
        matches=("ace", "size"), ace=("ace", "sum"),
        dfs=("df", "sum"), svpt=("svpt", "sum"), svgms=("svgms", "sum"),
        last=("tourney_date", "max"),
    )
    srv["ace_pct"] = shrink(srv.ace, srv.svpt, tour_ace)
    srv["df_pct"] = shrink(srv.dfs, srv.svpt, tour_df)
    srv["ace_pct_raw"] = srv.ace / srv.svpt

    # --- statystyki przy returnie (ile asow oddaje) ---
    ret = long.groupby("opp").agg(
        ret_matches=("ace", "size"), ace_conc=("ace", "sum"), svpt_faced=("svpt", "sum"),
    )
    ret["conceded_pct"] = shrink(ret.ace_conc, ret.svpt_faced, tour_ace)
    ret["ret_mult"] = ret.conceded_pct / tour_ace
    ret.index.name = "player"

    # --- rozbicie wlasne na nawierzchnie (z sciagnieciem do mnoznika tourowego) ---
    for surface in ("Hard", "Clay", "Grass"):
        sub = long[long.surface == surface].groupby("player").agg(
            a=("ace", "sum"), s=("svpt", "sum")
        )
        prior_rate = tour_ace * surf_mult.get(surface, 1.0)
        rate = shrink(sub.a, sub.s, prior_rate)
        srv[f"ace_{surface.lower()}"] = rate
        srv[f"n_{surface.lower()}"] = sub.s

    players = srv.join(ret, how="outer").fillna({"ret_matches": 0})
    players = players[players.matches.notna()]

    # srednia laczna liczba gemow wg formatu i nawierzchni (do domyslnych linii)
    uniq = long.drop_duplicates(subset=["tourney_date", "player", "opp"])
    games = {}
    for bo in (3, 5):
        sub = uniq[uniq.best_of == bo]
        if len(sub) < 100:
            continue
        games[str(bo)] = {"_all": round(float(2 * sub.svgms.mean()), 1)}
        for surf in ("Hard", "Clay", "Grass"):
            ss = sub[sub.surface == surf]
            if len(ss) > 100:
                games[str(bo)][surf] = round(float(2 * ss.svgms.mean()), 1)

    meta = {
        "avg_games": games,
        "tour_ace_pct": float(tour_ace),
        "tour_df_pct": float(tour_df),
        "pts_per_service_game": float(pts_per_gm),
        "surface_mult": surf_mult,
        "indoor_mult": indoor_mult,
        "shrink_svpt": SHRINK_SVPT,
        "n_matches": int(len(long) // 2),
        "years": [int(long.year.min()), int(long.year.max())],
    }
    return players, meta


if __name__ == "__main__":
    print("Pobieram TML-Database...")
    raw = download()
    long = to_long(raw)
    players, meta = build(long)

    players.to_csv(DATA / "players.csv")
    slim = long[["player", "opp", "surface", "indoor", "tourney_date",
                 "best_of", "ace", "df", "svpt", "svgms",
                 "tourney_name", "round", "score", "won"]]
    slim.to_csv(DATA / "matches_slim.csv", index=False)
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2))

    print(f"\nZawodnikow: {len(players)}  |  meczow: {meta['n_matches']}")
    print(f"Srednia tourowa ace%: {100 * meta['tour_ace_pct']:.2f}")
    print(f"Mnozniki nawierzchni: "
          + ", ".join(f"{k} {v:.2f}" for k, v in meta["surface_mult"].items()))
    print(f"Mnoznik hala: {meta['indoor_mult']:.2f}")
