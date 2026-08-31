"""
Parser odpowiedzi Tennis API.

Struktura: stats.player1 / stats.player2 jako ZAGNIEŻDŻONE obiekty.
W archiwum player1 to zwycięzca, więc gdy nasz zawodnik przegrał, jego
statystyki są pod player2 — czytanie na sztywno dałoby dane przeciwnika.
"""
import update_db as U


def mecz(pid_p1, pid_p2, ace1, ace2, **kw):
    d = {
        "date": "2026-08-26T02:00:00.000Z",
        "player1Id": pid_p1, "player2Id": pid_p2,
        "player1": {"id": pid_p1, "name": "Gracz A"},
        "player2": {"id": pid_p2, "name": "Gracz B"},
        "result": "7-5 6-3", "best_of": None,
        "tournament": {"name": "Test", "court": {"name": "Hard"},
                       "rank": {"name": "Main tour"}},
        "stats": {
            "player1": {"aces": ace1, "doubleFaults": 3, "firstServeOf": 66},
            "player2": {"aces": ace2, "doubleFaults": 4, "firstServeOf": 57},
        },
    }
    d.update(kw)
    return {"data": [d]}


class TestWyborZawodnika:
    def test_nasz_zawodnik_jako_player1(self):
        r = U.parse_matches(mecz(100, 200, 8, 10), "Gracz A", 100)
        assert r[0]["ace"] == 8
        assert r[0]["opp"] == "Gracz B"

    def test_nasz_zawodnik_jako_player2(self):
        """Regresja: czytanie aces1 na sztywno dałoby 8 zamiast 10."""
        r = U.parse_matches(mecz(200, 100, 8, 10), "Gracz B", 100)
        assert r[0]["ace"] == 10
        assert r[0]["opp"] == "Gracz A"

    def test_svpt_z_wlasciwego_obiektu(self):
        r = U.parse_matches(mecz(200, 100, 8, 10), "Gracz B", 100)
        assert r[0]["svpt"] == 57


class TestPolaMeczu:
    def test_gemy_z_wyniku_nie_z_szacunku(self):
        r = U.parse_matches(mecz(100, 200, 8, 10), "Gracz A", 100)
        assert r[0]["svgms"] == 13      # 7+6 dla player1

    def test_data_bez_myslnikow(self):
        r = U.parse_matches(mecz(100, 200, 8, 10), "Gracz A", 100)
        assert r[0]["tourney_date"] == 20260826

    def test_hala_z_nazwy_kortu(self):
        m = mecz(100, 200, 8, 10)
        m["data"][0]["tournament"]["court"]["name"] = "I.Hard"
        assert U.parse_matches(m, "Gracz A", 100)[0]["indoor"] == "I"

    def test_grand_slam_daje_bo5(self):
        m = mecz(100, 200, 8, 10)
        m["data"][0]["tournament"]["rank"]["name"] = "Grand Slam"
        assert U.parse_matches(m, "Gracz A", 100)[0]["best_of"] == 5

    def test_main_tour_daje_bo3(self):
        assert U.parse_matches(mecz(100, 200, 8, 10),
                               "Gracz A", 100)[0]["best_of"] == 3

    def test_zwyciezca_z_match_winner(self):
        m = mecz(100, 200, 8, 10)
        m["data"][0]["match_winner"] = 100
        r = U.parse_matches(m, "Gracz A", 100)
        assert r[0]["won"] == 1


class TestOdpornosc:
    def test_mecz_bez_statystyk_pominiety(self):
        m = mecz(100, 200, 8, 10)
        m["data"][0]["stats"] = {}
        assert U.parse_matches(m, "Gracz A", 100) == []

    def test_pusta_odpowiedz(self):
        assert U.parse_matches({"data": []}, "Gracz A", 100) == []

    def test_smieci_zamiast_danych(self):
        assert U.parse_matches({"blad": "x"}, "Gracz A", 100) == []

    def test_nieznany_zawodnik_pominiety(self):
        assert U.parse_matches(mecz(100, 200, 8, 10), "Ktos Inny", 999) == []


class TestWyszukiwanieId:
    def test_id_ze_sciezki_zdjecia(self):
        """Profil nie ma pola id — numer siedzi w nazwie pliku zdjęcia."""
        prof = {"name": "X", "image": "/tennis/api2/uploads/Photo/atp/22807.jpg"}
        assert U.deep_id(prof) == 22807

    def test_ignoruje_sciezke_bez_numeru(self):
        prof = {"image": "/tennis/api2/uploads/Photo/atp_name/daniil.jpg"}
        assert U.deep_id(prof) is None

    def test_pole_id_ma_pierwszenstwo(self):
        assert U.deep_id({"data": {"player": {"id": 555}}}) == 555
