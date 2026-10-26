import json
import subprocess

import pytest

from encolibmg.library import visual
from encolibmg.library import Library
from encolibmg.library.manifest import read_manifest
from encolibmg.youtube import VideoCandidate


def video(path, seconds=1, audio=True, size="320x240", codec="libx264"):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=blue:s={size}:d={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=d={seconds}", "-shortest"]
    cmd += ["-c:v", codec, str(path)]
    subprocess.run(cmd, check=True)
    return path


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,height",
                          "-of", "json", str(path)], capture_output=True, text=True).stdout
    return json.loads(out)["streams"]


@pytest.fixture
def lib(tmp_path):
    return Library.create(tmp_path / "EncoreLibrary", "t")


@pytest.fixture
def trashed(monkeypatch):
    out = []
    monkeypatch.setattr(visual, "send2trash", out.append)
    return out


def extra(lib):
    return read_manifest(lib.path)["additionalContents"]


def test_categories_add_rename_remove(lib, tmp_path, trashed):
    assert visual.add_category(lib, "Natureza: 4K?") == "Natureza 4K"
    with pytest.raises(ValueError):
        visual.add_category(lib, "natureza 4k")
    rel = visual.add_bgv_file(lib, "Natureza 4K", video(tmp_path / "mar.mov"))
    assert rel == "BGV/Natureza 4K/mar.mp4"
    assert visual.rename_category(lib, "Natureza 4K", "Praias") == "Praias"
    assert extra(lib)["bgvCategories"] == [{"BGV_CATEGORY": "Praias", "BGV_LIST": [rel]}]
    visual.remove_category(lib, "Praias")
    assert extra(lib)["bgvCategories"] == []
    assert trashed == [str(lib.path / rel)]


def test_bgv_is_h264_without_audio_and_unique_names(lib, tmp_path):
    visual.add_category(lib, "Cidade")
    src = video(tmp_path / "rua.webm", codec="libvpx-vp9")
    a = visual.add_bgv_file(lib, "Cidade", src)
    b = visual.add_bgv_file(lib, "Cidade", src)
    assert (a, b) == ("BGV/Cidade/rua.mp4", "BGV/Cidade/rua (2).mp4")
    assert probe(lib.path / a) == [{"codec_name": "h264", "codec_type": "video", "height": 240}]


def test_ready_bgv_is_copied_not_reencoded(lib, tmp_path):
    visual.add_category(lib, "X")
    src = video(tmp_path / "ok.mp4", audio=False)
    rel = visual.add_bgv_file(lib, "X", src)
    assert (lib.path / rel).read_bytes() == src.read_bytes()


def test_add_bgv_from_youtube_moves_download(lib, tmp_path, monkeypatch):
    visual.add_category(lib, "YT")
    seen = {}

    def fake_download(url, dest, cancel=None, cb=None, video_only=False, section=None):
        seen["section"] = section
        seen["video_only"] = video_only
        return video(dest / "video.mp4", audio=False)

    monkeypatch.setattr(visual.youtube, "download_video", fake_download)
    rel = visual.add_bgv_video(lib, "YT", VideoCandidate("i", "Drone: Rio 4K", "c", 3 * 3600.0, "u"))
    assert rel == "BGV/YT/Drone Rio 4K.mp4" and seen["video_only"]
    assert seen["section"] == (30.0, 330.0)  # 3-hour video: only 5 minutes after the intro
    assert not list(lib.path.glob(".encore-tmp-*"))


def test_remove_bgv(lib, tmp_path, trashed):
    visual.add_category(lib, "X")
    rel = visual.add_bgv_file(lib, "X", video(tmp_path / "a.mp4", audio=False))
    visual.remove_bgv(lib, "X", rel)
    assert extra(lib)["bgvCategories"][0]["BGV_LIST"] == []
    assert trashed == [str(lib.path / rel)]


def test_bumpers(lib, tmp_path, trashed):
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")
    assert visual.add_bumper(lib, tmp_path / "logo.png") == "Bumpers/logo.png"
    assert visual.add_bumper(lib, tmp_path / "logo.png") == "Bumpers/logo (2).png"
    with pytest.raises(ValueError):
        visual.add_bumper(lib, tmp_path / "x.bmp")
    visual.remove_bumper(lib, "Bumpers/logo.png")
    assert visual.bumpers(lib) == ["Bumpers/logo (2).png"]


def test_boot_video(lib, tmp_path, trashed):
    assert visual.set_boot_video(lib, video(tmp_path / "intro.mov")) == "Boot/boot.mp4"
    kinds = sorted(s["codec_type"] for s in probe(lib.path / "Boot" / "boot.mp4"))
    assert kinds == ["audio", "video"]
    visual.set_boot_video(lib, video(tmp_path / "intro2.mov"))  # replaces; old one goes to the bin
    assert trashed == [str(lib.path / "Boot" / "boot.mp4")]
    visual.clear_boot_video(lib)
    assert visual.boot_video(lib) is None


def test_narrations(lib, tmp_path, trashed):
    (tmp_path / "aplausos.mp3").write_bytes(b"ID3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=1", str(tmp_path / "x.flac")],
                   check=True)
    assert visual.set_narration(lib, 90, 100, tmp_path / "aplausos.mp3") == "Narrations/90-100.mp3"
    assert visual.set_narration(lib, 0, 69, tmp_path / "x.flac") == "Narrations/0-69.mp3"  # converted
    with pytest.raises(ValueError):
        visual.set_narration(lib, 60, 95, tmp_path / "aplausos.mp3")  # overlaps both
    with pytest.raises(ValueError):
        visual.set_narration(lib, 80, 70, tmp_path / "aplausos.mp3")
    visual.set_narration(lib, 90, 100, tmp_path / "aplausos.mp3")  # same range: replaces
    assert [(n["min"], n["max"]) for n in visual.narrations(lib)] == [(0, 69), (90, 100)]
    assert trashed == [str(lib.path / "Narrations" / "90-100.mp3")]
    visual.remove_narration(lib, 0, 69)
    visual.remove_narration(lib, 90, 100)
    assert "scoreNarrations" not in extra(lib)


def test_unknown_manifest_keys_survive(lib, tmp_path):
    data = read_manifest(lib.path)
    data["additionalContents"]["soundFont"] = "SoundFonts/gm.sf2"
    data["custom"] = 1
    (lib.path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    visual.add_category(lib, "A")
    after = read_manifest(lib.path)
    assert after["custom"] == 1 and after["additionalContents"]["soundFont"] == "SoundFonts/gm.sf2"


def test_bgv_section():
    assert visual.bgv_section(None) is None
    assert visual.bgv_section(200) is None          # short: whole video
    assert visual.bgv_section(320) == (0.0, 300.0)  # just over: from the start
    assert visual.bgv_section(42897) == (30.0, 330.0)


def test_remove_never_touches_files_outside_the_library(lib, tmp_path, trashed):
    import json

    outside = tmp_path / "importante.txt"
    outside.write_text("não apague")
    data = read_manifest(lib.path)
    data["additionalContents"]["bgvCategories"] = [{"BGV_CATEGORY": "X", "BGV_LIST": ["../importante.txt"]}]
    data["additionalContents"]["bumperImages"] = ["../importante.txt"]
    (lib.path / "manifest.json").write_text(json.dumps(data), encoding="utf-8")
    visual.remove_bumper(lib, "../importante.txt")
    visual.remove_bgv(lib, "X", "../importante.txt")
    visual.add_category(lib, "Y")
    visual.remove_category(lib, "X")
    assert trashed == [] and outside.exists()


def test_remove_only_trashes_listed_files(lib, tmp_path, trashed):
    (lib.path / "Bumpers").mkdir()
    (lib.path / "Bumpers" / "solto.png").write_bytes(b"")
    visual.remove_bumper(lib, "Bumpers/solto.png")  # not in the manifest: leave it alone
    assert trashed == []
