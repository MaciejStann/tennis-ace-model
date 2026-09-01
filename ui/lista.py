"""Widok listy: terminarz ATP i wybor reczny zawodnikow."""
import pandas as pd
import streamlit as st

import model as M
import ui.stan as S
from fixtures import fetch_events
from ui.nawigacja import open_match, theme_switch
from ui.pomocnicze import (default_games, infer_best_of,
                           surface_from_court)

try:
    import fixtures_free as FREE
except ImportError:
    FREE = None


def _fetch_cached(days: int, token: int):
    """
    Najpierw Sofascore — darmowe i bez limitu, wiec 500 zapytan z RapidAPI
    zostaje na dane statystyczne. RapidAPI tylko jako zapasowe.
    """
    if FREE is not None:
        ev, msg = FREE.fetch_events(days_ahead=days, tours=("atp",))
        if ev:
            return ev, msg
        pierwszy = msg
    else:
        pierwszy = "Moduł fixtures_free.py nie jest zainstalowany."
    ev, msg = fetch_events(days_ahead=days, tours=("atp",))
    if ev:
        return ev, msg + " (źródło zapasowe: RapidAPI)"
    return [], f"{pierwszy}\n\n--- źródło zapasowe (RapidAPI) ---\n{msg}"


def get_events(days: int, token: int):
    """
    Terminarz pobieramy RAZ na sesje i trzymamy w session_state.

    Wczesniej polegalismy na cache Streamlita, ale przy pustym wyniku
    czyscilismy go w calosci — a puste wyniki zdarzaja sie nieregularnie
    (jedno z dwoch zrodel milczy). Efekt: powrot z analizy do listy
    potrafil pobierac terminarz od nowa.

    Teraz pobranie nastepuje tylko wtedy, gdy zmienil sie zakres dni albo
    uzytkownik kliknal "Odswiez" (rosnie token). Nieudana proba nie kasuje
    ostatniego dobrego wyniku.
    """
    klucz = (days, token)
    zapas = st.session_state.get("fx_cache")
    if zapas and zapas[0] == klucz:
        return zapas[1], zapas[2]

    events, msg = _fetch_cached(days, token)
    if not events:
        _fetch_cached.clear()
        # zostaw poprzedni dobry wynik, jesli byl
        if zapas and zapas[1]:
            return zapas[1], (f"{msg}\n\nPokazuję ostatni pobrany "
                              f"terminarz.")
    st.session_state["fx_cache"] = (klucz, events, msg)
    return events, msg


def sidebar_list():
    with st.sidebar:
        st.markdown("<div class='eyebrow'>Tennis Ace Model</div>",
                    unsafe_allow_html=True)
        age = S.data_age_days()
        raw = str(S.META.get("last_match_date") or "")
        st.markdown(
            f"<div class='band' style='margin-top:.4rem'>"
            f"<div class='stat'><span class='sub'>Mecze</span>"
            f"<span>{S.META['n_matches']:,}</span></div>"
            f"<div class='stat'><span class='sub'>Zawodnicy</span>"
            f"<span>{len(S.PLAYERS)}</span></div>"
            f"<div class='stat'><span class='sub'>Dane do</span>"
            f"<span>{S.pl_date(raw) if len(raw) == 8 else '—'}</span></div>"
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
    raw = str(S.META.get("last_match_date") or "")
    st.markdown(
        f"<div class='hero hero-lg'>"
        f"<div class='eyebrow'>ATP · asy i podwójne błędy</div>"
        f"<h1 class='big'>Tennis Ace Model</h1>"
        f"<div class='lead'>Ile asów poda zawodnik w nadchodzącym meczu — "
        f"i czy linia bukmachera to dobrze wycenia.</div>"
        f"<div class='hero-stats'>"
        f"<div class='hero-stat'><b>{S.META['n_matches']:,}</b>"
        f"<span>meczów</span></div>"
        f"<div class='hero-stat'><b>{len(S.PLAYERS)}</b>"
        f"<span>zawodników</span></div>"
        f"<div class='hero-stat'><b>{S.META['years'][0]}–{S.META['years'][1]}</b>"
        f"<span>sezony</span></div>"
        f"<div class='hero-stat'><b>{S.pl_date(raw) if len(raw) == 8 else '—'}"
        f"</b><span>dane do</span></div>"
        f"</div></div>".replace(",", " "), unsafe_allow_html=True)

    MODES = ["Terminarz ATP", "Wybór ręczny", "Rejestr"]
    if st.session_state.pop("goto_manual", False):
        st.session_state.list_mode = MODES[1]
    # Przelacznik widoku i "Odswiez" w jednym rzedzie — przycisk dotyczy
    # terminarza, wiec stoi na jego wysokosci, a nie nizej w tresci.
    m_col, r_col = st.columns([5, 1])
    with m_col:
        mode = st.radio("Widok", MODES, horizontal=True, key="list_mode",
                        label_visibility="collapsed")
    with r_col:
        if mode == MODES[0]:
            if st.button("Odśwież", use_container_width=True,
                         key="fx_refresh",
                         help="Pobiera terminarz od nowa. Bez limitu — "
                              "źródłem jest Flashscore."):
                st.session_state.fx_token += 1
                st.rerun()

    # ---------------------------------------------------------- rejestr
    if mode == MODES[2]:
        from ui.rejestr_widok import view_rejestr
        view_rejestr()
        return

    # ---------------------------------------------------- wybór ręczny
    if mode == MODES[1]:
        st.caption("Zacznij pisać nazwisko, żeby znaleźć zawodnika.")

        c1, c2 = st.columns(2)
        s1 = c1.selectbox("Zawodnik 1", S.NAMES, key="man1")
        rest = [n for n in S.NAMES if n != s1]
        s2 = c2.selectbox("Zawodnik 2", rest, index=min(1, len(rest) - 1),
                          key="man2")

        # karty zamiast jednej dlugiej linii — przy dwoch ostrzezeniach
        # tekst zlewal sie w nieczytelny ciag
        pc = st.columns(2, gap="medium")
        for col, nm in zip(pc, (s1, s2)):
            cnt = S.MATCH_COUNT.get(nm, 0)
            if cnt >= 25:
                pill = (f"<span class='pill' style='background:{S.GOOD_SOFT};"
                        f"color:{S.GOOD}'>dość danych</span>")
            else:
                pill = (f"<span class='pill' style='background:{S.BAD_SOFT};"
                        f"color:{S.BAD}'>mało danych</span>")
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
        # Zakres na stale: dzis i jutro. Suwak byl zbedny — dluzszy
        # horyzont i tak nie ma sensu, bo drabinki sie zmieniaja.
        events, msg = get_events(2, st.session_state.fx_token)

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
                    st.code(fetch_events(days_ahead=2,
                                         tours=("atp",), debug=True)[1])
            return

        cache = st.session_state.namecache
        for e in events:
            e["m1"], e["c1"] = M.match_name(e["p1"], S.NAMES, cache)
            e["m2"], e["c2"] = M.match_name(e["p2"], S.NAMES, cache)
            e["known"] = sum(1 for k in ("m1", "m2") if e[k])
            # Nazwa z bazy jest krotsza i spojna ("Carlos Alcaraz" zamiast
            # "Alcaraz Garfia Carlos" z Flashscore). Oryginal tylko gdy
            # nie udalo sie dopasowac.
            e["n1"], e["n2"] = e["m1"] or e["p1"], e["m2"] or e["p2"]
            e["conf"] = min(e["c1"] or 1, e["c2"] or 1)

        f = st.columns([2, 2, 3])
        # Widgety z `key` trzymaja stan same — podawanie `value=` naraz
        # daje ostrzezenie o dwoch zrodlach prawdy.
        hide_low = f[0].checkbox("Tylko ATP Tour", True, key="hide_low",
                                 help="Ukrywa Challengery i ITF.")
        both_only = f[1].checkbox("Obaj znani w bazie", False, key="both_only")

        shown = events
        if hide_low:
            filtered = [e for e in shown if e.get("rank_id") not in (0, 1)]
            if filtered or all(e.get("rank_id") is None for e in shown):
                shown = filtered or shown
        if both_only:
            shown = [e for e in shown if e["known"] == 2]
        shown = [e for e in shown if e["known"] >= 1 and e["n1"] != e["n2"]]
        shown.sort(key=lambda e: e.get("start") or "9999")

        st.caption(f"{len(shown)} z {len(events)} meczów po filtrach")
        if not shown:
            st.info("Brak meczów spełniających filtry — odznacz "
                    "„Obaj znani w bazie” albo „Tylko ATP Tour”.")
            return

        by_tour: dict[str, list] = {}
        for e in shown:
            by_tour.setdefault(e.get("tournament") or "Turniej nieznany",
                               []).append(e)
        order = sorted(by_tour.items(),
                       key=lambda kv: min(x.get("start") or "9999"
                                          for x in kv[1]))

        for tname, group in order:
            rank = group[0].get("rank_name") or ""
            head = f"{tname} · {len(group)}" + (f" · {rank}" if rank else "")
            with st.expander(head, expanded=len(order) <= 4):
                for e in group:
                    render_row(e)


def _prognoza_wiersza(e):
    """
    Szybka prognoza asow i DF do listy. Liczona przy domyslnej dlugosci
    meczu — dokladna wartosc ustawia sie dopiero w analizie, tu chodzi
    o rzad wielkosci, zeby dalo sie przebiec wzrokiem po terminarzu.
    """
    if e["known"] < 2:
        return None
    surf, indoor = surface_from_court(e.get("court", ""))
    surf = surf or "Hard"
    bo, _ = infer_best_of(e.get("tournament", ""), e.get("rank_name", ""))
    gemy = default_games(bo, surf)
    svpt = gemy * S.META["pts_per_service_game"]
    try:
        a = M.estimate(S.PLAYERS, S.META, S.CALIB, e["n1"], e["n2"],
                       surf, indoor, svpt * .5, S.MATCHES)
        b = M.estimate(S.PLAYERS, S.META, S.CALIB, e["n2"], e["n1"],
                       surf, indoor, svpt * .5, S.MATCHES)
    except Exception:
        return None
    if not (a["known"] and b["known"]):
        return None
    # Osobno dla kazdego zawodnika — suma mowi mniej, bo to zwykle rynek
    # na konkretnego gracza sie obstawia.
    return {"a1": a["mu_ace"], "a2": b["mu_ace"],
            "d1": a["mu_df"], "d2": b["mu_df"]}


def render_row(e):
    """
    Uklad: nazwiska (klikalne) | prognoza asow i DF | czas po prawej.
    Caly wiersz reaguje na najechanie.
    """
    # Dymek ma mowic, KTOREGO zawodnika dotyczy problem — samo
    # "niepelne dane" nie pozwala ocenic, czy warto wchodzic w mecz.
    znaki = []
    for surowe, dopasowane, pewnosc in ((e["p1"], e["m1"], e.get("c1")),
                                        (e["p2"], e["m2"], e.get("c2"))):
        if not dopasowane:
            znaki.append(f"{surowe} — nie ma w bazie ATP Tour")
        elif pewnosc is not None and pewnosc < 0.9:
            znaki.append(f"{surowe} — rozpoznany jako {dopasowane} "
                         f"({100 * pewnosc:.0f}% pewności)")

    n1 = e["n1"] + ("" if e["m1"] else " ⚠")
    n2 = e["n2"] + ("" if e["m2"] else " ⚠")

    start = e.get("start") or ""
    dzien = start[8:10] + "." + start[5:7] if len(start) >= 10 else ""
    godz = start[11:16]
    kort = e.get("court", "")

    c_btn, c_prog, c_meta = st.columns([6, 3, 3])
    if c_btn.button(f"{n1}  vs  {n2}", key=f"go_{e['id']}",
                    use_container_width=True,
                    help="; ".join(znaki) if znaki else None):
        surf, indoor = surface_from_court(e.get("court", ""))
        bo, why = infer_best_of(e.get("tournament", ""), e.get("rank_name", ""))
        open_match(e["n1"], e["n2"],
                   {"surface": surf, "indoor": indoor, "best_of": bo,
                    "best_of_why": why, "tournament": e.get("tournament", ""),
                    "rank_name": e.get("rank_name", ""),
                    "start": e.get("start", "")})

    pr = _prognoza_wiersza(e)
    if pr:
        # Kolejnosc wierszy odpowiada kolejnosci nazwisk po lewej.
        c_prog.markdown(
            f"<div class='row-prog'>"
            f"<span class='row-prog-l'>asy</span>"
            f"<b>{pr['a1']:.0f}</b>"
            f"<span class='row-prog-s'>·</span>"
            f"<b>{pr['a2']:.0f}</b>"
            f"<span class='row-prog-l' style='margin-left:.8rem'>df</span>"
            f"<b>{pr['d1']:.0f}</b>"
            f"<span class='row-prog-s'>·</span>"
            f"<b>{pr['d2']:.0f}</b>"
            f"</div>", unsafe_allow_html=True)
    else:
        c_prog.markdown("<div class='row-prog' style='opacity:.45'>—</div>",
                        unsafe_allow_html=True)

    # Ikona ostrzezenia przed godzina. Tresc trafia do `help` przycisku,
    # bo atrybut `title` w HTML wstrzykiwanym przez st.markdown nie
    # generuje podpowiedzi — Streamlit go pomija.
    ostrz = "<span class='row-warn'>⚠</span>" if znaki else ""
    c_meta.markdown(
        f"<div class='row-meta'>{ostrz}<b>{godz}</b>"
        + (f" <span style='opacity:.6'>{dzien}</span>" if dzien else "")
        + (f"<div style='opacity:.7;font-size:.74rem'>{kort}</div>"
           if kort else "")
        + "</div>", unsafe_allow_html=True)
