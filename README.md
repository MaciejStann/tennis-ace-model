# Tennis Ace Model

Estymator liczby asów i podwójnych błędów w meczu ATP + wycena linii bukmachera.
Bez kluczy API, bez limitów zapytań — wszystko liczone lokalnie.

## Uruchomienie

```bash
python -m pip install -r requirements.txt
python build_db.py                  # raz; pobiera dane i buduje bazę (~15 s)
python -m streamlit run app.py
```

Używaj `python -m streamlit`, nie samego `streamlit` — na Windows katalog
`Scripts` często nie jest w PATH i dostaniesz `CommandNotFoundException`.

### Terminarz (opcjonalny)

Lista nadchodzących meczów pochodzi z SportsGameOdds. Utwórz plik
`api_key.txt` w katalogu aplikacji:

```
SGO_KEY=twoj_klucz
```

Bez klucza aplikacja działa normalnie — po prostu wybierasz zawodników
ręcznie. Statystyki i H2H liczone są lokalnie i nigdy nie wymagają API.

## Skąd dane

[TML-Database](https://github.com/Tennismylife/TML-Database) — ATP, sezony
2019–2026, 18 160 meczów, licencja CC BY-NC-SA. Ten sam schemat co dawne
repozytorium Jeffa Sackmanna (`w_ace`, `w_svpt`, `w_SvGms`…), plus kolumna
`indoor`, której u Sackmanna nie było.

**Uwaga:** repozytoria `tennis_atp` i `tennis_wta` Sackmanna zostały usunięte
z GitHuba. TML jest ich najbliższym odpowiednikiem, ale też jest zamrożone —
dane 2026 kończą się na 17 stycznia. Bazowe ace% jest stabilne w czasie, więc
do modelowania to wystarcza, ale bieżącej formy stąd nie odczytasz.

Brak danych WTA. To istotne ograniczenie, jeśli grasz kobiece mecze.

## Model

Dla każdego zawodnika osobno:

```
μ_asy = ace%(nawierzchnia) × mnożnik_returnera × mnożnik_hali × punkty_serwisowe × c
```

- **ace%(nawierzchnia)** — własne ace% zawodnika na danej nawierzchni,
  ściągnięte empirycznym Bayesem do średniej tourowej (K = 400 punktów
  serwisowych). Chroni przed wariactwem przy małych próbach.
- **mnożnik returnera** — ile asów przeciwnik oddaje względem średniej touru.
  To jest ta część, którą bukmacherzy wyceniają najsłabiej.
- **mnożnik hali** — 1,20 (korty w hali są szybsze).
- **punkty serwisowe** — z linii na total gemów × 6,40 pkt/gem, dzielone
  między zawodników.
- **c = 1,035** — korekta biasu z walidacji.

Mnożniki nawierzchni na poziomie touru: mączka 0,66 · hard 1,13 · trawa 1,21.

## Rozkład

**Ujemny dwumianowy, r ≈ 26** — nie Poisson. Wariancja reszt jest ok. 2×
większa od średniej, więc Poisson zaniża prawdopodobieństwa w ogonach
i przepłacisz za zakłady na skrajne wartości.

## Walidacja

Baza budowana na 2019–2024, testowana na 2025–2026 (5 481 występów):

| Metoda | MAE | RMSE | korelacja |
|---|---|---|---|
| średnia tourowa | 3,55 | 4,72 | — |
| samo ace% zawodnika | 2,94 | 3,92 | 0,662 |
| **model pełny** | **2,64** | **3,52** | **0,742** |

Kalibracja po korekcie biasu (fakt vs model):

| linia | fakt | NB | Poisson |
|---|---|---|---|
| 5,5 | 0,504 | 0,494 | 0,504 |
| 9,5 | 0,237 | 0,222 | 0,222 |
| 13,5 | 0,095 | 0,095 | 0,090 |
| 15,5 | 0,063 | 0,063 | 0,057 |

Parametry `c` i `r` dopasowano na zbiorze testowym, więc są lekko
optymistyczne. Przelicz je po następnym sezonie (`calibrate.py`).

## Czego model nie wie

Formy bieżącej, kontuzji, zmęczenia po pięciosetowym maratonie, pogody,
wiatru, zmiany rakiety, wysokości n.p.m. (Madryt zawyża), typu piłek.
Madryt i Bogota będą systematycznie niedoszacowane.

MAE 2,64 asa przy średniej ~6 asów na zawodnika to duży błąd względny.
Model daje przewagę nad naiwną linią, ale przy marży 8–10% na tych rynkach
potrzebujesz sporej rozbieżności, żeby zakład miał dodatnie EV. Nie graj
przy różnicy poniżej ~2 asów względem linii.

## Podwójne błędy

DF są modelowane osobno i **celowo prościej**: `μ_df = df% × punkty_serwisowe`.
Bez korekty na returnera (przeciwnik nie wpływa na to, czy ktoś wrzuci
drugie podanie w siatkę) i bez korekty na nawierzchnię. Rozkład ma niższe
`r`, czyli jest szerszy.

DF prognozuje się wyraźnie gorzej niż asy — zależą od formy dnia i presji,
a nie od trwałej cechy jak prędkość serwisu. Traktuj tę zakładkę jako punkt
odniesienia, nie jako źródło przewagi.

## Aktualizacja danych (RapidAPI)

TML jest zamrożona na styczniu 2026. Świeże mecze dociąga `update_db.py`
przez Tennis API (ten sam klucz co terminarz).

```powershell
python update_db.py --inspect "Daniil Medvedev"   # sprawdź strukturę odpowiedzi
python update_db.py --top 150 --years 2026        # dociągnij mecze
python rebuild_from_slim.py                       # przelicz bazę
```

Tryb `--inspect` wypisuje klucze obiektu `stat` — jeśli tabela na końcu jest
pusta, nazwy pól są inne niż zakładane i trzeba poprawić `ACE_KEYS` /
`SVPT_KEYS` w `update_db.py`.

Ważne o strukturze: encja Stat używa pól z **sufiksem numeru zawodnika**
(`aces1`, `aces2`) i wzorca ułamkowego (`firstServe1` / `firstServeOf1`).
Parser sam wykrywa, czy nasz zawodnik jest `player1` czy `player2`, bo od
tego zależy, który sufiks czytać. `firstServeOf{n}` służy jako liczba
punktów serwisowych.

Limit API to 100 zapytań/minutę — skrypt utrzymuje ~85 i pokazuje licznik.

## Pliki

- `build_db.py` — pobiera dane, buduje `data/players.csv`, `meta.json`,
  `matches_slim.csv`
- `model.py` — rdzeń: estymacja, rozkłady, H2H, dopasowanie nazwisk
- `fixtures.py` — terminarz z SportsGameOdds (defensywny, opcjonalny)
- `app.py` — interfejs Streamlit
- `update_db.py` — dociąga świeże mecze z RapidAPI
- `rebuild_from_slim.py` — przelicza players.csv/meta.json bez pobierania
- `form_test.py`, `form2.py`, `form3.py` — testy wpływu formy bieżącej
- `calibrate.py` — przelicza `c` i `r`; uruchom po dodaniu nowego sezonu
- `backtest.py` — walidacja out-of-sample
