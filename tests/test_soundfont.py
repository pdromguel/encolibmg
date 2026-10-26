from threading import Event

import pytest

from encolibmg import soundfont
from encolibmg.errors import Cancelled
from encolibmg.library import Library
from encolibmg.manifest import read_manifest


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


def test_install_copies_and_registers_relative_path(lib, tmp_path):
    src = tmp_path / "Meu Piano.sf2"
    src.write_bytes(b"RIFF....sfbk")
    assert soundfont.install_soundfont(lib, src) == "SoundFonts/Meu Piano.sf2"
    assert (lib.path / "SoundFonts" / "Meu Piano.sf2").read_bytes() == b"RIFF....sfbk"
    data = read_manifest(lib.path)
    assert data["additionalContents"]["soundFont"] == "SoundFonts/Meu Piano.sf2"
    assert data["additionalContents"]["bgvCategories"] == []
    # same file again: reused, not duplicated
    assert soundfont.install_soundfont(lib, src) == "SoundFonts/Meu Piano.sf2"
    assert len(list((lib.path / "SoundFonts").iterdir())) == 1


def test_install_different_file_same_name_gets_unique_name(lib, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    (a / "gm.sf2").write_bytes(b"1")
    (b / "gm.sf2").write_bytes(b"22")
    soundfont.install_soundfont(lib, a / "gm.sf2")
    assert soundfont.install_soundfont(lib, b / "gm.sf2") == "SoundFonts/gm (2).sf2"


def test_rejects_other_formats(lib, tmp_path):
    (tmp_path / "x.mp3").write_bytes(b"")
    with pytest.raises(ValueError):
        soundfont.install_soundfont(lib, tmp_path / "x.mp3")


def test_remove(lib, tmp_path, monkeypatch):
    trashed = []
    monkeypatch.setattr(soundfont, "send2trash", trashed.append)
    (tmp_path / "gm.sf2").write_bytes(b"1")
    soundfont.install_soundfont(lib, tmp_path / "gm.sf2")
    soundfont.remove_soundfont(lib)
    assert soundfont.current_soundfont(lib) is None
    assert trashed == [str(lib.path / "SoundFonts" / "gm.sf2")]


class FakeResp:
    def __init__(self, body):
        self.body = body
        self.headers = {"content-length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        for i in range(0, len(self.body), 4):
            yield self.body[i:i + 4]


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, stream=True, timeout=None):
        self.urls.append(url)
        return FakeResp(b"LICENSE" if url.endswith(".txt") else b"RIFFsfbkdata")


def test_download_generaluser(lib):
    s, seen = FakeSession(), []
    assert soundfont.download_generaluser(lib, on_progress=seen.append, session=s) == "SoundFonts/GeneralUser-GS.sf2"
    assert (lib.path / "SoundFonts" / "GeneralUser-GS.sf2").read_bytes() == b"RIFFsfbkdata"
    assert (lib.path / "SoundFonts" / "GeneralUser-GS-LICENSE.txt").exists()
    assert seen[-1] == 1.0
    assert soundfont.current_soundfont(lib) == "SoundFonts/GeneralUser-GS.sf2"


def test_download_cancel_leaves_nothing(lib):
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        soundfont.download_generaluser(lib, cancel=cancel, session=FakeSession())
    assert list((lib.path / "SoundFonts").iterdir()) == []
    assert soundfont.current_soundfont(lib) is None
