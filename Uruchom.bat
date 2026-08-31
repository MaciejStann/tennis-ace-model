@echo off
title Tennis Ace Model
echo Sprawdzanie bibliotek...
python -m pip install -r requirements.txt
echo.
echo Uruchamianie aplikacji...
python -m streamlit run app.py
pause
