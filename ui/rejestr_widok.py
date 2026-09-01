"""Widok rejestru zakladow: zapis, rozliczenie, skumulowany wynik."""
import pandas as pd
import streamlit as st

import rejestr as R
import ui.stan as S


def przycisk_zapisu(p1, p2, cfg, rynek, strona, linia, kurs, p_model, ev,
                    stawka, klucz):
    """Zapisuje zaklad z biezacego ekranu wyceny."""
    if st.button("Zapisz do rejestru", key=f"zap_{klucz}",
                 help="Zapisuje prognozę i kurs w chwili obstawiania. "
                      "Wynik uzupełnisz później w zakładce Rejestr."):
        R.dopisz(p1=p1, p2=p2, nawierzchnia=cfg["surface"], rynek=rynek,
                 strona=strona, linia=linia, kurs=kurs,
                 p_model=round(p_model, 4), ev=round(ev, 4),
                 stawka=round(stawka, 2),
                 data_meczu=(cfg.get("start") or "")[:10])
        st.success("Zapisano.")


def view_rejestr():
    st.markdown("<div class='eyebrow' style='margin-top:0'>Rejestr zakładów"
                "</div>", unsafe_allow_html=True)
    d = R.wczytaj()
    if d.empty:
        st.info("Rejestr jest pusty. Zapisz pierwszy zakład przyciskiem "
                "„Zapisz do rejestru” w wycenie meczu.")
        st.markdown(
            "<div class='note'>Po co to: walidacja modelu mierzy dokładność "
            "wobec <b>rzeczywistości</b> (MAE 2,62 asa), nigdy wobec "
            "<b>kursów</b>. Model trafiający w 80% na faworytach przy kursie "
            "1,20 traci pieniądze. Dopiero zapis realnych zakładów pokaże, "
            "czy przewaga istnieje.</div>", unsafe_allow_html=True)
        return

    s = R.podsumowanie(d)
    if s["n"]:
        c = st.columns(4, gap="medium")
        c[0].metric("Rozliczone", s["n"], f"{s['otwarte']} otwartych",
                    delta_color="off")
        c[1].metric("Skuteczność", f"{100 * s['skutecznosc']:.0f}%")
        c[2].metric("Zysk", f"{s['zysk']:+.0f}", f"obrót {s['obrot']:.0f}",
                    delta_color="off")
        c[3].metric("ROI", f"{100 * s['roi']:+.1f}%",
                    f"zakładany {100 * s['ev_oczekiwany']:+.1f}%",
                    delta_color="off")

        # To jest sedno: czy realny wynik dogania to, co model obiecywal.
        roznica = s["roi"] - s["ev_oczekiwany"]
        if s["n"] < 30:
            st.markdown(
                f"<div class='note'>Przy <b>{s['n']}</b> zakładach wynik jest "
                f"jeszcze przypadkiem — na sensowną ocenę trzeba około stu. "
                f"Model zakładał {100 * s['ev_oczekiwany']:+.1f}%, wyszło "
                f"{100 * s['roi']:+.1f}%.</div>", unsafe_allow_html=True)
        else:
            kol = S.GOOD if roznica > -0.02 else S.BAD
            st.markdown(
                f"<div class='band' style='border-color:{kol}'>"
                f"Model zakładał <b>{100 * s['ev_oczekiwany']:+.1f}%</b>, "
                f"wyszło <b style='color:{kol}'>{100 * s['roi']:+.1f}%</b>. "
                f"Różnica {100 * roznica:+.1f} pp.</div>",
                unsafe_allow_html=True)

        kal = R.kalibracja(d)
        if kal:
            st.markdown("<div class='eyebrow'>Czy prawdopodobieństwa są "
                        "prawdziwe</div>", unsafe_allow_html=True)
            wiersze = "".join(
                f"<tr><td>{k['zakres']}</td><td>{k['n']}</td>"
                f"<td>{100 * k['model']:.0f}%</td>"
                f"<td>{100 * k['fakt']:.0f}%</td></tr>" for k in kal)
            st.markdown(
                f"<table class='tbl'><thead><tr><th>Koszyk</th><th>n</th>"
                f"<th>Model</th><th>Fakt</th></tr></thead>"
                f"<tbody>{wiersze}</tbody></table>", unsafe_allow_html=True)

    st.markdown("<div class='eyebrow'>Zakłady</div>", unsafe_allow_html=True)
    otwarte = d[~d.wynik.isin(["W", "P"])]
    if not otwarte.empty:
        st.markdown("<div class='sub'>Nierozliczone — uzupełnij wynik:</div>",
                    unsafe_allow_html=True)
    for i, r in otwarte.iloc[::-1].iterrows():
        c = st.columns([6, 1, 1, 1])
        c[0].markdown(
            f"<div class='row-meta' style='text-align:left'>"
            f"<b>{r.p1} vs {r.p2}</b> · {r.rynek} {r.strona} "
            f"{r.linia if pd.notna(r.linia) else ''} · kurs {r.kurs} · "
            f"stawka {r.stawka}</div>", unsafe_allow_html=True)
        if c[1].button("Wygrany", key=f"w{i}"):
            R.rozlicz(i, True)
            st.rerun()
        if c[2].button("Przegrany", key=f"p{i}"):
            R.rozlicz(i, False)
            st.rerun()
        if c[3].button("Usuń", key=f"u{i}"):
            R.usun(i)
            st.rerun()

    rozliczone = d[d.wynik.isin(["W", "P"])]
    if not rozliczone.empty:
        with st.expander(f"Historia ({len(rozliczone)})"):
            pok = rozliczone[["data_meczu", "p1", "p2", "rynek", "strona",
                              "linia", "kurs", "stawka", "wynik", "zysk"]]
            st.markdown(pok.iloc[::-1].to_html(index=False,
                                               classes="tbl", border=0),
                        unsafe_allow_html=True)
