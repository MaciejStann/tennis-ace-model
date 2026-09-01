"""Widok listy: terminarz ATP i wybor reczny zawodnikow."""
import pandas as pd
import streamlit as st

import model as M
import ui.stan as S
from fixtures import fetch_events
from ui.nawigacja import open_match, theme_switch
from ui.pomocnicze import (infer_best_of, surface_from_court)

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
    Cache'ujemy WYŁĄCZNIE udane pobranie. Wcześniej pusty wynik (wyczerpany
    limit dzienny) siedział w cache przez godzinę — po odnowieniu limitu
    aplikacja nadal pokazywała błąd, choć API już działało.
    """
    events, msg = _fetch_cached(days, token)
    if not events:
        _fetch_cached.clear()
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

    MODES = ["Terminarz ATP", "Wybór ręczny"]
    if st.session_state.pop("goto_manual", False):
        st.session_state.list_mode = MODES[1]
    mode = st.radio("Widok", MODES, horizontal=True, key="list_mode",
                    label_visibility="collapsed")

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
            e["m1"], e["c1"] = M.match_name(e["p1"], S.NAMES, cache)
            e["m2"], e["c2"] = M.match_name(e["p2"], S.NAMES, cache)
            e["known"] = sum(1 for k in ("m1", "m2") if e[k])
            e["n1"], e["n2"] = e["m1"] or e["p1"], e["m2"] or e["p2"]
            e["conf"] = min(e["c1"] or 1, e["c2"] or 1)

        f = st.columns(3)
        # Widgety z `key` trzymaja stan same — podawanie `value=` naraz
        # daje ostrzezenie o dwoch zrodlach prawdy.
        hide_low = f[0].checkbox("Tylko ATP Tour", True, key="hide_low",
                                 help="Ukrywa Challengery i ITF.")
        both_only = f[1].checkbox("Obaj znani w bazie", False, key="both_only")
        newest = f[2].checkbox("Od najpóźniejszych", False, key="newest")

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
