"""Routing miedzy widokami i stan sesji."""
import streamlit as st

# Tylko klucze, ktorymi zarzadzamy SAMI. Widgety z wlasnym `key`
# (hide_low, both_only, newest, dark_mode, list_mode) trzymaja swoj stan
# same — deklarowanie ich tutaj i podawanie `value=` naraz wywoluje
# ostrzezenie Streamlita o podwojnym zrodle prawdy.
DEFAULTS = {
    "view": "list", "picked": None, "ctx": {}, "namecache": {},
    "fx_days": 2, "fx_token": 0,
    "origin": "fixtures", "match_key": "",
}


def init_stan():
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


def open_match(name1: str, name2: str, ctx: dict | None = None,
               origin: str = "fixtures"):
    """Przełącza na widok analizy. Klucz meczu izoluje stan widgetów."""
    st.session_state.picked = (name1, name2)
    st.session_state.ctx = ctx or {}
    st.session_state.match_key = f"{name1}|{name2}|{(ctx or {}).get('start', '')}"
    st.session_state.origin = origin
    st.session_state.view = "detail"
    st.rerun()


def go_back():
    """Powrót na listę, do zakładki, z której przyszedł użytkownik."""
    if st.session_state.get("origin") == "manual":
        st.session_state.list_mode = "Wybór ręczny"
    st.session_state.view = "list"
    st.session_state.picked = None
    st.rerun()


def theme_switch():
    """Przełącznik motywu. Widget zapisuje do session_state, a przeładowanie
    strony wstrzykuje CSS z odpowiedniej palety."""
    st.markdown("### Wygląd")
    st.toggle("Tryb ciemny", key="dark_mode")
