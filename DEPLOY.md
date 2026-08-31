# Publikacja na Streamlit Community Cloud

Darmowe, bez karty. Aplikacja dostanie adres `*.streamlit.app`.

## 1. Repozytorium na GitHubie

Repo może być **prywatne** — Streamlit Cloud i tak je odczyta po
autoryzacji konta.

```powershell
cd C:\Users\Maciek\Desktop\tab
git init
git add .
git commit -m "Tennis Ace Model"
git branch -M main
git remote add origin https://github.com/TWOJ_LOGIN/tennis-ace-model.git
git push -u origin main
```

Przed pierwszym commitem sprawdź, czy klucz nie wchodzi do repo:

```powershell
git status --short
```

Na liście **nie może** być `api_key.txt` ani `.streamlit/secrets.toml`.
Oba są w `.gitignore`.

## 2. Co musi być w repo

- `app.py`, `model.py`, `fixtures.py` — aplikacja
- `requirements.txt` — zależności
- `.streamlit/config.toml` — motyw
- `data/players.csv`, `data/meta.json`, `data/calib.json`,
  `data/matches_slim.csv` — baza (~2,5 MB, mieści się bez problemu)

Skrypty pomocnicze (`build_db.py`, `update_db.py`, `calibrate.py` itd.)
uruchamiasz lokalnie; w repo mogą zostać, nie przeszkadzają.

## 3. Wdrożenie

1. Wejdź na https://share.streamlit.io i zaloguj się kontem GitHub.
2. **Create app** → wskaż repozytorium, gałąź `main`, plik `app.py`.
3. **Advanced settings → Secrets** — wklej klucz API:

   ```toml
   RAPID_KEY = "twoj_klucz"
   ```

   Bez tego terminarz nie zadziała, ale reszta aplikacji owszem.
4. **Deploy**. Pierwsze uruchomienie trwa 2–3 minuty.

## 4. Aktualizacja danych

Streamlit Cloud nie odświeży bazy sam — aktualizujesz lokalnie i wysyłasz:

```powershell
python update_db.py --top 150 --years 2026
python rebuild_from_slim.py
python calibrate.py
git add data/
git commit -m "Aktualizacja danych"
git push
```

Aplikacja przeładuje się automatycznie po pushu.

## O czym warto wiedzieć

- **Aplikacja jest publiczna.** Każdy z linkiem ją otworzy. Prywatny dostęp
  wymaga planu płatnego.
- **Usypianie.** Po kilku dniach bez ruchu aplikacja zasypia; pierwsze
  wejście budzi ją w ~30 sekund.
- **Limit RapidAPI jest dzienny i wspólny.** Każde otwarcie terminarza przez
  dowolnego użytkownika zużywa 2 zapytania z twojej puli. Przy publicznym
  adresie warto to obserwować.
- **Zasoby.** 1 GB RAM. Baza waży 2,5 MB i jest cache'owana, więc mieścisz
  się z zapasem.
