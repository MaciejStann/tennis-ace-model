"""
Podglad surowego feedu Flashscore — zeby dopasowac parser do kodow pol.

    python probe_fs.py
"""
import requests

H = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"),
     "x-fsign": "SW9D1eZo"}
URL = "https://local-global.flashscore.ninja/2/x/feed/f_2_0_3_pl_1"

r = requests.get(URL, headers=H, timeout=25)
print(f"HTTP {r.status_code}, {len(r.content)} B\n")
txt = r.text

# feed to rekordy rozdzielone ~, pola rozdzielone ¬, pary KOD÷wartosc
rek = txt.split("~")
print(f"rekordow: {len(rek)}\n")

print("=== pierwsze 3 naglowki turniejow (ZA) ===")
n = 0
for r_ in rek:
    if r_.startswith("ZA÷"):
        print("  " + r_.split("¬")[0][3:])
        n += 1
        if n >= 3:
            break

print("\n=== pierwszy rekord meczu (AA) — WSZYSTKIE pola ===")
for r_ in rek:
    if r_.startswith("AA÷"):
        for pole in r_.split("¬"):
            if "÷" in pole:
                k, v = pole.split("÷", 1)
                print(f"  {k:6} = {v[:60]}")
        break

print("\n=== ile meczow w feedzie ===")
print(f"  rekordow AA (mecze): {sum(1 for x in rek if x.startswith('AA÷'))}")
print(f"  rekordow ZA (turnieje): {sum(1 for x in rek if x.startswith('ZA÷'))}")
