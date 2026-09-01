"""
Sprawdza darmowy terminarz (Flashscore). Nie zuzywa zapytan RapidAPI.

    python diag_free.py
"""
import json

import fixtures_free as F

ev, msg = F.fetch_events(days_ahead=2, tours=("atp",), debug=True)
print(msg)
if not ev:
    raise SystemExit

print(f"\n=== pierwsze {min(12, len(ev))} meczow ===")
for e in ev[:12]:
    print(f"  {e['start'][:16]:16} {e['p1'][:22]:22} vs {e['p2'][:22]:22} "
          f"{e['court']:12} {e['tournament'][:24]}")

print("\n=== czy nazwiska pasuja do naszej bazy? ===")
try:
    import model as M
    P, MT, C, MA = M.load()
    names = sorted(P[P.matches >= 5].index.tolist())
    cache = {}
    ok = brak = 0
    przyklady = []
    for e in ev[:40]:
        for nm in (e["p1"], e["p2"]):
            m, conf = M.match_name(nm, names, cache)
            if m:
                ok += 1
            else:
                brak += 1
                if len(przyklady) < 8:
                    przyklady.append(nm)
    print(f"  dopasowano {ok}, nie dopasowano {brak}")
    if przyklady:
        print(f"  niedopasowane: {przyklady}")
except FileNotFoundError:
    print("  (brak bazy — pomijam)")
