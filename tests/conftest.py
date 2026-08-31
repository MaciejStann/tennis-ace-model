"""Wspólne przygotowanie dla testów. Bez sieci i bez klucza API."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def db():
    """Prawdziwa baza. Jeśli jej nie ma, testy jej wymagające są pomijane."""
    import model as M
    try:
        return M.load()
    except FileNotFoundError:
        pytest.skip("brak data/ — uruchom `python build_db.py`")


@pytest.fixture(scope="session")
def names(db):
    players, _, _, _ = db
    return sorted(players[players.matches >= 5].index.tolist())
