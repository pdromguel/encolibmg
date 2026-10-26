import pytest


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Config, logs and backups go to a temp folder, never the real %APPDATA%."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
