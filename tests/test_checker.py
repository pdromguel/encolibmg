import subprocess

import pytest

from encolibmg import checker
from encolibmg.library import Library
from encolibmg.lyrics.lrclib import LyricsCandidate


def sine(path, seconds=2):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f=440:d={seconds}",
                    str(path)], check=True)
    return path


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


def kinds(issues):
    return sorted(i.kind for i in issues)


def test_clean_library_has_no_issues(lib):
    from encolibmg.tags import write_tags

    write_tags(sine(lib.path / "A - B.multiplexed.mp3"), "A", "B")
    (lib.path / "A - B.lrc").write_text("[00:01.00] oi\n", encoding="utf-8")
    (lib.path / "A - B.guide.mid").write_bytes(b"")
    assert checker.check(lib) == []


def test_detects_each_problem(lib):
    (lib.path / ".encore-tmp-123").mkdir()
    sub = lib.path / "Old"
    sub.mkdir()
    (sub / "X - Y.mp4").write_bytes(b"")
    sine(lib.path / "C - D.flac")
    sine(lib.path / "E - F.mp3")                       # orphan + missing tags
    (lib.path / "G - H.mp4").write_bytes(b"")
    (lib.path / "G - H.lrc").write_text("[offset:100]\n[00:01.00]x", encoding="utf-8")
    (lib.path / "SemTraço.mp4").write_bytes(b"")
    (lib.path / "I - J.mp4").write_bytes(b"")
    (lib.path / "i - j!.mp4").write_bytes(b"")
    found = checker.check(lib)
    assert kinds(found) == sorted(["temp_leftover", "subfolder", "unsupported", "orphan", "missing_tags",
                                   "bad_lrc", "bad_name", "duplicate", "duplicate"])
    by = {i.kind: i for i in found}
    assert by["bad_name"].fixable is False and by["duplicate"].fixable is False
    assert by["orphan"].fixable


def test_crlf_and_bom_lrc_are_fine(lib):
    # Encore trims lines and matches the stamp anywhere, so these play correctly
    (lib.path / "A - B.mp4").write_bytes(b"")
    (lib.path / "A - B.lrc").write_bytes("﻿[00:01.00] oi\r\n[00:02.00] la\r\n".encode("utf-8"))
    assert checker.check(lib) == []


def fix_all(lib, search=None):
    return {i.kind: checker.fix(lib, i, search=search) for i in checker.check(lib) if i.fixable}


def test_fixes(lib, tmp_path):
    (lib.path / ".encore-tmp-1").mkdir()
    sub = lib.path / "Old"
    sub.mkdir()
    (sub / "X - Y.mp4").write_bytes(b"")
    sine(lib.path / "C - D.flac")
    (lib.path / "G - H.mp4").write_bytes(b"")
    (lib.path / "G - H.lrc").write_text("[offset:100]\n[00:01.00]x", encoding="utf-8")
    fix_all(lib)
    names = sorted(p.name for p in lib.path.iterdir() if p.is_file())
    assert names == ["C - D.mp3", "G - H.lrc", "G - H.mp4", "X - Y.mp4", "manifest.json"]
    assert not (lib.path / ".encore-tmp-1").exists()
    assert (lib.path / "G - H.lrc").read_text(encoding="utf-8") == "[00:00.90] x\n"
    assert list((tmp_path / "appdata" / "EncoLibMG" / "backups").rglob("G - H.lrc"))
    # second pass: the converted mp3 now shows as orphan audio (no lyrics) — nothing else
    assert kinds(checker.check(lib)) == ["missing_tags", "orphan"]


def test_fix_orphan_finds_lyrics_by_duration(lib):
    sine(lib.path / "E - F.mp3", seconds=3)
    good = LyricsCandidate(1, "E", "F", "", 3.5, "[00:01.0]la", None)
    far = LyricsCandidate(2, "E", "F", "", 60.0, "[00:01.0]no", None)
    issue = next(i for i in checker.check(lib) if i.kind == "orphan")
    msg = checker.fix(lib, issue, search=lambda q: [far, good])
    assert "letra encontrada" in msg
    assert (lib.path / "E - F.lrc").read_text(encoding="utf-8") == "[00:01.00] la\n"


def test_fix_orphan_without_match_raises(lib):
    sine(lib.path / "E - F.mp3", seconds=3)
    issue = next(i for i in checker.check(lib) if i.kind == "orphan")
    with pytest.raises(LookupError):
        checker.fix(lib, issue, search=lambda q: [])


def test_loudness_check_and_fix(lib):
    p = lib.path / "A - B.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=3",
                    "-f", "lavfi", "-i", "sine=f=440:d=3", "-af", "volume=-25dB", "-c:v", "libx264",
                    "-c:a", "aac", "-shortest", str(p)], check=True)
    issues = checker.check(lib, include_loudness=True)
    assert kinds(issues) == ["loudness"]
    checker.fix(lib, issues[0])
    assert checker.check(lib, include_loudness=True) == []


def test_asset_folders_and_manifest_files_are_not_subfolder_issues(lib):
    import json

    for d in ("BGV/Praias", "Bumpers", "Boot", "Narrations", "SoundFonts"):
        (lib.path / d).mkdir(parents=True)
    (lib.path / "BGV" / "Praias" / "mar.mp4").write_bytes(b"")
    (lib.path / "Boot" / "boot.mp4").write_bytes(b"")
    (lib.path / "Narrations" / "0-69.mp3").write_bytes(b"")
    (lib.path / "Extras").mkdir()
    (lib.path / "Extras" / "fundo.mp4").write_bytes(b"")      # referenced by the manifest: fine
    (lib.path / "Extras" / "solta.mp4").write_bytes(b"")      # a real stray song file
    data = json.loads((lib.path / "manifest.json").read_text(encoding="utf-8"))
    data["additionalContents"]["bgvCategories"] = [{"BGV_CATEGORY": "X", "BGV_LIST": ["Extras/fundo.mp4"]}]
    (lib.path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    found = [(i.kind, i.path.name) for i in checker.check(lib)]
    assert found == [("subfolder", "solta.mp4")]
