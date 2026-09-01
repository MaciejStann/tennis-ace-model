"""
Tennis Ace Model — estymacja asow i podwojnych bledow w meczach ATP.

    python -m streamlit run app.py

Ten plik zawiera wylacznie start aplikacji i routing. Logika jest w:
    model.py       — estymacja asow i DF, H2H, dopasowanie nazwisk
    pointmodel.py  — model punktowy: zwyciezca, sety, tie-breaki, gemy
    fixtures.py    — terminarz z RapidAPI (zapasowy)
    fixtures_free.py — terminarz z Flashscore (glowny, darmowy)
    ui/            — warstwa prezentacji
"""
import streamlit as st

st.set_page_config(page_title="Tennis Ace Model", page_icon="🎾",
                   layout="wide", initial_sidebar_state="expanded")

import ui.stan as S          # noqa: E402  (po set_page_config)
from ui.nawigacja import init_stan   # noqa: E402

init_stan()

if not S.init():
    st.error("Brak bazy danych.")
    st.code("python build_db.py", language="powershell")
    st.stop()

S.zastosuj_css()

from ui.lista import view_list      # noqa: E402
from ui.mecz import view_detail     # noqa: E402

if st.session_state.view == "detail" and st.session_state.picked:
    view_detail()
else:
    view_list()

st.divider()
st.caption(
    f"Dane: TML-Database (CC BY-NC-SA), ATP {S.META['years'][0]}–"
    f"{S.META['years'][1]}. Terminarz: Flashscore. Model myli sie srednio "
    "o 2,6 asa. Nie zna formy dnia, kontuzji, pogody ani wysokosci nad "
    "poziomem morza. Wyliczenia maja charakter informacyjny.")
