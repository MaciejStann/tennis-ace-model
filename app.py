"""
Tennis Ace Model — estymacja asów i podwójnych błędów w meczach ATP.

    python -m streamlit run app.py

Logika obliczeń jest w model.py, terminarz w fixtures.py. Ten plik to
wyłącznie interfejs.
"""
import datetime as dt
import re

import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as sst

import model as M
from fixtures import fetch_events

st.set_page_config(page_title="Tennis Ace Model", page_icon="🎾",
                   layout="wide", initial_sidebar_state="expanded")

# Minimalny CSS: zwężenie odstępów, żeby tabele i metryki nie rozjeżdżały
# strony. Celowo bez selektorów klasowych Streamlita, które zmieniają się
# między wersjami.
# Dwie palety: jasna (mączka w słońcu) i ciemna (kort po zmroku).
# Wybór trzymamy w session_state — CSS wstrzykujemy raz, na górze skryptu,
# a przełącznik w sidebarze wywołuje przeładowanie.
LIGHT = {
    "BG": "#F8FAFC", "PANEL": "#FFFFFF", "SIDE": "#EEF4FA",
    "TEXT": "#16202B", "INK": "#6B7A8A", "LINE": "#DCE6F0",
    "CLAY": "#2E7FD4",        # błękit kortu — akcent
    "CLAY_DEEP": "#1B4F8A",   # duże płaszczyzny
    "CLAY_DIM": "#9DC2E8",
    "CLAY_SOFT": "#E7F1FB",
    "SUN": "#F2A93B",         # ciepły kontrapunkt
    "GOOD": "#2E9E6B", "GOOD_SOFT": "#E4F5EC",
    "BAD": "#DB5B4E", "BAD_SOFT": "#FDEBE8",
    "HARD": "#2E7FD4",
}
DARK = {
    "BG": "#0E141C", "PANEL": "#18212C", "SIDE": "#131B24",
    "TEXT": "#E8EEF5", "INK": "#8B9CAE", "LINE": "#26323F",
    "CLAY": "#57A0E8", "CLAY_DEEP": "#12395F", "CLAY_DIM": "#6F9BC4",
    "CLAY_SOFT": "#17293C",
    "SUN": "#F0B45C",
    "GOOD": "#4FBE8B", "GOOD_SOFT": "#152A22",
    "BAD": "#E8776A", "BAD_SOFT": "#2B1B1A",
    "HARD": "#57A0E8",
}

T = DARK if st.session_state.get("dark_mode") else LIGHT
BG, PANEL, SIDE = T["BG"], T["PANEL"], T["SIDE"]
TEXT, INK, LINE = T["TEXT"], T["INK"], T["LINE"]
CLAY, CLAY_DEEP, CLAY_DIM, CLAY_SOFT = (T["CLAY"], T["CLAY_DEEP"],
                                        T["CLAY_DIM"], T["CLAY_SOFT"])
GOOD, GOOD_SOFT, BAD, BAD_SOFT = (T["GOOD"], T["GOOD_SOFT"],
                                  T["BAD"], T["BAD_SOFT"])
SUN = T["SUN"]
SURFACE_COLOR = {"Hard": T["HARD"], "Clay": "#C9683F", "Grass": GOOD}

st.markdown(f"""
<style>
  /* nadpisujemy motyw z config.toml, zeby przelacznik dzialal w locie */
  .stApp, [data-testid="stAppViewContainer"] {{
      background: {BG}; color: {TEXT}; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {{
      color: inherit; }}
  h1, h2, h3, h4 {{ color: {TEXT}; }}

  .block-container {{ padding-top: 2.4rem; max-width: 1100px; }}
  html, body, [class*="css"] {{ -webkit-font-smoothing: antialiased; }}
  h1 {{ font-weight: 640; letter-spacing: -.026em; font-size: 2rem;
        margin: 0 0 .2rem; line-height: 1.18; }}
  hr {{ border-color: {LINE}; }}

  .eyebrow {{ font-size: .68rem; letter-spacing: .15em;
              text-transform: uppercase; color: {CLAY}; font-weight: 700;
              margin: 1.8rem 0 .7rem; }}
  .sub {{ font-size: .82rem; color: {INK}; line-height: 1.6; }}
  .lead {{ font-size: .95rem; color: {INK}; line-height: 1.6;
           margin: .2rem 0 1.6rem; }}

  /* blok koloru: zaokraglony, w rytmie tresci, nie na pelna szerokosc */
  .hero {{ background: linear-gradient(135deg, {CLAY_DEEP}, {CLAY});
           color:#F2F8FF; border-radius: 18px;
           padding: 1.5rem 1.7rem; margin: .2rem 0 1.6rem; }}
  .hero-lg {{ padding: 2.1rem 2rem 1.9rem; }}
  .hero h1.big {{ font-size: 2.1rem; }}
  .hero-stats {{ display:flex; gap:2.2rem; margin-top:1.3rem;
                 padding-top:1.1rem; border-top:1px solid rgba(255,255,255,.18); }}
  .hero-stat b {{ display:block; font-size:1.35rem; font-weight:650;
                  letter-spacing:-.02em; color:#FFFFFF; line-height:1.1; }}
  .hero-stat span {{ font-size:.7rem; letter-spacing:.1em;
                     text-transform:uppercase; color:{CLAY_DIM}; }}
  .band {{ background:{CLAY_SOFT}; border:1px solid {CLAY_DIM};
           border-radius:16px; padding:1.1rem 1.3rem; margin:.2rem 0 1rem; }}
  .pcard {{ background:{PANEL}; border:1px solid {LINE}; border-radius:16px;
            padding:.9rem 1.1rem; }}
  .pcard b {{ font-size:1rem; }}
  .pill {{ display:inline-block; padding:.12rem .55rem; border-radius:999px;
           font-size:.68rem; font-weight:700; margin-left:.4rem; }}
  .hero h1 {{ color:#FFFFFF; margin:0 0 .2rem; font-size:1.65rem; }}
  .hero .eyebrow {{ color:{CLAY_DIM}; margin:0 0 .4rem; }}
  .hero .lead {{ color:#D9E9FA; margin:0; max-width:44rem; font-size:.88rem; }}

  .card {{ background: {PANEL}; border: 1px solid {LINE};
           border-radius: 16px; padding: 1.1rem 1.25rem;
           margin-bottom: .7rem; }}
  .pick {{ border-radius: 16px; padding: 1.15rem 1.3rem; height: 100%;
           border: 1px solid {LINE}; background: {PANEL}; }}
  .pick-good {{ border: 1px solid {GOOD}; background: {GOOD_SOFT}; }}
  .pick-bad {{ background: {PANEL}; }}
  .pick-head {{ display:flex; justify-content:space-between;
                align-items:center; margin-bottom:.9rem; }}
  .pick-side {{ font-size:1.05rem; font-weight:700; letter-spacing:-.01em; }}
  .pick-ev {{ font-size:2.1rem; font-weight:660; letter-spacing:-.03em;
              font-variant-numeric: tabular-nums; line-height:1;
              margin-bottom:.55rem; }}
  .pick-note {{ font-size:.82rem; color:{INK}; line-height:1.6; }}
  .pick-foot {{ margin-top:.9rem; padding-top:.75rem;
                border-top:1px solid {LINE}; font-size:.82rem; }}

  .row {{ display:flex; justify-content:space-between;
          align-items:baseline; gap:1rem; }}
  .tag {{ display:inline-block; padding:.22rem .7rem; border-radius:999px;
          font-size:.66rem; font-weight:700; letter-spacing:.09em;
          text-transform:uppercase; }}
  .tag-sun {{ background:{SUN}; color:#3A2A0C; }}
  .stat {{ display:flex; justify-content:space-between; align-items:baseline;
           padding:.5rem 0; border-bottom:1px solid {LINE};
           font-variant-numeric: tabular-nums; font-size:.92rem; }}
  .stat:last-child {{ border-bottom:none; padding-bottom:0; }}

  div[data-testid="stMetric"] {{ background:{PANEL}; border:1px solid {LINE};
      border-radius:16px; padding:.9rem 1.1rem; }}
  div[data-testid="stMetricValue"] {{ font-size:1.9rem; font-weight:640;
      letter-spacing:-.03em; font-variant-numeric:tabular-nums;
      color:{TEXT}; }}
  div[data-testid="stMetricLabel"] {{ font-size:.7rem; color:{INK};
      text-transform:uppercase; letter-spacing:.1em; font-weight:700; }}

  div[role="radiogroup"] {{ gap:.4rem; }}
  div[role="radiogroup"] label {{ border:1px solid {LINE};
      border-radius:999px; padding:.3rem .9rem; margin:0; background:{PANEL};
      transition:border-color .12s, background .12s; }}
  div[role="radiogroup"] label:hover {{ border-color:{CLAY}; }}
  div[role="radiogroup"] label > div:first-child {{ display:none; }}
  div[role="radiogroup"] label:has(input:checked) {{
      border-color:{CLAY}; background:{CLAY_SOFT}; font-weight:650;
      color:{CLAY}; }}

  /* Streamlit rysuje ramke focusa na zakladkach — kasujemy ja na wszystkich
     stanach i warstwach, razem z pseudo-elementami. */
  [data-testid="stTabs"] button,
  [data-baseweb="tab-list"] button,
  button[data-baseweb="tab"] {{
      font-size:.9rem; font-weight:600; color:{TEXT};
      outline:0 !important; box-shadow:none !important;
      border:0 !important; }}
  [data-testid="stTabs"] button:focus,
  [data-testid="stTabs"] button:focus-visible,
  [data-testid="stTabs"] button:active,
  [data-testid="stTabs"] button:hover {{
      outline:0 !important; box-shadow:none !important;
      border:0 !important; background:transparent !important; }}
  [data-testid="stTabs"] button::before,
  [data-testid="stTabs"] button::after {{ display:none !important; }}
  [data-baseweb="tab-list"] {{ gap:1.4rem; border:0 !important; }}
  div[data-baseweb="tab-highlight"] {{ background-color:{CLAY}; }}
  div[data-baseweb="tab-border"] {{ background-color:{LINE}; }}
  *:focus, *:focus-visible {{ outline:none !important; }}
  .stButton button:focus {{ box-shadow:none !important; }}

  section[data-testid="stSidebar"] {{ border-right:none; background:{SIDE}; }}
  section[data-testid="stSidebar"] * {{ color:{TEXT}; }}
  section[data-testid="stSidebar"] h3 {{ margin:1.5rem 0 .4rem;
      font-size:.68rem; letter-spacing:.14em; text-transform:uppercase;
      color:{CLAY}; font-weight:700; }}
  section[data-testid="stSidebar"] .card {{ border-color:{CLAY_DIM}; }}

  div[data-testid="stExpander"] details {{ border:1px solid {LINE};
      border-radius:16px; background:{PANEL}; }}
  .stButton button {{ border-radius:12px; font-weight:600;
      border:1px solid {LINE}; background:{PANEL}; color:{TEXT}; }}
  .stButton button:hover {{ border-color:{CLAY}; color:{CLAY}; }}
  div[data-testid="stNumberInput"] input,
  div[data-baseweb="select"] > div {{ background:{PANEL}; color:{TEXT}; }}
</style>
""", unsafe_allow_html=True)


def color_delta(value: float, _unused: bool = True, unit: str = "") -> str:
    """Plus zielony, minus czerwony — bez odwracania znaczenia."""
    col = "inherit" if abs(value) < 1e-9 else (GOOD if value > 0 else BAD)
    return (f"<span style='color:{col};font-weight:650'>"
            f"{value:+.2f}{unit}</span>")


# =============================================================== dane

@st.cache_data(show_spinner="Wczytuję bazę…")
def load_all():
    return M.load()


try:
    PLAYERS, META, CALIB, MATCHES = load_all()
except FileNotFoundError:
    st.error("Brak bazy danych.")
    st.code("python build_db.py", language="powershell")
    st.stop()

NAMES = sorted(PLAYERS[PLAYERS.matches >= 5].index.tolist())
MATCH_COUNT = PLAYERS.matches.to_dict()

DEFAULTS = {
    "view": "list", "picked": None, "ctx": {}, "namecache": {},
    "fx_days": 2, "fx_token": 0,
    "hide_low": True, "both_only": False, "newest": False,
    # klucze ustawiane w trakcie nawigacji — deklarujemy je tutaj, żeby
    # `.get()` w losowym miejscu nie trafiał na brak
    "origin": "fixtures", "match_key": "", "dark_mode": False,
    "list_mode": "Terminarz ATP",
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

GRAND_SLAMS = ("us open", "australian open", "wimbledon",
               "roland garros", "french open")
ROUNDS = {"F": "Finał", "SF": "Półfinał", "QF": "Ćwierćfinał", "R16": "1/8",
          "R32": "1/16", "R64": "1/32", "R128": "1/64", "RR": "Grupa",
          "BR": "O 3. miejsce", "Q1": "Kwalifikacje", "Q2": "Kwalifikacje",
          "Q3": "Kwalifikacje"}


def infer_best_of(tournament: str, rank_name: str) -> tuple[int, str]:
    """Wielki Szlem = bo5. Interpunkcja z API bywa różna („U.S. Open")."""
    blob = re.sub(r"[^a-z0-9]+", " ", f"{tournament} {rank_name}".lower())
    compact = blob.replace(" ", "")
    if "grandslam" in compact:
        return 5, "ranga: Grand Slam"
    for gs in GRAND_SLAMS:
        if gs.replace(" ", "") in compact:
            return 5, f"turniej: {gs.title()}"
    if "daviscup" in compact:
        return 5, "Puchar Davisa"
    return 3, ""


def default_games(best_of: int, surface: str) -> float:
    table = META.get("avg_games", {}).get(str(best_of), {})
    return float(table.get(surface) or table.get("_all")
                 or (35.6 if best_of == 5 else 22.8))


def surface_from_court(court: str) -> tuple[str | None, bool]:
    c = (court or "").lower()
    surf = next((s for w, s in (("clay", "Clay"), ("grass", "Grass"),
                                ("hard", "Hard"), ("carpet", "Hard"))
                 if w in c), None)
    return surf, ("indoor" in c or c.startswith("i."))


def data_age_days() -> int:
    raw = str(META.get("last_match_date") or "")
    if len(raw) != 8:
        return 0
    return (dt.date.today()
            - dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))).days


def pl_date(x) -> str:
    s = str(int(x))
    return f"{s[6:]}.{s[4:6]}.{s[:4]}"


def open_match(name1: str, name2: str, ctx: dict | None = None,
               origin: str = "fixtures"):
    """Przełącza na widok analizy. Klucz meczu izoluje stan widgetów."""
    st.session_state.picked = (name1, name2)
    st.session_state.ctx = ctx or {}
    st.session_state.match_key = f"{name1}|{name2}|{(ctx or {}).get('start', '')}"
    st.session_state.origin = origin
    st.session_state.view = "detail"
    st.rerun()


# =============================================================== widok listy

@st.cache_data(ttl=3600, show_spinner="Pobieram terminarz…")
def _fetch_cached(days: int, token: int):
    return fetch_events(days_ahead=days, tours=("atp",))


def get_events(days: int, token: int):
    """
    Cache'ujemy WYŁĄCZNIE udane pobranie. Wcześniej pusty wynik (wyczerpany
    limit dzienny) siedział w cache przez godzinę — po odnowieniu limitu
    aplikacja nadal pokazywała błąd, choć API już działało.
    """
    events, msg = _fetch_cached(days, token)
    if not events:
        _fetch_cached.clear()
    return events, msg


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


def sidebar_list():
    with st.sidebar:
        st.markdown("<div class='eyebrow'>Tennis Ace Model</div>",
                    unsafe_allow_html=True)
        age = data_age_days()
        raw = str(META.get("last_match_date") or "")
        st.markdown(
            f"<div class='band' style='margin-top:.4rem'>"
            f"<div class='stat'><span class='sub'>Mecze</span>"
            f"<span>{META['n_matches']:,}</span></div>"
            f"<div class='stat'><span class='sub'>Zawodnicy</span>"
            f"<span>{len(PLAYERS)}</span></div>"
            f"<div class='stat'><span class='sub'>Dane do</span>"
            f"<span>{pl_date(raw) if len(raw) == 8 else '—'}</span></div>"
            f"</div>".replace(",", " "), unsafe_allow_html=True)

        if age > 45:
            with st.expander(f"Dane sprzed {age} dni"):
                st.caption("Skuteczność serwisu zmienia się powoli, więc model "
                           "wciąż działa — ale nie zna ostatnich meczów.")
                st.code("python update_db.py --top 150\n"
                        "python rebuild_from_slim.py\n"
                        "python calibrate.py", language="powershell")

        st.markdown("### Jak to działa")
        st.markdown(
            "<div class='sub'>Model bierze zwykłą skuteczność serwisu "
            "zawodnika na danej nawierzchni, poprawia ją o to, jak dobrze "
            "przeciwnik odbiera, i mnoży przez długość meczu.</div>",
            unsafe_allow_html=True)
        theme_switch()


def view_list():
    sidebar_list()
    raw = str(META.get("last_match_date") or "")
    st.markdown(
        f"<div class='hero hero-lg'>"
        f"<div class='eyebrow'>ATP · asy i podwójne błędy</div>"
        f"<h1 class='big'>Tennis Ace Model</h1>"
        f"<div class='lead'>Ile asów poda zawodnik w nadchodzącym meczu — "
        f"i czy linia bukmachera to dobrze wycenia.</div>"
        f"<div class='hero-stats'>"
        f"<div class='hero-stat'><b>{META['n_matches']:,}</b>"
        f"<span>meczów</span></div>"
        f"<div class='hero-stat'><b>{len(PLAYERS)}</b>"
        f"<span>zawodników</span></div>"
        f"<div class='hero-stat'><b>{META['years'][0]}–{META['years'][1]}</b>"
        f"<span>sezony</span></div>"
        f"<div class='hero-stat'><b>{pl_date(raw) if len(raw) == 8 else '—'}"
        f"</b><span>dane do</span></div>"
        f"</div></div>".replace(",", " "), unsafe_allow_html=True)

    MODES = ["Terminarz ATP", "Wybór ręczny"]
    if st.session_state.pop("goto_manual", False):
        st.session_state.list_mode = MODES[1]
    st.session_state.setdefault("list_mode", MODES[0])
    mode = st.radio("Widok", MODES, horizontal=True, key="list_mode",
                    label_visibility="collapsed")

    # ---------------------------------------------------- wybór ręczny
    if mode == MODES[1]:
        st.caption("Zacznij pisać nazwisko, żeby znaleźć zawodnika.")

        c1, c2 = st.columns(2)
        s1 = c1.selectbox("Zawodnik 1", NAMES, key="man1")
        rest = [n for n in NAMES if n != s1]
        s2 = c2.selectbox("Zawodnik 2", rest, index=min(1, len(rest) - 1),
                          key="man2")

        # karty zamiast jednej dlugiej linii — przy dwoch ostrzezeniach
        # tekst zlewal sie w nieczytelny ciag
        pc = st.columns(2, gap="medium")
        for col, nm in zip(pc, (s1, s2)):
            cnt = MATCH_COUNT.get(nm, 0)
            if cnt >= 25:
                pill = (f"<span class='pill' style='background:{GOOD_SOFT};"
                        f"color:{GOOD}'>dość danych</span>")
            else:
                pill = (f"<span class='pill' style='background:{BAD_SOFT};"
                        f"color:{BAD}'>mało danych</span>")
            col.markdown(
                f"<div class='pcard'><b>{nm}</b>{pill}"
                f"<div class='sub' style='margin-top:.25rem'>"
                f"{cnt:.0f} meczów w bazie</div></div>",
                unsafe_allow_html=True)

        st.write("")
        if st.button("Analizuj", type="primary", key="man_go"):
            open_match(s1, s2, origin="manual")

    # ---------------------------------------------------- terminarz
    if mode == MODES[0]:
        top = st.columns([3, 1, 4])
        days = top[0].select_slider("Zakres dni", options=[1, 2, 3, 5, 7],
                                    value=st.session_state.fx_days,
                                    format_func=lambda d: f"{d} dni",
                                    key="fx_days_w")
        # Zapytanie idzie tylko po kliknięciu — plan ma limit dzienny,
        # a suwak przy każdym ruchu paliłby kolejne wywołania.
        if top[1].button("Odśwież", use_container_width=True):
            st.session_state.fx_days = days
            st.session_state.fx_token += 1
            st.rerun()
        if days != st.session_state.fx_days:
            top[2].caption("Zmieniono zakres — kliknij **Odśwież**.")

        events, msg = get_events(st.session_state.fx_days,
                                 st.session_state.fx_token)

        if not events:
            st.markdown(
                f"<div class='band'>"
                f"<b>Terminarz niedostępny</b>"
                f"<div class='sub' style='margin-top:.3rem'>"
                f"Analiza działa bez niego — wystarczy wybrać zawodników "
                f"samemu. Wszystko liczy się na twoim komputerze.</div></div>",
                unsafe_allow_html=True)
            if st.button("Wybierz zawodników", type="primary"):
                st.session_state.goto_manual = True
                st.rerun()
            with st.expander("Szczegóły błędu"):
                st.caption(msg)
                if st.button("Sprawdź połączenie"):
                    st.code(fetch_events(days_ahead=st.session_state.fx_days,
                                         tours=("atp",), debug=True)[1])
            return

        cache = st.session_state.namecache
        for e in events:
            e["m1"], e["c1"] = M.match_name(e["p1"], NAMES, cache)
            e["m2"], e["c2"] = M.match_name(e["p2"], NAMES, cache)
            e["known"] = sum(1 for k in ("m1", "m2") if e[k])
            e["n1"], e["n2"] = e["m1"] or e["p1"], e["m2"] or e["p2"]
            e["conf"] = min(e["c1"] or 1, e["c2"] or 1)

        f = st.columns(3)
        hide_low = f[0].checkbox(
            "Tylko ATP Tour", value=st.session_state.hide_low,
            key="hide_low", help="Ukrywa Challengery i ITF.")
        both_only = f[1].checkbox("Obaj znani w bazie",
                                  value=st.session_state.both_only,
                                  key="both_only")
        newest = f[2].checkbox("Od najpóźniejszych",
                               value=st.session_state.newest, key="newest")

        shown = events
        if hide_low:
            filtered = [e for e in shown if e.get("rank_id") not in (0, 1)]
            if filtered or all(e.get("rank_id") is None for e in shown):
                shown = filtered or shown
        if both_only:
            shown = [e for e in shown if e["known"] == 2]
        shown = [e for e in shown if e["known"] >= 1 and e["n1"] != e["n2"]]
        shown.sort(key=lambda e: e.get("start") or "9999", reverse=newest)

        st.caption(f"{len(shown)} z {len(events)} meczów po filtrach")
        if not shown:
            st.info("Brak meczów spełniających filtry — odznacz "
                    "„Obaj znani w bazie” albo zwiększ zakres dni.")
            return

        by_tour: dict[str, list] = {}
        for e in shown:
            by_tour.setdefault(e.get("tournament") or "Turniej nieznany",
                               []).append(e)
        order = sorted(by_tour.items(),
                       key=lambda kv: min(x.get("start") or "9999"
                                          for x in kv[1]), reverse=newest)

        for tname, group in order:
            rank = group[0].get("rank_name") or ""
            head = f"{tname} · {len(group)}" + (f" · {rank}" if rank else "")
            with st.expander(head, expanded=len(order) <= 4):
                for e in group:
                    render_row(e)


def render_row(e):
    c_name, c_meta, c_btn = st.columns([6, 3, 2])
    n1 = e["n1"] + ("" if e["m1"] else " ⚠")
    n2 = e["n2"] + ("" if e["m2"] else " ⚠")
    c_name.markdown(f"**{n1}** vs **{n2}**")

    bits = [e.get("court", ""), (e.get("start") or "")[:16].replace("T", " ")]
    c_meta.caption(" · ".join(b for b in bits if b) or "—")
    notes = []
    if e["known"] < 2:
        notes.append("brak danych o 1 zawodniku")
    if e["conf"] < 0.9:
        notes.append("dopasowanie przybliżone")
    if notes:
        c_meta.caption("⚠ " + ", ".join(notes))

    if c_btn.button("Analizuj", key=f"go_{e['id']}", use_container_width=True):
        surf, indoor = surface_from_court(e.get("court", ""))
        bo, why = infer_best_of(e.get("tournament", ""), e.get("rank_name", ""))
        open_match(e["n1"], e["n2"],
                   {"surface": surf, "indoor": indoor, "best_of": bo,
                    "best_of_why": why, "tournament": e.get("tournament", ""),
                    "rank_name": e.get("rank_name", ""),
                    "start": e.get("start", "")})


# =============================================================== widok meczu

def sidebar_detail(ctx: dict, mkey: str) -> dict:
    """Ustawienia meczu. Zwraca słownik parametrów."""
    with st.sidebar:
        back_label = ("← Wybór zawodników"
                      if st.session_state.get("origin") == "manual"
                      else "← Lista meczów")
        if st.button(back_label, use_container_width=True, key="back_side"):
            go_back()

        st.markdown("### Warunki meczu")
        surfaces = ["Hard", "Clay", "Grass"]
        auto = ctx.get("surface")
        surface = st.selectbox(
            "Nawierzchnia", surfaces,
            index=surfaces.index(auto) if auto in surfaces else 0,
            key=f"surf_{mkey}")
        indoor = st.checkbox("Hala", value=bool(ctx.get("indoor")),
                             key=f"ind_{mkey}",
                             help=f"Mnożnik {META['indoor_mult']:.2f} — "
                                  "w hali serwuje się nieco łatwiej.")
        auto_bo = int(ctx.get("best_of") or 3)
        best_of = st.radio(
            "Format", [3, 5], horizontal=True,
            index=1 if auto_bo == 5 else 0, key=f"bo_{mkey}",
            format_func=lambda b: "do 2 setów" if b == 3 else "do 3 setów")
        if ctx.get("best_of_why"):
            st.caption(f"Wykryto bo{auto_bo} — {ctx['best_of_why']}")

        st.markdown("### Długość meczu")
        dflt = default_games(best_of, surface)
        gkey, pkey = f"games_{mkey}", f"games_prev_{mkey}"
        # Klucz nie zalezy od formatu ani nawierzchni, wiec recznie wpisana
        # wartosc przezywa ich zmiane. Ale gdy uzytkownik NIC nie wpisal,
        # wartosc musi podazac za domyslna — inaczej przelaczenie bo3/bo5
        # nie zmienialoby niczego w wynikach.
        if gkey not in st.session_state:
            st.session_state[gkey] = dflt
            st.session_state[pkey] = dflt
        prev = st.session_state.get(pkey, dflt)
        untouched = abs(st.session_state[gkey] - prev) < 0.01
        if untouched and abs(prev - dflt) > 0.01:
            st.session_state[gkey] = dflt
        st.session_state[pkey] = dflt

        total_games = st.number_input(
            "Linia bukmachera na total gemów", 12.0, 70.0, step=0.5,
            key=gkey, format="%.1f")
        touched = abs(total_games - dflt) > 0.01
        cc = st.columns([3, 2])
        cc[0].caption(f"Typowo przy bo{best_of} na {surface.lower()}: "
                      f"{dflt:.1f}")
        if touched and cc[1].button("Domyślna", use_container_width=True):
            st.session_state[gkey] = dflt
            st.session_state[pkey] = dflt
            st.rerun()
        if not touched:
            st.markdown(
                f"<div class='sub' style='color:{CLAY}'>"
                f"To średnia, nie prognoza tego meczu. Wpisz linię bukmachera "
                f"— inaczej wynik może być zawyżony lub zaniżony o ¼.</div>",
                unsafe_allow_html=True)

        split = st.slider(
            "Podział gemów serwisowych (%)", 44, 56, 50, key=f"sp_{mkey}",
            help="W danych 90% meczów mieści się w 47–53%.") / 100

        with st.expander("Zaawansowane"):
            bankroll = st.number_input("Bankroll", 100.0, 1e6, 5000.0, 100.0,
                                       key=f"bk_{mkey}")
            kfrac = st.slider("Ułamek Kelly'ego", 0.05, 1.0, 0.25, 0.05,
                              key=f"kf_{mkey}")
            nb_r = st.number_input("Dyspersja NB (r)", 5.0, 100.0,
                                   float(CALIB["nb_r"]), 1.0, key=f"nb_{mkey}")
            st.caption("Stawka jest ograniczona do 10% bankrolla niezależnie "
                       "od ułamka Kelly'ego.")
        theme_switch()

    return {"surface": surface, "indoor": indoor, "best_of": best_of,
            "total_games": total_games, "split": split, "bankroll": bankroll,
            "kfrac": kfrac, "nb_r": nb_r}


def market_block(mu: float, key: str, r: float, bankroll: float,
                 kfrac: float, mkey_for_sens: str = ""):
    """Linia, kursy, EV, Kelly i rozkład dla jednego rynku."""
    c = st.columns(3, gap="medium")
    raw_line = c[0].number_input(
        "Linia", 0.5, 60.5, float(np.floor(mu) + 0.5), 0.5,
        key=f"l_{key}", format="%.1f")
    # Linie totali sa polowkowe (8.5, 9.5, 10.5) — przy calkowitej wynik
    # rowny linii oznacza zwrot stawki, czego model nie liczy. Przyciagamy
    # wiec do najblizszej polowki.
    line = round(raw_line - 0.5) + 0.5
    line = min(max(line, 0.5), 60.5)
    if abs(line - raw_line) > 1e-9:
        c[0].caption(f"Zaokrąglono do {line:g}")
    o_ov = c[1].number_input("Kurs OVER", 1.01, 20.0, 1.90, 0.01,
                             key=f"ov_{key}")
    o_un = c[2].number_input("Kurs UNDER", 1.01, 20.0, 1.90, 0.01,
                             key=f"un_{key}")

    po = M.p_over(line, mu, r)
    devig = 1 / o_ov + 1 / o_un

    sides = []
    for side, word, prob, odds in (("OVER", "powyżej", po, o_ov),
                                   ("UNDER", "poniżej", 1 - po, o_un)):
        ev = prob * odds - 1
        sides.append({
            "side": side, "word": word, "prob": prob, "odds": odds, "ev": ev,
            "market": 1 / odds / devig,
            "stake": M.kelly(prob, odds, kfrac) * bankroll,
        })
    best = max(sides, key=lambda x: x["ev"])

    st.write("")
    cols = st.columns(2, gap="medium")
    for col, sd in zip(cols, sides):
        win = sd["ev"] > 0.02
        cls = "pick pick-good" if win else "pick pick-bad"
        verdict = ("Graj" if win else
                   "Odpuść" if sd["ev"] <= 0 else "Za mała przewaga")
        tag_bg, tag_fg = ((GOOD_SOFT, GOOD) if win else (BAD_SOFT, BAD))
        ev_col = GOOD if sd["ev"] > 0 else BAD
        foot = (f"Sugerowana stawka <b>{sd['stake']:,.0f}</b>".replace(",", " ")
                if win else "Bez stawki")
        col.markdown(
            f"<div class='{cls}'>"
            f"  <div class='pick-head'>"
            f"    <span class='pick-side'>{sd['side']} {line:g}</span>"
            f"    <span class='tag' style='background:{tag_bg};"
            f"color:{tag_fg}'>{verdict}</span>"
            f"  </div>"
            f"  <div class='pick-ev' style='color:{ev_col}'>"
            f"{100 * sd['ev']:+.1f}%</div>"
            f"  <div class='pick-note'>"
            f"    Model: <b>{100 * sd['prob']:.0f}%</b> szans &nbsp;·&nbsp; "
            f"    bukmacher: {100 * sd['market']:.0f}% &nbsp;·&nbsp; "
            f"    kurs {sd['odds']:.2f}"
            f"  </div>"
            f"  <div class='pick-foot sub'>{foot}</div>"
            f"</div>", unsafe_allow_html=True)

    st.write("")
    if best["ev"] > 0.02:
        st.markdown(
            f"<div class='band' style='background:{GOOD_SOFT};"
            f"border-color:{GOOD}'>"
            f"<b style='color:{GOOD}'>{best['side']} {line:g}</b> "
            f"<span class='sub'>wygląda na niedowartościowane o "
            f"{100 * best['ev']:.1f}%. To przewaga oczekiwana, nie pewny "
            f"zakład.</span></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='band'><span class='sub'>Brak przewagi po żadnej "
            f"stronie. Marża bukmachera "
            f"{100 * (devig - 1):.1f}%.</span></div>",
            unsafe_allow_html=True)
    st.write("")

    with st.expander("Co jeśli mecz potrwa inaczej"):
        st.markdown(
            "<div class='sub'>Długość meczu to największa niewiadoma: "
            "w danych łączna liczba gemów ma odchylenie <b>8,4 przy średniej "
            "25</b>, a siła zawodników prawie tego nie przewiduje. Poniżej "
            "widać, jak prognoza i wycena zmieniają się, gdy mecz okaże się "
            "krótszy lub dłuższy niż zakładasz.</div>",
            unsafe_allow_html=True)
        st.write("")
        base_g = st.session_state.get(f"games_{mkey_for_sens}", 22.8)
        rows = []
        for delta, lab in ((-6, "bardzo krótki"), (-3, "krótszy"),
                           (0, "jak ustawiłeś"), (3, "dłuższy"),
                           (6, "bardzo długi")):
            g = base_g + delta
            if g < 10:
                continue
            mu_g = mu * g / base_g
            po_g = M.p_over(line, mu_g, r)
            ev_ov = po_g * o_ov - 1
            ev_un = (1 - po_g) * o_un - 1
            best_side = "OVER" if ev_ov >= ev_un else "UNDER"
            best_ev = max(ev_ov, ev_un)
            rows.append({
                "Gemy": f"{g:.1f}",
                "Scenariusz": lab,
                "Prognoza": f"{mu_g:.1f}",
                f"P(over {line:g})": f"{100 * po_g:.0f}%",
                "Lepsza strona": best_side,
                "EV": f"{100 * best_ev:+.1f}%",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)
        sides = {r_["Lepsza strona"] for r_ in rows}
        if len(sides) > 1:
            st.markdown(
                f"<div class='sub' style='color:{BAD}'><b>Uwaga:</b> przy "
                f"innej długości meczu opłacalna strona się zmienia. "
                f"Ten zakład jest wrażliwy na długość — bez linii bukmachera "
                f"na total gemów lepiej odpuścić.</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='sub' style='color:{GOOD}'>Ta sama strona "
                f"wygrywa w każdym scenariuszu — wycena jest odporna na "
                f"niepewność co do długości meczu.</div>",
                unsafe_allow_html=True)

    with st.expander("Rozkład prawdopodobieństwa"):
        rr, pp = M.nb(mu, r)
        xs = np.arange(0, int(mu * 2.5) + 6)
        st.bar_chart(pd.DataFrame({"liczba": xs,
                                   "p": sst.nbinom.pmf(xs, rr, pp)})
                     .set_index("liczba"), height=200)
        lo, hi = sst.nbinom.ppf([0.1, 0.9], rr, pp)
        st.caption(f"Mediana {sst.nbinom.ppf(0.5, rr, pp):.0f} · "
                   f"przedział 80%: {lo:.0f}–{hi:.0f} · rozkład ujemny "
                   f"dwumianowy, r={r:.0f}")


def stat_tab(kind: str, p1: str, p2: str, e1: dict, e2: dict, cfg: dict,
             mkey: str):
    field = "mu_ace" if kind == "ace" else "mu_df"
    label = "asy" if kind == "ace" else "podwójne błędy"
    both = e1["known"] and e2["known"]
    total = (e1[field] + e2[field]) if both else None
    r = cfg["nb_r"] if kind == "ace" else max(cfg["nb_r"] * 0.35, 3.0)

    st.markdown(f"<div class='eyebrow' style='margin-top:.4rem'>"
                f"Przewidywane {label}</div>", unsafe_allow_html=True)
    c = st.columns(3, gap="medium")
    for col, nm, e in zip(c, (p1, p2), (e1, e2)):
        col.metric(nm.split()[-1],
                   f"{e[field]:.1f}" if e["known"] else "—")
    c[2].metric("Razem", f"{total:.1f}" if both else "—")

    opts = {}
    if both:
        opts["Obaj razem"] = total
    for nm, e in ((p1, e1), (p2, e2)):
        if e["known"]:
            opts[nm] = e[field]
    if not opts:
        st.info("Brak danych o obu zawodnikach — nie ma czego wyceniać. "
                "Wybierz zawodników z bazy w zakładce „Wybór ręczny”.")
        return

    st.markdown("<div class='eyebrow'>Wycena linii bukmachera</div>"
                "<div class='sub' style='margin:-.35rem 0 .5rem'>"
                "Wybierz rynek, potem wpisz linię i kursy z oferty.</div>",
                unsafe_allow_html=True)
    choice = st.radio("Rynek", list(opts), horizontal=True,
                      key=f"mkt_{kind}_{mkey}", label_visibility="collapsed")
    st.markdown(f"<div class='sub'>Prognoza modelu dla wybranego rynku: "
                f"<b>{opts[choice]:.1f}</b> — to wartość oczekiwana, "
                f"dlatego nie jest połówkowa.</div>",
                unsafe_allow_html=True)
    # Klucz musi zawierac WYBRANY rynek — inaczej pole "Linia" zostawaloby
    # przy wartosci z poprzedniego rynku, mimo ze mu jest inne.
    slot = list(opts).index(choice)
    market_block(opts[choice], f"{kind}_{slot}_{mkey}", r, cfg["bankroll"],
                 cfg["kfrac"], mkey)

    known = [(nm, e) for nm, e in ((p1, e1), (p2, e2)) if e["known"]]
    with st.expander("Skąd się bierze ta liczba"):
        cols = st.columns(len(known), gap="medium") if known else []
        for col, (nm, e) in zip(cols, known):
            if kind == "ace":
                items = [
                    ("Mecze w bazie", f"{e['n']}"),
                    ("Asy na 100 podań", f"{100 * e['ace_overall']:.1f}"),
                    (f"…na nawierzchni {cfg['surface'].lower()}",
                     f"{100 * e['ace']:.1f}"),
                    ("Poprawka na returnera", f"×{e['ret_mult']:.2f}"),
                    ("Poprawka na halę", f"×{e['indoor_mult']:.2f}"),
                    ("Podań w meczu", f"{e['svpt']:.0f}"),
                ]
            else:
                items = [
                    ("Mecze w bazie", f"{e['n']}"),
                    ("Błędy na 100 podań", f"{100 * e['df_overall']:.1f}"),
                    ("Podań w meczu", f"{e['svpt']:.0f}"),
                ]
            rows = "".join(
                f"<div class='stat'><span class='sub'>{k}</span>"
                f"<span>{v}</span></div>" for k, v in items)
            col.markdown(
                f"<div class='card'><b>{nm}</b>{rows}"
                f"<div class='stat' style='border-top:1px solid {LINE};"
                f"margin-top:.2rem;padding-top:.5rem'>"
                f"<span class='sub'>Wynik</span>"
                f"<span style='color:{CLAY};font-weight:650'>"
                f"{e[field]:.1f}</span></div></div>",
                unsafe_allow_html=True)

        if kind == "ace":
            st.caption(
                "Skuteczność serwisu na tej nawierzchni razy poprawka na to, "
                "jak przeciwnik odbiera, razy poprawka na halę, razy liczba "
                "punktów przy serwisie. Umiejętności returnowe przeciwnika "
                "poprawiają trafność najbardziej ze wszystkich składników.")
            if any(e["known"] and not e["ret_known"] for e in (e1, e2)):
                st.caption("⚠ Mnożnik returnera 1,00 znaczy, że **nie mam "
                           "danych** o przeciwniku — a nie, że jest przeciętny.")
        else:
            used = [(nm, e["form"]["df"]) for nm, e in known
                    if e.get("form", {}).get("df")]
            st.caption(
                "Skuteczność razy liczba punktów przy serwisie. Bez poprawki "
                "na przeciwnika — to, czy ktoś wrzuci drugie podanie w siatkę, "
                "nie zależy od tego, kto stoi po drugiej stronie. Podwójne "
                "błędy są mniej przewidywalne niż asy.")
            if used:
                for nm, fi in used:
                    st.caption(
                        f"Dla **{nm}** wzięta pod uwagę forma z ostatnich "
                        f"{fi['n']} meczów (od {pl_date(fi['since'])}). "
                        "Sprawdziłem na danych, że przy podwójnych błędach "
                        "to pomaga.")
            else:
                st.caption("Forma nie jest brana pod uwagę. Uruchom "
                           "`python oos_check.py`, żeby sprawdzić, czy "
                           "pomogłaby na twoich danych.")


def surface_of(cfg: dict) -> str:
    return {"Hard": "hard", "Clay": "mączka", "Grass": "trawa"}.get(
        cfg["surface"], cfg["surface"].lower())


def h2h_tab(p1: str, p2: str, e1: dict, e2: dict, cfg: dict, mkey: str):
    games = M.h2h_list(MATCHES, p1, p2)

    if not games:
        st.info("Ci zawodnicy nie grali ze sobą w meczu ATP Tour.")
    else:
        st.markdown(f"<div class='eyebrow'>Mecze między sobą · "
                    f"{len(games)}</div>", unsafe_allow_html=True)

        if len(games) == 1:
            m = games[0]
        else:
            def label(g):
                w = (g["stats"].get(p1) or {}).get("won")
                sc = g["score"] if w is not False else M.flip_score(g["score"])
                bits = [g["date_str"], g["tournament"] or "?",
                        ROUNDS.get(g["round"], g["round"]), sc]
                return " · ".join(b for b in bits if b)

            idx = st.selectbox("Mecz", range(len(games)),
                               format_func=lambda i: label(games[i]),
                               key=f"h2h_{mkey}", label_visibility="collapsed")
            m = games[idx]

        s1, s2 = m["stats"][p1], m["stats"][p2]
        w1 = (s1 or {}).get("won")
        sc = (m["score"] if w1 is not False
              else M.flip_score(m["score"])) if m["score"] else ""
        scol = SURFACE_COLOR.get(m["surface"], T["HARD"])

        # --- blok 1: gdzie i kiedy ---
        meta_bits = [m["tournament"], ROUNDS.get(m["round"], m["round"]),
                     m["date_str"]]
        st.markdown(
            f"<div class='band'>"
            f"<div class='row'><span><b>{m['tournament'] or 'Turniej'}</b>"
            f" &nbsp;<span class='sub'>"
            f"{' · '.join(b for b in meta_bits[1:] if b)}</span></span>"
            f"<span class='tag' style='background:{scol};color:#fff'>"
            f"{m['surface']}{' · hala' if m['indoor'] else ''}</span></div>"
            f"</div>", unsafe_allow_html=True)

        # --- blok 2: kto wygral i jakim wynikiem ---
        def nm_fmt(nm, won):
            return (f"<b style='font-size:1.05rem'>{nm}</b>" if won
                    else f"<span style='color:{INK}'>{nm}</span>")

        st.markdown(
            f"<div class='card' style='border-left:4px solid {CLAY}'>"
            f"<div class='row'>"
            f"<span style='font-size:1.02rem'>{nm_fmt(p1, w1 is not False)}"
            f" <span class='sub'>vs</span> {nm_fmt(p2, w1 is not True)}</span>"
            f"<span style='font-weight:650;font-variant-numeric:tabular-nums'>"
            f"{sc}</span></div>"
            f"<div class='sub' style='margin-top:.3rem'>Pogrubiony wygrał"
            f"</div></div>", unsafe_allow_html=True)

        # --- blok 3: serwis w tym meczu, zawodnik obok zawodnika ---
        st.markdown("<div class='eyebrow' style='margin-top:.6rem'>"
                    "Serwis w tym meczu</div>", unsafe_allow_html=True)
        cc = st.columns(2, gap="medium")
        for col, nm, sd in zip(cc, (p1, p2), (s1, s2)):
            with col:
                if not sd:
                    st.markdown(f"<div class='card'><b>{nm}</b>"
                                f"<div class='sub'>brak statystyk</div></div>",
                                unsafe_allow_html=True)
                    continue
                lines = [f"<div class='card'><b>{nm}</b>"]
                for metric, lab, good in (("ace", "Asy", True),
                                          ("df", "Podwójne błędy", False)):
                    avg = M.career_rate(MATCHES, nm, metric, m["surface"])
                    right = f"<b>{sd[metric]:.0f}</b>"
                    if avg is not None:
                        right += ("&nbsp;&nbsp;"
                                  + color_delta(sd[metric] - avg, good)
                                  + f" <span class='sub'>(zwykle "
                                    f"{avg:.1f})</span>")
                    lines.append(f"<div class='stat'><span class='sub'>{lab}"
                                 f"</span><span>{right}</span></div>")
                lines.append(f"<div class='stat'><span class='sub'>Gemy przy "
                             f"serwisie</span><span>{sd['svgms']:.0f}</span>"
                             f"</div></div>")
                st.markdown("".join(lines), unsafe_allow_html=True)

        st.caption(f"Porównanie z tym, ile ten zawodnik podaje zwykle na "
                   f"nawierzchni {m['surface'].lower()}. "
                   "**Model nie bierze H2H pod uwagę** — kilka meczów to za "
                   "mało, żeby cokolwiek z nich wnioskować.")

        totals, n = M.h2h_totals(MATCHES, p1, p2)
        if n > 1:
            with st.expander(f"Średnia ze wszystkich {n} spotkań"):
                cc2 = st.columns(2, gap="medium")
                for col, nm in zip(cc2, (p1, p2)):
                    if nm not in totals.columns:
                        continue
                    rows = "".join(
                        f"<div class='stat'><span class='sub'>{r['Metryka']}"
                        f"</span><span>{r[nm]:.2f}</span></div>"
                        for _, r in totals.iterrows())
                    col.markdown(f"<div class='card'><b>{nm}</b>{rows}</div>",
                                 unsafe_allow_html=True)

    st.divider()
    st.markdown("<div class='eyebrow'>Jak często przekraczali linię</div>",
                unsafe_allow_html=True)
    st.markdown(
        "<div class='sub'>Element informacyjny — <b>model tego nie używa</b>. "
        "Sprawdziłem na danych: seria pokryć nie przewiduje kolejnego meczu. "
        "Efekt, który wygląda na passę, znika po uwzględnieniu tego, że model "
        "systematycznie zaniża albo zawyża konkretnych zawodników.</div>",
        unsafe_allow_html=True)
    st.write("")

    c = st.columns([2, 2, 3])
    metric_lab = c[0].radio("Metryka", ["Asy", "Podwójne błędy"],
                            horizontal=True, key=f"srmet_{mkey}",
                            label_visibility="collapsed")
    metric = "ace" if metric_lab == "Asy" else "df"
    win_n = c[1].radio("Okno", [5, 10, 20], horizontal=True,
                       key=f"srwin_{mkey}", label_visibility="collapsed",
                       format_func=lambda n: f"ost. {n}")
    only_surf = c[2].checkbox(f"Tylko {surface_of(cfg)}", key=f"srsurf_{mkey}")

    for nm, e in ((p1, e1), (p2, e2)):
        if not e["known"]:
            continue
        res = M.last_results(MATCHES, nm, metric, win_n,
                             cfg["surface"] if only_surf else None)
        if not res:
            st.caption(f"{nm}: brak meczów w bazie.")
            continue
        # linia domyslna: tam, gdzie ustawilby ja bukmacher dla tego zawodnika
        mu_p = e["mu_ace"] if metric == "ace" else e["mu_df"]
        line_p = float(np.floor(mu_p) + 0.5)
        hits = sum(1 for x in res if x["value"] > line_p)
        vals = " ".join(
            f"<span style='color:{GOOD if x['value'] > line_p else INK};"
            f"font-weight:600'>{x['value']:.0f}</span>" for x in res)
        st.markdown(
            f"<div class='card'>"
            f"<div class='row'><b>{nm}</b>"
            f"<span>powyżej {line_p:g} w <b>{hits}</b> z {len(res)}</span>"
            f"</div>"
            f"<div class='sub' style='margin-top:.45rem;font-size:1rem;"
            f"letter-spacing:.08em'>{vals}</div>"
            f"<div class='sub' style='margin-top:.35rem'>"
            f"najnowsze po lewej · {res[-1]['date_str']} – "
            f"{res[0]['date_str']}</div></div>",
            unsafe_allow_html=True)

    st.divider()
    st.markdown("<div class='eyebrow'>Forma — ostatnie mecze</div>",
                unsafe_allow_html=True)
    win = (CALIB.get("form", {}).get("df") or {}).get("window", 10)
    for nm, e in ((p1, e1), (p2, e2)):
        if not e["known"]:
            continue
        cols = st.columns(2, gap="medium")
        for col, metric, lab, prior, base in (
                (cols[0], "ace", "ace%", META["tour_ace_pct"], e["ace"]),
                (cols[1], "df", "df%", META["tour_df_pct"], e["df_overall"])):
            rate, cnt, since = M.recent_rate(MATCHES, nm, metric, win, prior)
            if rate is None:
                col.caption(f"{nm} — {lab}: brak danych")
                continue
            diff = 100 * (rate - base)
            col.metric(f"{nm} — {lab} z {cnt} ost.", f"{100 * rate:.2f}%")
            arrow = "wyżej" if diff > 0 else "niżej"
            # przy asach wiecej = lepiej dla serwujacego, przy DF odwrotnie
            col.markdown(
                f"<span class='sub'>{color_delta(diff, metric == 'ace', ' pp')}"
                f" {arrow} niż zwykle · od {pl_date(since)}</span>",
                unsafe_allow_html=True)
    st.caption(
        "**Przy asach forma nie ma znaczenia** — sprawdziłem to na danych "
        "i nie poprawia prognozy. Skuteczność serwisu to cecha stała: zależy "
        "od wzrostu i techniki, a te nie zmieniają się z tygodnia na tydzień. "
        "Przy podwójnych błędach forma działa i model ją uwzględnia.")


def view_detail():
    p1, p2 = st.session_state.picked
    ctx = st.session_state.ctx
    mkey = st.session_state.get("match_key", f"{p1}|{p2}")
    cfg = sidebar_detail(ctx, mkey)

    head = [ctx.get("tournament", ""), ctx.get("rank_name", ""),
            f"bo{cfg['best_of']}", f"{cfg['total_games']:.1f} gemów",
            (ctx.get("start") or "")[:16].replace("T", " ")]

    top_back = ("← Wróć do wyboru zawodników"
                if st.session_state.get("origin") == "manual"
                else "← Wróć do listy meczów")
    if st.button(top_back, key="back_top"):
        go_back()

    st.markdown(
        f"<div class='hero'>"
        f"<div class='eyebrow'>Analiza meczu</div>"
        f"<h1>{p1} <span style='opacity:.55;font-weight:400'>vs</span> "
        f"{p2}</h1>"
        f"<div class='lead' style='margin-top:.2rem'>"
        f"<span class='tag' style='background:rgba(255,255,255,.16);"
        f"color:#FFF3EC'>{cfg['surface']}"
        f"{' · hala' if cfg['indoor'] else ''}</span>"
        f"&nbsp;&nbsp;{' · '.join(h for h in head if h)}</div>"
        f"</div>", unsafe_allow_html=True)

    svpt = cfg["total_games"] * META["pts_per_service_game"]
    e1 = M.estimate(PLAYERS, META, CALIB, p1, p2, cfg["surface"],
                    cfg["indoor"], svpt * cfg["split"], MATCHES)
    e2 = M.estimate(PLAYERS, META, CALIB, p2, p1, cfg["surface"],
                    cfg["indoor"], svpt * (1 - cfg["split"]), MATCHES)

    # Blokujące ostrzeżenia zostają na wierzchu, resztę chowamy —
    # przy kilku naraz zalewały ekran i nikt ich nie czytał.
    unknown = [n for n, e in ((p1, e1), (p2, e2)) if not e["known"]]
    if unknown:
        st.error(
            f"Nie mam danych o zawodniku: **{', '.join(unknown)}**. "
            "Nie policzę dla niego nic ani nie podam sumy z obu zawodników. "
            "Zwykle chodzi o gracza z Challengerów albo ITF.")

    minor = []
    thin = [n for n, e in ((p1, e1), (p2, e2)) if e["known"] and e["n"] < 25]
    if thin:
        minor.append(f"**Mało meczów w bazie:** {', '.join(thin)}. "
                     "Prognoza jest przez to przesunięta w stronę przeciętnego "
                     "zawodnika i mniej pewna.")
    if e1["known"] and not e1["ret_known"] or e2["known"] and not e2["ret_known"]:
        minor.append("**Nie znam przeciwnika.** Nie wiem, jak dobrze odbiera "
                     "serwis, więc pomijam tę poprawkę — a to najmocniejsza "
                     "część modelu.")
    if data_age_days() > 45:
        minor.append(f"**Dane sprzed {data_age_days()} dni.** Model nie zna "
                     "meczów z ostatnich tygodni.")
    if minor:
        with st.expander(f"Zastrzeżenia do tej estymacji ({len(minor)})"):
            for m in minor:
                st.markdown("- " + m)

    t1, t2, t3 = st.tabs(["Asy", "Podwójne błędy", "H2H i forma"])
    with t1:
        stat_tab("ace", p1, p2, e1, e2, cfg, mkey)
    with t2:
        stat_tab("df", p1, p2, e1, e2, cfg, mkey)
    with t3:
        h2h_tab(p1, p2, e1, e2, cfg, mkey)


# =============================================================== router

if st.session_state.view == "detail" and st.session_state.picked:
    view_detail()
else:
    view_list()

st.divider()
st.caption(
    f"Dane: TML-Database (CC BY-NC-SA), ATP {META['years'][0]}–"
    f"{META['years'][1]}. Terminarz: Tennis API. Model myli się średnio "
    "o 2,6 asa. Nie zna formy dnia, kontuzji, pogody ani wysokości nad "
    "poziomem morza. Wyliczenia mają charakter informacyjny.")
