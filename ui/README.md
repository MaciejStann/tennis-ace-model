# Narzędzia diagnostyczne

Uruchamiane rzadko, z katalogu głównego projektu:

```powershell
python tools/analysis.py       # wkład składników modelu, serie, trendy
python tools/backtest.py       # walidacja MAE out-of-sample
python tools/form_check.py     # wpływ formy in-sample
python tools/check_won.py      # spójność kolumny `won`
python tools/diag_free.py      # czy terminarz Flashscore działa
python tools/diag_fixtures.py  # czy RapidAPI odpowiada (~3 zapytania)
```

Usunięte jako jednorazowe (wyniki są w komentarzach kodu i KONTEKST.md):
`probe_fs.py`, `diag_zrodla.py`, `compare_k.py`, `form2.py`, `form3.py`,
`form_test.py`.
