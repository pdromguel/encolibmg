import pytest


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Config, logs and backups go to a temp folder, never the real %APPDATA%."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture(autouse=True)
def portuguese():
    """Most tests assert the Portuguese texts; English has its own tests."""
    from encolibmg import i18n

    i18n.set_language("pt-BR")
    yield
    i18n.set_language("pt-BR")
