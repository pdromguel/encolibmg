"""Library health check: finds what Encore would ignore or show wrong, and fixes it."""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from send2trash import send2trash

from encolibmg.audio import loudness
from encolibmg.audio.convert import (UNSUPPORTED_AUDIO, UNSUPPORTED_VIDEO, convert_audio,
                                      convert_video, duration)
from encolibmg.errors import Cancelled
from encolibmg.library import (AUDIO_EXTS, LYRIC_EXTS, MIDI_EXTS, VIDEO_EXTS, Library, Track,
                                _split_base, _strip_ext)
from encolibmg.lyrics.match import find_synced, read_lrc
from encolibmg.lyrics.normalize import normalize_lrc
from encolibmg.manifest import ensure_additional, read_manifest, write_manifest
from encolibmg.midi_info import midi_has_lyrics
from encolibmg.paths import backup_file
from encolibmg.tags import write_tags

MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS | MIDI_EXTS | LYRIC_EXTS | UNSUPPORTED_AUDIO | UNSUPPORTED_VIDEO

KIND_LABEL = {
    "orphan": "Áudio sem letra",
    "bad_lrc": "Letra fora do padrão",
    "unsupported": "Formato não aceito",
    "subfolder": "Em subpasta",
    "temp_leftover": "Pasta temporária",
    "missing_tags": "Sem tags",
    "loudness": "Volume",
    "bad_name": "Nome fora do padrão",
    "duplicate": "Possível duplicata",
    "no_guide": "Sem guia MIDI",
    "midi_no_lyrics": "MIDI sem letra",
    "manifest_incomplete": "Manifest incompleto",
}


# folders the app (and Encore's manifest) use for library assets, not songs
ASSET_DIRS = {"bgv", "bumpers", "boot", "narrations", "soundfonts"}


def _manifest_files(root: Path) -> set[Path]:
    """Every file the manifest points to (BGV lists, bumpers, boot video, narrations, SoundFont)."""
    try:
        extra = read_manifest(root).get("additionalContents") or {}
    except (OSError, ValueError):
        return set()
    rels = [v for c in extra.get("bgvCategories") or [] for v in c.get("BGV_LIST", [])]
    rels += list(extra.get("bumperImages") or []) + [n.get("file") for n in extra.get("scoreNarrations") or []]
    rels += [extra.get("bootVideo"), extra.get("soundFont")]
    return {(root / r).resolve() for r in rels if isinstance(r, str) and r}


@dataclass
class Issue:
    kind: str
    path: Path
    message: str
    fixable: bool
    track: Track | None = None
    extra: dict = field(default_factory=dict)


def _has_tags(mp3: Path) -> bool:
    from mutagen.id3 import ID3, ID3NoHeaderError

    try:
        tags = ID3(mp3)
    except (ID3NoHeaderError, Exception):
        return False
    return bool(tags.getall("TPE1")) and bool(tags.getall("TIT2"))


def _dup_key(track: Track) -> str:
    return re.sub(r"[\W_]+", "", f"{track.artist}{track.title}".casefold())


def check(lib: Library, include_loudness: bool = False, cancel: Event | None = None,
          on_progress=None) -> list[Issue]:
    issues: list[Issue] = []
    root = lib.path

    try:
        if ensure_additional(read_manifest(root)):
            issues.append(Issue("manifest_incomplete", root / "manifest.json", "Sem 'additionalContents': o Encore "
                                "não cria a categoria MTV nem lê vídeos de fundo desta biblioteca.", True))
    except (OSError, ValueError):
        pass

    referenced = _manifest_files(root)
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            if entry.name.startswith(".encore-tmp-"):
                issues.append(Issue("temp_leftover", entry, "Sobra de um download interrompido.", True))
                continue
            if entry.name.lower() in ASSET_DIRS:
                continue  # BGVs, bumpers, boot video, narrations and SoundFonts live in subfolders on purpose
            for f in sorted(entry.rglob("*")):
                if f.is_file() and f.suffix.lower() in MEDIA_EXTS and f.resolve() not in referenced:
                    free = not (root / f.name).exists()
                    issues.append(Issue("subfolder", f, f"O Encore só lê a raiz: {f.relative_to(root)}"
                                        + ("" if free else " (já existe um arquivo com esse nome na raiz)"),
                                        free))
        elif entry.suffix.lower() in UNSUPPORTED_AUDIO | UNSUPPORTED_VIDEO:
            target = entry.with_suffix(".mp3" if entry.suffix.lower() in UNSUPPORTED_AUDIO else ".mp4")
            issues.append(Issue("unsupported", entry, f"O Encore não lê {entry.suffix}; converter para "
                                f"{target.suffix}.", not target.exists()))

    tracks = lib.scan()
    groups: dict[str, list[Track]] = defaultdict(list)
    for t in tracks:
        groups[_dup_key(t)].append(t)
        if t.kind == "orphan":
            issues.append(Issue("orphan", t.files[0], "Áudio sem letra: o Encore não mostra esta faixa.",
                                " - " in t.base, t))
        if " - " not in t.base:
            issues.append(Issue("bad_name", t.files[0], "Nome sem 'Artista - Título'. Use Editar.", False, t))
        if t.kind == "midi":
            midi = t.file_with(MIDI_EXTS)
            if midi and not midi_has_lyrics(midi):
                issues.append(Issue("midi_no_lyrics", midi, "O Encore toca, mas sem letra na tela.", False, t))
        if t.kind == "multiplex_lrc" and not t.has_guide:
            issues.append(Issue("no_guide", t.files[0], "Sem guia MIDI: o Encore estima as notas ao vivo "
                                "(guia e pontuação piores). Gerar leva ~30 s.", True, t))
        for f in t.files:
            ext = f.suffix.lower()
            if ext == ".lrc":
                # CRLF and BOM are harmless: Encore trims each line and finds the stamp anywhere
                text = read_lrc(f).replace("\r\n", "\n")
                if normalize_lrc(text) != text:
                    issues.append(Issue("bad_lrc", f, "Letra em formato que o Encore lê errado.", True, t))
            elif ext == ".mp3" and not _has_tags(f) and " - " in t.base:
                issues.append(Issue("missing_tags", f, "mp3 sem artista/título nas tags.", True, t))

    for same in groups.values():
        if len(same) > 1:
            names = ", ".join(t.base for t in same)
            for t in same:
                issues.append(Issue("duplicate", t.files[0], f"Parecidas: {names}", False, t))

    if include_loudness:
        files = [f for t in tracks for f in t.files if f.suffix.lower() in AUDIO_EXTS | VIDEO_EXTS]
        for n, f in enumerate(files):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if on_progress:
                on_progress("medindo volume", n / max(1, len(files)))
            if loudness.is_marked(f) or not loudness.has_audio(f):
                continue
            l = loudness.measure(f)
            if loudness.needs_fix(l):
                issues.append(Issue("loudness", f, f"{l.i:.1f} LUFS (alvo {loudness.TARGET:g}).", True,
                                    extra={"lufs": l.i}))
    return issues


def fix(lib: Library, issue: Issue, search=None) -> str:
    """Applies the automatic fix; returns a short result message (raises on failure)."""
    p = issue.path
    if not issue.fixable:
        raise ValueError("Este problema não tem correção automática.")

    if issue.kind == "manifest_incomplete":
        data = read_manifest(lib.path)
        ensure_additional(data)
        write_manifest(lib.path, data)
        return "manifest completado"

    if issue.kind == "temp_leftover":
        shutil.rmtree(p)
        return "apagada"

    if issue.kind == "subfolder":
        target = lib.path / p.name
        if target.exists():
            raise FileExistsError(f"{p.name} já existe na raiz.")
        shutil.move(str(p), str(target))
        return "movido para a raiz"

    if issue.kind == "unsupported":
        is_audio = p.suffix.lower() in UNSUPPORTED_AUDIO
        target = p.with_suffix(".mp3" if is_audio else ".mp4")
        if target.exists():
            raise FileExistsError(f"{target.name} já existe.")
        (convert_audio if is_audio else convert_video)(p, target)
        send2trash(str(p))
        return f"convertido para {target.suffix}"

    if issue.kind == "bad_lrc":
        backup_file(p)
        p.write_text(normalize_lrc(read_lrc(p)), encoding="utf-8", newline="\n")
        return "letra normalizada"

    if issue.kind == "missing_tags":
        artist, title = _split_base(_strip_ext(p.name))
        write_tags(p, artist, title)
        return "tags gravadas"

    if issue.kind == "loudness":
        loudness.normalize_file(p)
        return "volume ajustado"

    if issue.kind == "no_guide":
        from encolibmg.guide.build import build_guide

        _, stats = build_guide(lib, issue.track)
        return f"guia gerado ({stats['aligned']} linhas alinhadas, {stats['fallback']} estimadas)"

    if issue.kind == "orphan":
        artist, title = _split_base(issue.track.base)
        cand = find_synced(artist, title, duration(p), search=search)
        if cand is None:
            raise LookupError("nenhuma letra sincronizada com a mesma duração")
        lrc = p.with_name(issue.track.base + ".lrc")
        lrc.write_text(normalize_lrc(cand.synced), encoding="utf-8", newline="\n")
        return f"letra encontrada ({cand.artist} - {cand.title})"

    raise ValueError(f"Correção desconhecida: {issue.kind}")
