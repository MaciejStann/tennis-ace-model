"""
Dopasowanie nazwisk z terminarza do bazy.

Historia: pierwsza wersja szukała nazwiska jako najdłuższego członu, przez co
"BUBLIK Alexander" trafiało w imię. Poprawka była zbyt permisywna i "Taylor
Townsend" (WTA) dawało "Taylor Fritz". Oba przypadki są tu zamrożone.
"""
import model as M


def _m(q, names):
    return M.match_name(q, names, {})[0]


class TestFormatyZapisu:
    def test_dokladne(self, names):
        assert _m("Ben Shelton", names) == "Ben Shelton"

    def test_nazwisko_wersalikami(self, names):
        assert _m("SHELTON Ben", names) == "Ben Shelton"

    def test_nazwisko_z_inicjalem(self, names):
        assert _m("Shelton B.", names) == "Ben Shelton"

    def test_nazwisko_pierwsze_wersalikami(self, names):
        # regresja: najdłuższym członem jest "Alexander", nie "Bublik"
        assert _m("BUBLIK Alexander", names) == "Alexander Bublik"

    def test_samo_nazwisko(self, names):
        assert _m("Bublik", names) == "Alexander Bublik"

    def test_male_litery(self, names):
        assert _m("alexander bublik", names) == "Alexander Bublik"

    def test_czlon_nazwiska_malymi(self, names):
        assert _m("Alex De Minaur", names) == "Alex de Minaur"


class TestRozroznianie:
    def test_bracia_zverev_po_imieniu(self, names):
        assert _m("ZVEREV Alexander", names) == "Alexander Zverev"
        assert _m("ZVEREV Mischa", names) == "Mischa Zverev"

    def test_bracia_zverev_po_inicjale(self, names):
        assert _m("Zverev A.", names) == "Alexander Zverev"


class TestCoNieMozeTrafic:
    def test_imie_nie_wystarcza(self, names):
        # regresja: "Taylor" nie może dać "Taylor Fritz"
        assert _m("Taylor", names) is None

    def test_inne_nazwisko_to_samo_imie(self, names):
        # regresja: zawodniczka WTA nie może trafić w zawodnika ATP
        assert _m("Taylor Townsend", names) is None

    def test_nieznany_zawodnik(self, names):
        assert _m("Jan Kowalski", names) is None

    def test_pusty_string(self, names):
        assert _m("", names) is None


class TestPewnosc:
    def test_dokladne_ma_pewnosc_1(self, names):
        assert M.match_name("Ben Shelton", names, {})[1] == 1.0

    def test_przyblizone_ma_nizsza_pewnosc(self, names):
        assert M.match_name("Shelton B.", names, {})[1] < 1.0

    def test_brak_trafienia_ma_pewnosc_0(self, names):
        assert M.match_name("Jan Kowalski", names, {})[1] == 0.0
