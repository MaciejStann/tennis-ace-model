"""
Wspolny stan aplikacji: wczytana baza, paleta kolorow, CSS.

Wszystkie moduly widokow importuja stad przez `import ui.stan as S`,
dzieki czemu nie ma zmiennych globalnych rozsianych po plikach ani
importow cyklicznych.
"""
import datetime as dt
import json

import pandas as pd
import streamlit as st

import model as M

# wypelniane przez init() na starcie aplikacji
PLAYERS = META = CALIB = MATCHES = None
NAMES: list = []
MATCH_COUNT: dict = {}


@st.cache_data(show_spinner="Wczytuje baze...")
def _load():
    return M.load()


@st.cache_data(show_spinner="Przygotowuje model meczu...")
def _load_point_cached(znacznik: str):
    """
    Cache po znaczniku bazy, nie po globalnej MATCHES. Wczesniej funkcja
    czytala globalna zmienna w momencie wywolania przez cache Streamlita,
    kiedy ta mogla byc jeszcze None — na Streamlit Cloud konczylo sie to
    AttributeError.
    """
    return M.load_point_rates(MATCHES)


def load_point():
    if MATCHES is None:
        return None, None
    znacznik = f"{len(MATCHES)}|{int(MATCHES.tourney_date.max())}"
    return _load_point_cached(znacznik)


@st.cache_data(show_spinner=False)
def last_ranks():
    """Ranking: najpierw swiezy z current_ranks.json, potem z bazy meczow."""
    out = {}
    if MATCHES is not None and "rank" in MATCHES.columns:
        m = MATCHES.dropna(subset=["rank"]).sort_values("tourney_date")
        out = m.groupby("player")["rank"].last().to_dict()
    path = M.DATA / "current_ranks.json"
    if path.exists():
        try:
            for nm, v in json.loads(path.read_text()).items():
                if isinstance(v, dict) and v.get("rank"):
                    out[nm] = float(v["rank"])
        except ValueError:
            pass
    return out


def init() -> bool:
    """Wczytuje baze. False, gdy jej nie ma."""
    global PLAYERS, META, CALIB, MATCHES, NAMES, MATCH_COUNT
    try:
        PLAYERS, META, CALIB, MATCHES = _load()
    except FileNotFoundError:
        return False
    NAMES = sorted(PLAYERS.index.tolist())
    MATCH_COUNT = PLAYERS.matches.to_dict()
    return True


# Dwie palety: jasna (mączka w słońcu) i ciemna (kort po zmroku).
# Wybór trzymamy w session_state — CSS wstrzykujemy raz, na górze skryptu,
# a przełącznik w sidebarze wywołuje przeładowanie.
LIGHT = {
    "BG": "#F8FAFC", "PANEL": "#FFFFFF", "SIDE": "#EEF4FA",
    "TEXT": "#16202B", "INK": "#556270", "LINE": "#DCE6F0",
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
    "TEXT": "#E8EEF5", "INK": "#9AAABB", "LINE": "#2B3846",
    "CLAY": "#57A0E8", "CLAY_DEEP": "#12395F", "CLAY_DIM": "#6F9BC4",
    "CLAY_SOFT": "#17293C",
    "SUN": "#F0B45C",
    "GOOD": "#4FBE8B", "GOOD_SOFT": "#152A22",
    "BAD": "#E8776A", "BAD_SOFT": "#2B1B1A",
    "HARD": "#57A0E8",
}

# UWAGA: modul importuje sie RAZ, wiec wybor palety nie moze zostac tutaj.
# Po podziale na moduly ciemny motyw przestal dzialac wlasnie dlatego —
# `zastosuj_css()` przelicza go teraz przy kazdym przebiegu skryptu.
T = LIGHT
BG, PANEL, SIDE = T["BG"], T["PANEL"], T["SIDE"]
TEXT, INK, LINE = T["TEXT"], T["INK"], T["LINE"]
CLAY, CLAY_DEEP, CLAY_DIM, CLAY_SOFT = (T["CLAY"], T["CLAY_DEEP"],
                                        T["CLAY_DIM"], T["CLAY_SOFT"])
GOOD, GOOD_SOFT, BAD, BAD_SOFT = (T["GOOD"], T["GOOD_SOFT"],
                                  T["BAD"], T["BAD_SOFT"])
SUN = T["SUN"]
SURFACE_COLOR = {"Hard": T["HARD"], "Clay": "#C9683F", "Grass": GOOD}

def _css():
    return f"""
<style>
  /* nadpisujemy motyw z config.toml, zeby przelacznik dzialal w locie */
  .stApp, [data-testid="stAppViewContainer"] {{
      background: {BG}; color: {TEXT}; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {{
      color: inherit; }}
  h1, h2, h3, h4 {{ color: {TEXT}; }}

  /* Cale UI o ~6% wieksze — przy tabelach liczb latwiej o pomylke,
     gdy tekst jest maly. */
  html {{ font-size: 17px; }}
  .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
  html, body, [class*="css"] {{ -webkit-font-smoothing: antialiased; }}
  h1 {{ font-weight: 640; letter-spacing: -.026em; font-size: 2rem;
        margin: 0 0 .2rem; line-height: 1.18; }}
  hr {{ border-color: {LINE}; }}

  .eyebrow {{ font-size: .72rem; letter-spacing: .13em;
              text-transform: uppercase; color: {CLAY}; font-weight: 700;
              margin: 1.8rem 0 .7rem; }}
  .sub {{ font-size: .87rem; color: {INK}; line-height: 1.62; }}
  /* `sub` to podpis przy danych; `note` to wyjasnienie merytoryczne.
     Rozdzielone, zeby ostrzezenia nie zlewaly sie z etykietami. */
  /* --- wiersze terminarza --- */
  /* Przycisk-wiersz: wyglada jak pozycja listy, nie jak przycisk. */
  div[data-testid="stHorizontalBlock"] .stButton button {{
      text-align: left; justify-content: flex-start;
      border: none; background: transparent; font-weight: 600;
      font-size: 1.06rem; padding: .75rem .25rem; border-radius: 8px;
      letter-spacing: -.005em;
  }}
  /* Streamlit owija etykiete w <p> z wlasnym wyrownaniem — bez tego
     nazwiska zostawaly wysrodkowane mimo reguly wyzej. */
  div[data-testid="stHorizontalBlock"] .stButton button p,
  div[data-testid="stHorizontalBlock"] .stButton button div {{
      text-align: left !important; width: 100%;
      /* Najdluzsze nazwisko w bazie ma 33 znaki; para moze dac 66.
         Przy waskim oknie ucinamy zamiast lamac wiersz na dwie linie. */
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }}
  div[data-testid="stHorizontalBlock"] .stButton button:hover {{
      background: transparent; color: {CLAY};
  }}
  /* Kreska miedzy meczami + naprzemienne tlo, zeby oko trzymalo wiersz. */
  /* :not(...) wyklucza rzad z pigulkami widoku — tam podswietlenie
     calego pasa wygladalo jak blad. */
  div[data-testid="stHorizontalBlock"]:has(.stButton):not(
      :has(div[role="radiogroup"])) {{
      border-bottom: 1px solid {LINE}; align-items: center;
      border-radius: 8px; transition: background .12s;
      min-height: 3.2rem;
  }}
  div[data-testid="stHorizontalBlock"]:has(.stButton):not(
      :has(div[role="radiogroup"])):nth-of-type(even) {{
      background: rgba(127,127,127,.035);
  }}
  /* Podswietlenie CALEGO wiersza, nie samego przycisku. */
  div[data-testid="stHorizontalBlock"]:has(.stButton):not(
      :has(div[role="radiogroup"])):hover {{
      background: {CLAY_SOFT};
  }}
  /* Wiersz terminarza — wyzszy, zeby dalo sie go objac wzrokiem. */
  div[data-testid="stCaptionContainer"] p {{ font-size: .84rem;
      color: {INK}; line-height: 1.55; }}
  .row-meta {{ font-size: .86rem; color: {INK}; text-align: right;
               padding-right: .5rem; line-height: 1.3; }}
  .row-prog {{ font-size: .95rem; color: {TEXT};
               font-variant-numeric: tabular-nums; line-height: 1.3; }}
  .row-prog-l {{ font-size: .7rem; color: {INK}; text-transform: uppercase;
                 letter-spacing: .08em; margin-right: .35rem; }}
  /* Separator miedzy zawodnikami — kolejnosc jak w nazwiskach obok. */
  .row-prog-s {{ color: {INK}; opacity: .5; margin: 0 .3rem; }}
  /* Ostrzezenie jako ikona z podpowiedzia — pelny tekst lamal wiersz. */
  .row-warn {{ color: {SUN}; margin-right: .45rem; cursor: help;
               font-size: .9rem; }}
  /* Przycisk "Odswiez" obok pigulek widoku — wyrownany do ich wysokosci. */
  div[data-testid="stHorizontalBlock"]:has(div[role="radiogroup"])
      .stButton button {{
      font-size: .84rem; padding: .32rem .7rem; border: 1px solid {LINE};
      background: {PANEL}; font-weight: 600;
  }}

  .note {{ font-size: .89rem; color: {INK}; line-height: 1.68;
           margin: .55rem 0; padding-left: .8rem;
           border-left: 2px solid {LINE}; }}
  .lead {{ font-size: 1rem; color: {INK}; line-height: 1.62;
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
  /* Wlasna tabela — st.dataframe rysuje sie na plotnie i ignoruje CSS. */
  .tbl {{ width: 100%; border-collapse: collapse; font-size: .9rem;
          margin: .3rem 0 .2rem; }}
  .tbl th {{ text-align: left; font-size: .72rem; letter-spacing: .09em;
             text-transform: uppercase; color: {INK}; font-weight: 700;
             padding: .5rem .7rem; border-bottom: 1px solid {LINE}; }}
  .tbl td {{ padding: .6rem .7rem; border-bottom: 1px solid {LINE};
             color: {TEXT}; font-variant-numeric: tabular-nums; }}
  .tbl tr:last-child td {{ border-bottom: none; }}
  .tbl tbody tr:hover {{ background: {CLAY_SOFT}; }}

</style>
"""




def zastosuj_css():
    """
    Ustawia palete wedlug przelacznika i wstrzykuje CSS.
    Wolane przy KAZDYM przebiegu — inaczej motyw zostalby zamrozony
    na wartosci z momentu importu modulu.
    """
    global T, BG, PANEL, SIDE, TEXT, INK, LINE, CLAY, CLAY_DEEP
    global CLAY_DIM, CLAY_SOFT, SUN, GOOD, GOOD_SOFT, BAD, BAD_SOFT
    global SURFACE_COLOR, CSS

    # Domyslnie ciemna, zgodnie z config.toml. Przelacznik zmienia NASZE
    # elementy; natywne widgety Streamlita ida wylacznie za config.toml.
    # Podazamy za motywem wybranym w menu Ustawien Streamlita.
    # st.context.theme.type zwraca "dark" albo "light".
    try:
        jasny = st.context.theme.type == "light"
    except Exception:
        jasny = False
    T = LIGHT if jasny else DARK
    BG, PANEL, SIDE = T["BG"], T["PANEL"], T["SIDE"]
    TEXT, INK, LINE = T["TEXT"], T["INK"], T["LINE"]
    CLAY, CLAY_DEEP, CLAY_DIM, CLAY_SOFT = (T["CLAY"], T["CLAY_DEEP"],
                                            T["CLAY_DIM"], T["CLAY_SOFT"])
    SUN = T["SUN"]
    GOOD, GOOD_SOFT, BAD, BAD_SOFT = (T["GOOD"], T["GOOD_SOFT"],
                                      T["BAD"], T["BAD_SOFT"])
    SURFACE_COLOR = {"Hard": T["HARD"], "Clay": "#C9683F", "Grass": GOOD}
    CSS = _css()
    st.markdown(CSS, unsafe_allow_html=True)


def color_delta(value: float, _unused: bool = True, unit: str = "") -> str:
    """Plus zielony, minus czerwony — bez odwracania znaczenia."""
    col = "inherit" if abs(value) < 1e-9 else (GOOD if value > 0 else BAD)
    return (f"<span style='color:{col};font-weight:650'>"
            f"{value:+.2f}{unit}</span>")


def data_age_days() -> int:
    raw = str(META.get("last_match_date") or "")
    if len(raw) != 8:
        return 0
    return (dt.date.today()
            - dt.date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))).days


def pl_date(x) -> str:
    s = str(int(x))
    return f"{s[6:]}.{s[4:6]}.{s[:4]}"
