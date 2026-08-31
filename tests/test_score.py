"""
Odwracanie wyniku.

W danych `score` jest ZAWSZE z perspektywy zwycięzcy. Wyświetlony przy
przegranym bez odwrócenia kłamie — ten błąd wystąpił w aplikacji.
"""
import model as M
import update_db as U
import pytest


class TestFlipScore:
    @pytest.mark.parametrize("wejscie,oczekiwane", [
        ("6-3 6-3", "3-6 3-6"),
        ("7-6(2) 6-4", "6-7(2) 4-6"),
        ("6-2 3-6 6-1 6-4", "2-6 6-3 1-6 4-6"),
        ("7-6(4) 6-7(5) 7-5", "6-7(4) 7-6(5) 5-7"),
    ])
    def test_odwraca(self, wejscie, oczekiwane):
        assert M.flip_score(wejscie) == oczekiwane

    def test_tiebreak_zachowuje_punkty(self):
        # 7-6(2) -> 6-7(2): numer w nawiasie NIE jest odwracany
        assert M.flip_score("7-6(2)") == "6-7(2)"

    @pytest.mark.parametrize("znacznik", ["RET", "W/O", "DEF", "ABD"])
    def test_znaczniki_bez_zmian(self, znacznik):
        assert M.flip_score(f"5-0 {znacznik}") == f"0-5 {znacznik}"

    def test_pusty(self):
        assert M.flip_score("") == ""

    def test_podwojne_odwrocenie_daje_oryginal(self):
        for s in ("6-3 7-6(2)", "6-2 3-6 6-1 6-4", "5-0 RET"):
            assert M.flip_score(M.flip_score(s)) == s


class TestGamesFromScore:
    @pytest.mark.parametrize("wynik,gemy", [
        ("7-5 6-3", (13, 8)),
        ("6-7(3) 7-6(4) 6-1", (19, 14)),
        ("6-4 6-4 6-4", (18, 12)),
        ("6-0 6-0", (12, 0)),
    ])
    def test_liczy_gemy(self, wynik, gemy):
        assert U.games_from_score(wynik) == gemy

    def test_ignoruje_znaczniki(self):
        assert U.games_from_score("5-0 RET") == (5, 0)

    def test_pusty_zwraca_none(self):
        assert U.games_from_score("") is None
        assert U.games_from_score("W/O") is None
