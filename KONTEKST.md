# Tennis Ace Model — kontekst projektu

Aplikacja Streamlit przewidująca liczbę asów, podwójnych błędów i przebieg
meczu ATP (zwycięzca, wynik w setach, tie-breaki, gemy), wyceniająca na tej
podstawie linie bukmacherskie. Ma rejestr zakładów do sprawdzenia, czy
model faktycznie zarabia.

- **Online:** tennis-ace-model.streamlit.app
- **Repo:** github.com/MaciejStann/tennis-ace-model (publiczne)
- **Katalog:** `C:\Users\Maciek\Desktop\tab`

---

# KOMENDY

## Codzienne

```powershell
# uruchomienie (pierwszy start 5-10 s — import Streamlita, nie błąd)
python -m streamlit run app.py

# testy — po KAŻDEJ zmianie w kodzie
python -m pytest
```

## Aktualizacja danych

Pełny cykl, w tej kolejności:

```powershell
python update_db.py --z-terminarza --years 2026   # ~60-77 zapytań
python rebuild_from_slim.py                        # przelicz statystyki
python calibrate.py                                # przelicz kalibrację
python check_data.py                               # kontrola spójności
git add . ; git commit -m "Aktualizacja danych" ; git push
```

Warianty pobierania:

```powershell
python update_db.py --top 150 --years 2026        # top N zamiast terminarza
python update_db.py --top 150 --active-days 250   # ostrzejszy próg aktywności
python update_db.py --inspect "Carlos Alcaraz"    # surowa odpowiedź API
```

**Uwaga na limit:** plan BASIC to **500 zapytań MIESIĘCZNIE**, nie dziennie.
Terminarz nic nie kosztuje (Flashscore). Jedno zapytanie na zawodnika przy
pełnym cache ID (`data/player_ids.json`), trzy przy nowym.

## Budowa bazy od zera

```powershell
python build_db.py            # z plików data/tml*.csv
python migrate_serve.py       # kolumny serwisowe (model punktowy)
python fix_won.py             # napraw `won`, jeśli ma wartości -1
python rebuild_from_slim.py
python calibrate.py
```

## Walidacja i diagnostyka

```powershell
python backtest_walk.py         # backtest krocz-przez-czas, model vs ranking
python validate_point.py        # walidacja modelu punktowego
python oos_check.py             # czy forma pomaga (zapisuje do calib.json)
python tools/analysis.py        # wkład składników, overdyspersja
python tools/backtest.py        # MAE out-of-sample
python tools/check_won.py       # spójność kolumny `won`
python tools/diag_free.py       # czy Flashscore odpowiada
python tools/diag_fixtures.py   # czy RapidAPI żyje (~3 zapytania)
```

## Git

```powershell
git status --short              # przed commitem: czy nie wchodzi api_key.txt
git checkout -b poprawki        # pracuj na gałęzi, main = wersja publiczna
git checkout -- ui/mecz.py      # cofnij zmiany w pliku
git reset --soft HEAD~1         # cofnij commit, zachowaj zmiany
```

---

# STRUKTURA

| Plik | Linie | Rola |
|---|---|---|
| `app.py` | 43 | start i routing |
| `ui/stan.py` | 373 | paleta, CSS — **cały CSS tutaj** |
| `ui/lista.py` | 338 | terminarz, wybór ręczny, rejestr |
| `ui/mecz.py` | 847 | cztery zakładki analizy |
| `ui/rejestr_widok.py` | 109 | widok rejestru zakładów |
| `ui/pomocnicze.py` | 53 | daty, linie, wykrywanie formatu |
| `ui/nawigacja.py` | 51 | stan sesji, przejścia |
| `model.py` | 464 | estymacja asów i DF, H2H, nazwiska |
| `pointmodel.py` | 342 | zwycięzca, sety, tie-breaki, gemy |
| `rejestr.py` | 121 | zapis i rozliczanie zakładów |
| `tools/` | | diagnostyka, uruchamiana rzadko |
| `tests/` | | 71 testów, bez sieci i klucza API |

Moduły `ui/` sięgają po wspólny stan przez `import ui.stan as S`.

---

# MODEL

## Asy i podwójne błędy

```
μ_asy = ace%(nawierzchnia) × mnożnik_returnera × mnożnik_hali
        × punkty_serwisowe × calib_c
μ_df  = df% × punkty_serwisowe × calib_c_df    (+ blend z formą)
```

Rozkład **ujemny dwumianowy** (wariancja ≈ 2× średnia, overdyspersja 1,97).
Regularyzacja: **K = 800** globalnie, **400** dla nawierzchni.
MAE out-of-sample **2,62 asa**. Siła returnu przeciwnika to najmocniejszy
składnik (+7%).

## Model punktowy

Z `p_serve` liczy analitycznie gem → tie-break → set → mecz.
Parametry po ablacji: `SHRINK_PTS = 2000`, `PROB_SCALE = 0,75`,
`GAMES_SCALE = 0,90`, `RANK_BLEND`. **`SHRINK_SURF` usunięty** — osobny
parametr dla nawierzchni dawał 0,6378 wobec 0,6377 bez niego.

Wkład parametrów (log loss out-of-sample, n = 6122):

| wyłączony | strata |
|---|---|
| RANK_BLEND | +3,19% |
| PROB_SCALE | +0,77% |
| SHRINK_PTS | +0,21% |
| SHRINK_SURF | −0,09% (usunięty) |

Backtest krocz-przez-czas, 5 sezonów, n ≈ 27 000:

| | log loss | trafność |
|---|---|---|
| model punktowy | 0,650 | 60,6% |
| sam ranking | 0,666 | 63,0% |
| **połączone** | **0,639** | 63,2% |

Poziom gema bardzo dobry (błąd do 0,009). Wynik w setach **zaniża
rozstrzygalność** (2:0 model 43%, fakt 52%), tie-break **zawyża** (50%
vs 40%) — skutek założenia niezależności punktów.

Modele nie kłócą się ze sobą: korelacja długości meczu z ace% wynosi +0,08.

---

# DANE

- **TML-Database** — ATP 2019–2026. Licencja **CC BY-NC-SA: zakaz użytku
  komercyjnego.** Repozytoria Sackmanna usunięte, TML jest następcą.
- **RapidAPI Tennis API** — świeże mecze. **500 zapytań miesięcznie.**
- **Flashscore** — terminarz, darmowy, bez limitu.
  `local-global.flashscore.ninja/2/x/feed/f_2_0_3_pl_1`, nagłówek
  `x-fsign: SW9D1eZo`. Format: rekordy `~`, pola `¬`, pary `KOD÷wartość`.
  Kody: `ZA` turniej (z nawierzchnią), `AA` mecz, `AD` czas UTC,
  `AB` status (1 = zaplanowany), `WU`/`WV` nazwiska „nazwisko-imię".
  **Sofascore i ESPN blokują po IP — sprawdzone, nie próbuj.**

`data/matches_slim.csv` (~37 tys. wierszy) to format **long**: wiersz =
występ jednego zawodnika, mecz to dwa wiersze.
`data/zaklady.csv` — rejestr, w `.gitignore`, dane prywatne.

---

# ODRZUCONE HIPOTEZY

Dziewięć rzeczy sprawdzonych i odrzuconych. **Nie wracaj bez nowego
argumentu** — liczby są w komentarzach kodu.

| Hipoteza | Wynik |
|---|---|
| forma przy asach | +0,14% — szum |
| serie pokryć linii | +0,22% po kontroli na zawodnika |
| „gorąca ręka" | artefakt: r 0,16 → 0,07 po demeaningu |
| dni odpoczynku | niemonotoniczne |
| korekta biasu zawodnika | 0,83%, wymaga progu i ściągania |
| upodobanie do nawierzchni | trwałość tylko 0,285 |
| break pointy | trwałość 0,352 |
| forma wynikowa | mierzy to samo co ranking |
| H2H przy zwycięzcy | bez wpływu |

**Przetrwały dwie:** ranking (+3,3%) i forma przy DF (+4,8%).

**Elo** sprawdzone: log loss 0,632 (lepiej niż ranking 0,638), ale trafność
62,8% (gorzej niż 63,8%). Dodanie modelu punktowego do Elo **pogarsza**
wynik. Niewdrożone.

**Zawsze rób kontrolę na zawodnika** — odejmij jego średnią i sprawdź, czy
efekt przetrwał. Dwa razy uratowało to przed wdrożeniem artefaktu.

---

# PUŁAPKI

1. **Orientacja wyniku.** `score` zawsze z perspektywy zwycięzcy
   (`model.flip_score`).
2. **Zmienna zakłócona.** Mnożnik „hala" wynosił 1,20, bo 99% meczów
   halowych to hard. Po kontroli 1,04.
3. **Semantyka daty.** W TML `tourney_date` to data rozpoczęcia turnieju,
   w API data meczu. Klucz `(player, opp, tourney_date)` **nie jest
   unikalny**.
4. **Kolumna `won`.** `migrate_columns.py` wstawiał −1 jako „nieznane",
   co odwracało kalibrację. Naprawia `fix_won.py`.
5. **Klucze widgetów** muszą zawierać identyfikator meczu i rynek.
6. **Podwójne źródło prawdy.** Widget z `key` nie może dostawać `value=`
   ani być w `DEFAULTS`.
7. **Zakładek nie da się przełączać programowo** — lista używa `st.radio`.
8. **Obramowanie focusa** wyłączone na trzech poziomach selektorów.
9. **Linie muszą być połówkowe** (8,5 · 9,5).
10. **Brak danych ≠ średnia.** Nieznany zawodnik zwraca `None`.
11. **Terminarz** siedzi w `session_state["fx_cache"]`, pobiera się raz na
    sesję. Nieudane pobranie nie kasuje ostatniego dobrego wyniku.
12. **Markdown w blokach HTML nie działa** — używaj `<b>`, nie `**`.
13. **`st.expander` nie może być zagnieżdżony.**
14. **Paleta przeliczana w `zastosuj_css()`**, nie na poziomie modułu —
    moduł importuje się raz i motyw by zamarzł. Ta regresja już wystąpiła.
15. **`st.dataframe` renderuje się na płótnie** i ignoruje CSS. Używaj
    `tabela()` z `ui/mecz.py`.
16. **Motyw idzie przez `config.toml`.** Sekcje `[theme.light]`
    i `[theme.dark]`, przełącznik w menu Ustawień Streamlita, nasz CSS
    podąża przez `st.context.theme.type`. Własny przełącznik + 41 reguł
    `!important` nie działał — zostało 12 reguł, wszystkie udokumentowane.
17. **Pandas nie wstawi tekstu do pustej kolumny liczbowej.** W `rejestr.py`
    typy tekstowe wymuszone jawnie przy `read_csv`.

---

# OGRANICZENIA

Tylko ATP, brak WTA. Baza to ATP Tour — gracze z Challengerów mają mało
meczów albo brak. Model nie zna formy dnia, kontuzji, pogody, wysokości
n.p.m. (Madryt niedoszacowany).

**Największe źródło błędu to pole „linia na total gemów".** Liczba asów
skaluje się z długością meczu liniowo, a odchylenie długości to 8,4 gema
przy średniej 25. Wartość domyślna daje ±25% błędu — więcej niż cała
przewaga modelu. Siła zawodników prawie tego nie przewiduje (korelacja
−0,07). Stąd sekcja „Co jeśli mecz potrwa inaczej".

**Model nie bije rankingu w trafności.** Gdy zmienia typ względem rankingu,
ma rację w ~50%. Wartość leży w stopniowaniu pewności (log loss).

**Nie wiadomo jeszcze, czy model zarabia.** Cała walidacja mierzy dokładność
wobec rzeczywistości, nigdy wobec kursów. Od tego jest rejestr zakładów —
po około stu pozycjach porówna zakładane EV z faktycznym ROI.

---

# CO DALEJ

- **Zbierać dane w rejestrze.** Sto zakładów da pierwszą odpowiedź
  o rentowności. Wszystko inne jest wtórne wobec tego pytania.
- **Backtest 1/2 na kursach historycznych** — API zwraca `odd1`/`odd2`
  w `past-matches`, `update_db.py` ich nie zapisuje. Wymaga kwoty.
- **Automatyzacja** GitHub Actions. Wymaga decyzji, gdzie trzymać dane —
  2,5 MB CSV przy codziennych commitach rozdmucha historię repo.
- **Notebook z analizą** do portfolio.

---

# ZASADY PRACY

- **Weryfikuj kodem i danymi.** Nie ufaj temu plikowi — uruchamiaj to,
  co zmieniasz.
- **Nie zmieniaj liczb modelu** bez walidacji out-of-sample. Poprawa
  poniżej 1% nie uzasadnia nowego parametru — sprawdzone trzykrotnie.
- **Nie usuwaj funkcji bez pytania.** Zgłoszenie usterki to prośba
  o naprawę, nie o wycięcie. To się już zdarzyło.
- **Zachowaj ostrzeżenia merytoryczne.** „Forma nie wchodzi do modelu
  asów", „model nie używa H2H", „mnożnik returnera 1,00 to brak danych",
  „przy tej próbie prognoza to średnia tourowa" są wynikiem walidacji.
  Formę można zmieniać, sens nie.
- **Nie ukrywaj niepewności.**
- **KISS.** Dziewięć odrzuconych hipotez i jeden usunięty parametr
  pokazują, że sygnał jest cienki, a komplikowanie zwykle dokłada szum.
- **Cały CSS w `ui/stan.py`.** Bez nowych zależności.
- Po każdej zmianie: `python -m pytest` (71 testów) i uruchomienie.
- Pracuj na gałęzi — push na `main` przeładowuje publiczną aplikację.
