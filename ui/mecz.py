"""Widok meczu: asy, podwojne bledy, przebieg meczu, H2H i forma."""
import numpy as np
import pandas as pd
import streamlit as st
from scipy import stats as sst

import model as M
import pointmodel as PM
import ui.stan as S
from ui.nawigacja import go_back, theme_switch
from ui.pomocnicze import ROUNDS, default_games, polowka, surface_of


def _szacunek_gemow(p1, p2, surface: str, best_of: int):
    """Szacunek dlugosci meczu z modelu punktowego. None, gdy brak danych."""
    if not p1 or not p2:
        return None
    try:
        rates, pmeta = S.load_point()
        if rates is None:
            return None
        a = PM.effective_p_serve(rates, pmeta, p1, p2, surface)
        b = PM.effective_p_serve(rates, pmeta, p2, p1, surface)
        if a is None or b is None:
            return None
        return PM.match_outcome(a, b, best_of)["exp_games"]
    except Exception:
        return None


def tabela(rows: list[dict], wyroznij: str | None = None):
    """
    Tabela jako HTML zamiast st.dataframe.

    st.dataframe renderuje sie na plotnie (glide-data-grid), wiec nie
    reaguje na nasz CSS i w ciemnym motywie zostawala biala.
    """
    if not rows:
        return
    kol = list(rows[0])
    thead = "".join(f"<th>{k}</th>" for k in kol)
    tbody = ""
    for r in rows:
        tds = ""
        for k in kol:
            v = str(r[k])
            styl = ""
            if k == wyroznij or v.startswith("+") or v.startswith("-"):
                if v.startswith("+"):
                    styl = f" style='color:{S.GOOD};font-weight:650'"
                elif v.startswith("-"):
                    styl = f" style='color:{S.BAD};font-weight:650'"
            tds += f"<td{styl}>{v}</td>"
        tbody += f"<tr>{tds}</tr>"
    st.markdown(f"<table class='tbl'><thead><tr>{thead}</tr></thead>"
                f"<tbody>{tbody}</tbody></table>", unsafe_allow_html=True)


def _etykieta_powrotu() -> str:
    return ("← Wybór zawodników"
            if st.session_state.get("origin") == "manual"
            else "← Lista meczów")


def sidebar_detail(ctx: dict, mkey: str) -> dict:
    """Ustawienia meczu. Zwraca słownik parametrów."""
    with st.sidebar:
        st.markdown("### Warunki meczu")
        surfaces = ["Hard", "Clay", "Grass"]
        auto = ctx.get("surface")
        surface = st.selectbox(
            "Nawierzchnia", surfaces,
            index=surfaces.index(auto) if auto in surfaces else 0,
            key=f"surf_{mkey}")
        indoor = st.checkbox("Hala", value=bool(ctx.get("indoor")),
                             key=f"ind_{mkey}",
                             help=f"Mnożnik {S.META['indoor_mult']:.2f} — "
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
        # Model punktowy potrafi oszacowac dlugosc dla konkretnej pary.
        # Na calej probie jest tylko tyle samo wart co srednia (MAE 5,49
        # vs 5,50), ale dopasowuje sie do zestawienia, wiec przy skrajnych
        # parach powinien byc blizej.
        szac = _szacunek_gemow(ctx.get("p1"), ctx.get("p2"), surface, best_of)
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

        total_games_raw = st.number_input(
            "Linia bukmachera na total gemów", 12.5, 70.5, step=1.0,
            key=gkey, format="%.1f")
        total_games = polowka(total_games_raw)
        if abs(total_games - total_games_raw) > 1e-9:
            st.caption(f"Zaokrąglono do {total_games:g}")
        touched = abs(total_games - dflt) > 0.01
        cc = st.columns([3, 2])
        podp = f"Typowo przy bo{best_of} na {surface.lower()}: {dflt:.1f}"
        if szac is not None:
            podp += f" · model dla tej pary: **{szac:.1f}**"
        cc[0].caption(podp)
        if touched and cc[1].button("Domyślna", use_container_width=True):
            st.session_state[gkey] = dflt
            st.session_state[pkey] = dflt
            st.rerun()
        if not touched:
            st.markdown(
                f"<div class='sub' style='color:{S.CLAY}'>"
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
                                   float(S.CALIB["nb_r"]), 1.0, key=f"nb_{mkey}")
            st.caption("Stawka jest ograniczona do 10% bankrolla niezależnie "
                       "od ułamka Kelly'ego.")
        theme_switch()

    return {"surface": surface, "indoor": indoor, "best_of": best_of,
            "total_games": total_games, "split": split, "bankroll": bankroll,
            "kfrac": kfrac, "nb_r": nb_r}


def market_block(mu: float, key: str, r: float, bankroll: float,
                 kfrac: float, mkey_for_sens: str = "",
                 ctx_p1: str = "", ctx_p2: str = "",
                 cfg_ref: dict | None = None, rynek_ref: str = ""):
    """Linia, kursy, EV, Kelly i rozkład dla jednego rynku."""
    c = st.columns(3, gap="medium")
    raw_line = c[0].number_input(
        "Linia", 0.5, 60.5, float(np.floor(mu) + 0.5), 1.0,
        key=f"l_{key}", format="%.1f")
    # Linie totali sa polowkowe (8.5, 9.5, 10.5) — przy calkowitej wynik
    # rowny linii oznacza zwrot stawki, czego model nie liczy. Przyciagamy
    # wiec do najblizszej polowki.
    line = min(max(polowka(raw_line), 0.5), 60.5)
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
        tag_bg, tag_fg = ((S.GOOD_SOFT, S.GOOD) if win else (S.BAD_SOFT, S.BAD))
        ev_col = S.GOOD if sd["ev"] > 0 else S.BAD
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
            f"<div class='band' style='background:{S.GOOD_SOFT};"
            f"border-color:{S.GOOD}'>"
            f"<b style='color:{S.GOOD}'>{best['side']} {line:g}</b> "
            f"<span class='sub'>wygląda na niedowartościowane o "
            f"{100 * best['ev']:.1f}%. To przewaga oczekiwana, nie pewny "
            f"zakład.</span></div>", unsafe_allow_html=True)
        # Zapis do rejestru tylko przy dodatnim EV — reszty i tak nie gramy.
        from ui.rejestr_widok import przycisk_zapisu
        przycisk_zapisu(
            ctx_p1, ctx_p2, cfg_ref, rynek_ref, best["side"], line,
            best["odds"], best["prob"], best["ev"], best["stake"], key)
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
        tabela(rows)
        sides = {r_["Lepsza strona"] for r_ in rows}
        if len(sides) > 1:
            st.markdown(
                f"<div class='sub' style='color:{S.BAD}'><b>Uwaga:</b> przy "
                f"innej długości meczu opłacalna strona się zmienia. "
                f"Ten zakład jest wrażliwy na długość — bez linii bukmachera "
                f"na total gemów lepiej odpuścić.</div>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div class='sub' style='color:{S.GOOD}'>Ta sama strona "
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
    """
    Kolejnosc jest celowa: najpierw wybor rynku i kursy, potem od razu EV.
    Wczesniej EV bylo ~40 linii nizej, pod metrykami i rozbiciem — czyli
    pod zgieciem ekranu, mimo ze to jedyna liczba, na podstawie ktorej
    podejmuje sie decyzje.
    """
    field = "mu_ace" if kind == "ace" else "mu_df"
    label = "asy" if kind == "ace" else "podwójne błędy"
    both = e1["known"] and e2["known"]
    total = (e1[field] + e2[field]) if both else None
    r = cfg["nb_r"] if kind == "ace" else max(cfg["nb_r"] * 0.35, 3.0)

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

    st.markdown(f"<div class='eyebrow' style='margin-top:.4rem'>"
                f"Prognoza — {label}</div>", unsafe_allow_html=True)
    c = st.columns(3, gap="medium")
    for col, nm, e in zip(c, (p1, p2), (e1, e2)):
        # Liczba meczow w bazie decyduje o wiarygodnosci prognozy, wiec
        # stoi przy niej, a nie tylko w rozbiciu.
        podpis = (f"{e['n']} meczów w bazie" if e["known"]
                  else "brak w bazie")
        col.metric(nm, f"{e[field]:.1f}" if e["known"] else "—", podpis,
                   delta_color="off")
    c[2].metric("Razem", f"{total:.1f}" if both else "—")

    st.markdown("<div class='eyebrow'>Rynek do wyceny</div>",
                unsafe_allow_html=True)
    choice = st.radio("Rynek", list(opts), horizontal=True,
                      key=f"mkt_{kind}_{mkey}", label_visibility="collapsed")
    mu = opts[choice]
    st.markdown(
        f"<div class='note'>Prognoza modelu: <b>{mu:.1f}</b> — to wartość "
        f"oczekiwana, dlatego nie jest połówkowa. Linia bukmachera zawsze "
        f"jest.</div>", unsafe_allow_html=True)

    slot = list(opts).index(choice)
    market_block(mu, f"{kind}_{slot}_{mkey}", r, cfg["bankroll"],
                 cfg["kfrac"], mkey, p1, p2, cfg,
                 f"{label} · {choice}")

    if kind == "df":
        st.markdown(
            "<div class='note'><b>DF prognozuje się gorzej niż asy.</b> "
            "Zależą od formy dnia i presji, nie od trwałej cechy jak "
            "prędkość serwisu. Model nie stosuje korekty na returnera — "
            "przeciwnik nie wpływa na to, czy ktoś wrzuci drugie podanie "
            "w siatkę.</div>", unsafe_allow_html=True)

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
                f"<div class='stat' style='border-top:1px solid {S.LINE};"
                f"margin-top:.2rem;padding-top:.5rem'>"
                f"<span class='sub'>Wynik</span>"
                f"<span style='color:{S.CLAY};font-weight:650'>"
                f"{e[field]:.1f}</span></div></div>",
                unsafe_allow_html=True)

        if kind == "ace":
            st.markdown(
                "<div class='note'>Skuteczność serwisu na tej nawierzchni "
                "razy poprawka na to, jak przeciwnik odbiera, razy poprawka "
                "na halę, razy liczba punktów przy serwisie. Umiejętności "
                "returnowe przeciwnika poprawiają trafność najbardziej ze "
                "wszystkich składników.</div>", unsafe_allow_html=True)
            if any(e["known"] and not e["ret_known"] for e in (e1, e2)):
                st.markdown(
                    "<div class='note'>⚠ Mnożnik returnera 1,00 znaczy, że "
                    "<b>nie mam danych</b> o przeciwniku — a nie, że jest "
                    "przeciętny.</div>", unsafe_allow_html=True)
        else:
            used = [(nm, e["form"]["df"]) for nm, e in known
                    if e.get("form", {}).get("df")]
            st.markdown(
                "<div class='note'>Skuteczność razy liczba punktów przy "
                "serwisie. Bez poprawki na przeciwnika.</div>",
                unsafe_allow_html=True)
            if used:
                for nm, fi in used:
                    st.markdown(
                        f"<div class='note'>Dla <b>{nm}</b> wzięta pod uwagę "
                        f"forma z ostatnich {fi['n']} meczów (od "
                        f"{S.pl_date(fi['since'])}). Sprawdziłem na danych, "
                        f"że przy podwójnych błędach to pomaga.</div>",
                        unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='note'>Forma nie jest brana pod uwagę. "
                    "Uruchom <code>python oos_check.py</code>, żeby "
                    "sprawdzić, czy pomogłaby na twoich danych.</div>",
                    unsafe_allow_html=True)


def match_tab(p1: str, p2: str, cfg: dict, mkey: str):
    """Przebieg meczu: zwyciezca, wynik w setach, tie-breaki, gemy."""
    import pointmodel as PM

    try:
        rates, pmeta = S.load_point()
    except Exception as exc:
        st.error("Nie udało się przygotować modelu meczu.")
        st.caption(f"{type(exc).__name__}: {exc}")
        st.caption("Zwykle znaczy to, że baza nie ma kolumn serwisowych. "
                   "Uruchom: python migrate_serve.py")
        return
    if rates is None:
        st.info("Brak danych o punktach serwisowych. Uruchom:")
        st.code("python migrate_serve.py\npython rebuild_from_slim.py",
                language="powershell")
        return

    ps1 = PM.effective_p_serve(rates, pmeta, p1, p2, cfg["surface"])
    ps2 = PM.effective_p_serve(rates, pmeta, p2, p1, cfg["surface"])
    if ps1 is None or ps2 is None:
        brak = [n for n, v in ((p1, ps1), (p2, ps2)) if v is None]
        st.error(f"Brak danych punktowych dla: {', '.join(brak)}.")
        return

    o = PM.match_outcome(ps1, ps2, cfg["best_of"])
    p_raw = o["p_win"]

    # Sam model widzi tylko serwis. Ranking dokłada informację o klasie
    # zawodnika — w meczach o podobnym serwisie to jedyne, co rozstrzyga.
    rk = S.last_ranks()
    r1, r2 = rk.get(p1), rk.get(p2)
    pw1 = PM.blend_with_rank(p_raw, r1, r2)
    pw2 = 1 - pw1

    st.markdown("<div class='eyebrow' style='margin-top:.4rem'>"
                "Kto wygra</div>", unsafe_allow_html=True)
    c = st.columns(2, gap="medium")
    for col, nm, pw in zip(c, (p1, p2), (pw1, pw2)):
        col.metric(nm.split()[-1], f"{100 * pw:.0f}%")

    pewnosc = abs(pw1 - 0.5)
    if pewnosc < 0.04:
        traf, opis, kol = "52%", "model nie ma zdania", S.BAD
    elif pewnosc < 0.08:
        traf, opis, kol = "56%", "słaby sygnał", S.BAD
    elif pewnosc < 0.14:
        traf, opis, kol = "60%", "przeciętny sygnał", S.INK
    elif pewnosc < 0.20:
        traf, opis, kol = "70%", "mocny sygnał", S.GOOD
    else:
        traf, opis, kol = "75–80%", "bardzo mocny sygnał", S.GOOD
    st.markdown(
        f"<div class='band' style='border-color:{kol}'>"
        f"<b style='color:{kol}'>{opis.capitalize()}</b>"
        f"<div class='sub' style='margin-top:.3rem'>Przy takiej pewności "
        f"model trafiał historycznie w <b>{traf}</b> przypadków. "
        f"Serwis: {p1.split()[-1]} {100 * ps1:.1f}%, {p2.split()[-1]} "
        f"{100 * ps2:.1f}%"
        + (f" · ranking {r1:.0f} vs {r2:.0f}" if r1 and r2 else
           " · brak rankingu w bazie")
        + "</div></div>", unsafe_allow_html=True)

    # --- wycena rynku 1/2 ---
    st.markdown("<div class='eyebrow'>Wycena zwycięzcy</div>",
                unsafe_allow_html=True)
    k = st.columns(2, gap="medium")
    o1 = k[0].number_input(f"Kurs na {p1.split()[-1]}", 1.01, 30.0, 1.90, 0.01,
                           key=f"w1_{mkey}", format="%.2f")
    o2 = k[1].number_input(f"Kurs na {p2.split()[-1]}", 1.01, 30.0, 1.90, 0.01,
                           key=f"w2_{mkey}", format="%.2f")
    devig = 1 / o1 + 1 / o2
    rows = []
    for nm, pw, od in ((p1, pw1, o1), (p2, pw2, o2)):
        ev = pw * od - 1
        rows.append({"Zawodnik": nm, "Model": f"{100 * pw:.0f}%",
                     "Kurs sprawiedliwy": f"{PM.fair_odds(pw):.2f}",
                     "Kurs bukmachera": f"{od:.2f}",
                     "Rynek": f"{100 / od / devig:.0f}%",
                     "EV": f"{100 * ev:+.1f}%"})
    tabela(rows)
    st.markdown(
        f"<div class='note'><b>Kurs sprawiedliwy</b> to taki, przy którym "
        f"zakład ma zerową wartość oczekiwaną — jeśli bukmacher daje więcej, "
        f"jest przewaga. Marża {100 * (devig - 1):.1f}%. "
        f"<b>Rynek 1/2 jest wyceniany sprawnie</b>, więc dużą różnicę "
        f"traktuj z rezerwą, nie jak okazję.</div>",
        unsafe_allow_html=True)

    # Sekcje ponizej maja NIZSZA wiarygodnosc niz prognoza zwyciezcy
    # (model zaniza rozstrzygalnosc), wiec sa zwiniete — zeby nie
    # konkurowaly wzrokowo z wycena 1/2.
    with st.expander("Wynik w setach, tie-breaki i gemy"):
        _przebieg_szczegoly(p1, p2, o, mkey)


def _przebieg_szczegoly(p1: str, p2: str, o: dict, mkey: str):
    st.markdown("<div class='eyebrow' style='margin-top:0'>"
                "Wynik w setach</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='note' style='color:{S.CLAY}'>⚠ Ta sekcja jest mniej "
        f"wiarygodna niż prognoza zwycięzcy. Model zakłada, że punkty są "
        f"niezależne, więc daje <b>za mało rozstrzygających wyników</b>: "
        f"2:0 przewiduje na 43%, a w danych zdarza się w 52% wygranych "
        f"meczów. Traktuj to jako orientację, nie wycenę.</div>",
        unsafe_allow_html=True)
    sc = st.columns(2, gap="medium")
    for col, nm, kier in zip(sc, (p1, p2), (True, False)):
        wiersze = []
        for (w, l), v in o["sets"].items():
            wygral_p1 = w > l
            if wygral_p1 != kier:
                continue
            a, b = (w, l) if kier else (l, w)
            wiersze.append(
                f"<div class='stat'><span class='sub'>{a}:{b}</span>"
                f"<span>{100 * v:.0f}%</span></div>")
        col.markdown(f"<div class='card'><b>{nm}</b>{''.join(wiersze)}</div>",
                     unsafe_allow_html=True)

    # --- pozostale rynki ---
    st.markdown("<div class='eyebrow'>Pozostałe rynki</div>",
                unsafe_allow_html=True)
    m = st.columns(3, gap="medium")
    m[0].metric("Tie-break w meczu", f"{100 * o['p_any_tiebreak']:.0f}%")
    m[1].metric("Gemy — prognoza", f"{o['exp_games']:.1f}")
    m[2].metric("Setów", f"{o['exp_sets']:.1f}")
    st.markdown(
        "<div class='note'>Prognoza gemów: typowa pomyłka ok. 5,6 gema — "
        "<b>długość meczu jest z natury trudna</b>. Szansa tie-breaka jest "
        "z tego samego powodu <b>zawyżona o ok. 10 punktów</b> (model 50%, "
        "w danych 40%). Obie liczby traktuj orientacyjnie.</div>",
        unsafe_allow_html=True)

    # Bez st.expander — jestesmy juz wewnatrz rozwijki, a Streamlit nie
    # pozwala ich zagniezdzac.
    st.markdown("<div class='eyebrow'>Skąd te liczby</div>",
                unsafe_allow_html=True)
    st.markdown(
        f"<div class='note'>Model punktowy: z prawdopodobieństwa wygrania "
        f"punktu liczymy analitycznie gem, tie-break, set i mecz. "
        f"Zakłada niezależność punktów — przybliżenie, bo punkty ważne "
        f"rozgrywane są inaczej, dlatego prognozy są dodatkowo ściągane "
        f"do środka.<br><br>"
        f"Utrzymanie podania: <b>{p1.split()[-1]} "
        f"{100 * o['hold1']:.0f}%</b>, <b>{p2.split()[-1]} "
        f"{100 * o['hold2']:.0f}%</b>. Szansa wygrania seta przez "
        f"{p1.split()[-1]}: <b>{100 * o['p_set']:.0f}%</b>."
        f"<br><br>Walidacja out-of-sample: log loss 0,655 wobec 0,693 "
        f"dla rzutu monetą i 0,872 dla „wyżej notowany wygrywa”. "
        f"Trafność 60%.</div>", unsafe_allow_html=True)


def h2h_tab(p1: str, p2: str, e1: dict, e2: dict, cfg: dict, mkey: str):
    games = M.h2h_list(S.MATCHES, p1, p2)

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
        scol = S.SURFACE_COLOR.get(m["surface"], S.T["HARD"])

        # --- blok 1: gdzie i kiedy ---
        meta_bits = [m["tournament"], ROUNDS.get(m["round"], m["round"]),
                     m["date_str"]]
        st.markdown(
            f"<div class='card'>"
            f"<div class='row'><span><b>{m['tournament'] or 'Turniej'}</b>"
            f" &nbsp;<span class='sub'>"
            f"{' · '.join(b for b in meta_bits[1:] if b)}</span></span>"
            f"<span class='tag' style='background:{scol};color:#fff'>"
            f"{m['surface']}{' · hala' if m['indoor'] else ''}</span></div>"
            f"</div>", unsafe_allow_html=True)

        # --- blok 2: kto wygral i jakim wynikiem ---
        def nm_fmt(nm, won):
            return (f"<b style='font-size:1.05rem'>{nm}</b>" if won
                    else f"<span style='color:{S.INK}'>{nm}</span>")

        st.markdown(
            f"<div class='card' style='border-left:4px solid {S.CLAY}'>"
            f"<div class='row'>"
            f"<span style='font-size:1.02rem'>{nm_fmt(p1, w1 is not False)}"
            f" <span class='sub'>vs</span> {nm_fmt(p2, w1 is not True)}</span>"
            f"<span style='font-weight:650;font-variant-numeric:tabular-nums'>"
            f"{sc}</span></div>"
            f"</div>", unsafe_allow_html=True)

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
                    avg = M.career_rate(S.MATCHES, nm, metric, m["surface"])
                    right = f"<b>{sd[metric]:.0f}</b>"
                    if avg is not None:
                        right += ("&nbsp;&nbsp;"
                                  + S.color_delta(sd[metric] - avg, good)
                                  + f" <span class='sub'>(zwykle "
                                    f"{avg:.1f})</span>")
                    lines.append(f"<div class='stat'><span class='sub'>{lab}"
                                 f"</span><span>{right}</span></div>")
                lines.append(f"<div class='stat'><span class='sub'>Gemy przy "
                             f"serwisie</span><span>{sd['svgms']:.0f}</span>"
                             f"</div></div>")
                st.markdown("".join(lines), unsafe_allow_html=True)

        st.markdown(
            f"<div class='note'>Porównanie z tym, ile ten zawodnik podaje "
            f"zwykle na nawierzchni {m['surface'].lower()}. "
            "<b>Model nie bierze H2H pod uwagę</b> — kilka meczów to za "
            "mało, żeby cokolwiek z nich wnioskować.</div>",
            unsafe_allow_html=True)

        totals, n = M.h2h_totals(S.MATCHES, p1, p2)
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
        res = M.last_results(S.MATCHES, nm, metric, win_n,
                             cfg["surface"] if only_surf else None)
        if not res:
            st.caption(f"{nm}: brak meczów w bazie.")
            continue
        # linia domyslna: tam, gdzie ustawilby ja bukmacher dla tego zawodnika
        mu_p = e["mu_ace"] if metric == "ace" else e["mu_df"]
        line_p = float(np.floor(mu_p) + 0.5)
        hits = sum(1 for x in res if x["value"] > line_p)
        vals = " ".join(
            f"<span style='color:{S.GOOD if x['value'] > line_p else S.INK};"
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
    win = (S.CALIB.get("form", {}).get("df") or {}).get("window", 10)
    for nm, e in ((p1, e1), (p2, e2)):
        if not e["known"]:
            continue
        cols = st.columns(2, gap="medium")
        for col, metric, lab, prior, base in (
                (cols[0], "ace", "ace%", S.META["tour_ace_pct"], e["ace"]),
                (cols[1], "df", "df%", S.META["tour_df_pct"], e["df_overall"])):
            rate, cnt, since = M.recent_rate(S.MATCHES, nm, metric, win, prior)
            if rate is None:
                col.caption(f"{nm} — {lab}: brak danych")
                continue
            diff = 100 * (rate - base)
            col.metric(f"{nm} — {lab} z {cnt} ost.", f"{100 * rate:.2f}%")
            arrow = "wyżej" if diff > 0 else "niżej"
            # przy asach wiecej = lepiej dla serwujacego, przy DF odwrotnie
            col.markdown(
                f"<span class='sub'>{S.color_delta(diff, metric == 'ace', ' pp')}"
                f" {arrow} niż zwykle · od {S.pl_date(since)}</span>",
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
    ctx = dict(ctx, p1=p1, p2=p2)
    cfg = sidebar_detail(ctx, mkey)

    head = [ctx.get("tournament", ""), ctx.get("rank_name", ""),
            f"bo{cfg['best_of']}", f"{cfg['total_games']:.1f} gemów",
            (ctx.get("start") or "")[:16].replace("T", " ")]
    baza = " · ".join(
        f"{n.split()[-1]} {int(S.PLAYERS.loc[n, 'matches'])} meczów"
        if n in S.PLAYERS.index else f"{n.split()[-1]} brak w bazie"
        for n in (p1, p2))

    if st.button(_etykieta_powrotu(), key="back_top"):
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
        f"&nbsp;&nbsp;{' · '.join(h for h in head if h)}"
        f"<br><span style='opacity:.75;font-size:.82rem'>W bazie: {baza}"
        f"</span></div></div>", unsafe_allow_html=True)

    svpt = cfg["total_games"] * S.META["pts_per_service_game"]
    e1 = M.estimate(S.PLAYERS, S.META, S.CALIB, p1, p2, cfg["surface"],
                    cfg["indoor"], svpt * cfg["split"], S.MATCHES)
    e2 = M.estimate(S.PLAYERS, S.META, S.CALIB, p2, p1, cfg["surface"],
                    cfg["indoor"], svpt * (1 - cfg["split"]), S.MATCHES)

    # Blokujące ostrzeżenia zostają na wierzchu, resztę chowamy —
    # przy kilku naraz zalewały ekran i nikt ich nie czytał.
    # Jeden pasek statusu zamiast czterech komunikatow jeden pod drugim.
    # Blokujace zostaje widoczne — uniewaznia wynik. Reszta zwinieta,
    # ale z widoczna liczba, zeby nie dalo sie jej przeoczyc.
    unknown = [n for n, e in ((p1, e1), (p2, e2)) if not e["known"]]
    if unknown:
        st.error(
            f"Nie mam danych o zawodniku: **{', '.join(unknown)}**. "
            "Nie policzę dla niego nic ani nie podam sumy z obu zawodników. "
            "Zwykle chodzi o gracza z Challengerów albo ITF.")

    zastrzezenia = []
    nic = [f"{n} ({e['n']} meczów)" for n, e in ((p1, e1), (p2, e2))
           if e["known"] and not e.get("wiarygodny", True)]
    if nic:
        zastrzezenia.append(
            f"**{', '.join(nic)}** — przy takiej próbie prognoza to "
            f"praktycznie sama średnia tourowa "
            f"({100 * S.META['tour_ace_pct']:.1f}% asów), a nie wiedza o tym "
            "zawodniku. Baza obejmuje wyłącznie ATP Tour.")
    thin = [n for n, e in ((p1, e1), (p2, e2))
            if e["known"] and e.get("wiarygodny", True) and e["n"] < 25]
    if thin:
        zastrzezenia.append(
            f"**Mało meczów w bazie:** {', '.join(thin)}. Prognoza jest przez "
            "to przesunięta w stronę przeciętnego zawodnika i mniej pewna.")
    if (e1["known"] and not e1["ret_known"]) or \
            (e2["known"] and not e2["ret_known"]):
        zastrzezenia.append(
            "**Nie znam przeciwnika.** Nie wiem, jak dobrze odbiera serwis, "
            "więc pomijam tę poprawkę — a to najmocniejsza część modelu.")
    if S.data_age_days() > 45:
        zastrzezenia.append(
            f"**Dane sprzed {S.data_age_days()} dni.** Model nie zna meczów "
            "z ostatnich tygodni.")

    if zastrzezenia:
        with st.expander(f"⚠ Zastrzeżenia do tej estymacji "
                         f"({len(zastrzezenia)})"):
            for z in zastrzezenia:
                st.markdown(f"<div class='note'>{z}</div>",
                            unsafe_allow_html=True)

    t1, t2, t4, t3 = st.tabs(["Asy", "Podwójne błędy", "Przebieg meczu",
                              "H2H i forma"])
    with t1:
        stat_tab("ace", p1, p2, e1, e2, cfg, mkey)
    with t2:
        stat_tab("df", p1, p2, e1, e2, cfg, mkey)
    with t4:
        match_tab(p1, p2, cfg, mkey)
    with t3:
        h2h_tab(p1, p2, e1, e2, cfg, mkey)
