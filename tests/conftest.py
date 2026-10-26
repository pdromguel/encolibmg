import pytest


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Config, logs and backups go to a temp folder, never the real %APPDATA%."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture(autouse=True)
def portuguese(monkeypatch):
    """Most tests assert the Portuguese texts; English has its own tests.

    "auto" (the default setting, applied when Api starts) follows the Windows language, so it is pinned too:
    otherwise the tests would depend on the machine (CI runners are in English).
    """
    from encolibmg import i18n

    monkeypatch.setattr(i18n, "detect_language", lambda: "pt-BR")
    i18n.set_language("pt-BR")
    yield
    i18n.set_language("pt-BR")
