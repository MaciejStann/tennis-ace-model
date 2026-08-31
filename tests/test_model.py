"""Estymacja, rozkłady, obsługa braku danych."""
import json
import numpy as np
import pandas as pd
import pytest

import model as M


class TestBrakDanych:
    """Nieznany zawodnik ma zwracać None, NIGDY średniej tourowej.
    Liczba udająca estymację jest gorsza niż jej brak."""

    def test_nieznany_serwujacy_zwraca_none(self, db):
        P, MT, C, MA = db
        e = M.estimate(P, MT, C, "Jan Kowalski", "Alexander Bublik",
                       "Hard", False, 73, MA)
        assert e["mu_ace"] is None
        assert e["mu_df"] is None
        assert e["known"] is False

    def test_nieznany_returner_nie_blokuje(self, db):
        P, MT, C, MA = db
        e = M.estimate(P, MT, C, "Alexander Bublik", "Jan Kowalski",
                       "Hard", False, 73, MA)
        assert e["mu_ace"] is not None
        assert e["ret_known"] is False   # mnożnik 1.0 = brak danych

    def test_bez_bazy_meczow_nie_wywala(self, db):
        P, MT, C, _ = db
        e = M.estimate(P, MT, C, "Alexander Bublik", "Alex de Minaur",
                       "Hard", False, 73, None)
        assert e["mu_ace"] is not None


class TestNawierzchnie:
    """55% zawodników nie ma meczu na trawie — int(NaN) wywalał aplikację."""

    def test_brak_meczow_na_nawierzchni(self, db):
        P, MT, C, MA = db
        bez_trawy = P[P.n_grass.isna()]
        if bez_trawy.empty:
            pytest.skip("wszyscy grali na trawie")
        nm = bez_trawy.index[0]
        r = M.player_rates(P, MT, nm, "Grass")
        assert r["n_surf"] == 0
        assert r["ace"] is not None

    def test_nie_mnozy_podwojnie(self, db):
        """ace_{surface} z bazy JEST już skorygowane — fallback tylko przy braku."""
        P, MT, C, MA = db
        r = M.player_rates(P, MT, "Alexander Bublik", "Clay")
        assert abs(r["ace"] - P.loc["Alexander Bublik", "ace_clay"]) < 1e-12


class TestKelly:
    def test_sufit_10_procent(self):
        assert M.kelly(0.999, 1.5, 1.0) <= 0.10

    def test_zero_przy_ujemnym_ev(self):
        assert M.kelly(0.4, 2.0, 0.25) == 0.0

    def test_zero_przy_kursie_1(self):
        assert M.kelly(0.9, 1.0, 0.25) == 0.0

    def test_rosnie_z_przewaga(self):
        a = M.kelly(0.55, 2.0, 0.25)
        b = M.kelly(0.65, 2.0, 0.25)
        assert 0 < a < b


class TestRozklad:
    def test_p_over_maleje_z_linia(self):
        p = [M.p_over(L, 8.0, 24.0) for L in (3.5, 5.5, 8.5, 12.5)]
        assert p == sorted(p, reverse=True)

    def test_p_over_w_zakresie(self):
        for mu in (0.5, 6, 30):
            for L in (0.5, 8.5, 60.5):
                assert 0.0 <= M.p_over(L, mu, 24.0) <= 1.0

    def test_p_over_nie_zwraca_dokladnie_jeden(self):
        """Kelly bez sufitu eksplodował przy p=1.0."""
        assert M.p_over(0.5, 50, 24.0) < 1.0


class TestLoad:
    """calib.json bywa nadpisywany przez różne skrypty — brak klucza
    nie może wywalić aplikacji."""

    @pytest.mark.parametrize("tresc", [
        "{}",
        '{"form": {}}',
        '{nieprawidlowy json',
        '{"calib_c": 1.05}',
    ])
    def test_niekompletny_calib(self, tmp_path, monkeypatch, tresc, db):
        import shutil
        src = M.DATA
        d = tmp_path / "data"
        d.mkdir()
        for f in ("players.csv", "meta.json"):
            shutil.copy(src / f, d / f)
        (d / "calib.json").write_text(tresc)
        monkeypatch.setattr(M, "DATA", d)
        _, _, C, _ = M.load()
        assert "calib_c" in C and "nb_r" in C and "form" in C
