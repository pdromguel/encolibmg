# Changelog

All notable changes to EncoLibMG. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Download queue**: tick several search results or add a whole list (pasted text, a public YouTube playlist, a
  Spotify playlist exported with Exportify, or any artist/title CSV). Lyrics are picked automatically only when
  artist, title (and length) really match. The next song downloads while the GPU works on the current one; the queue
  is saved between sessions (reopening starts it paused); failed songs say why and offer MTV or Try again; a summary
  at the end. The footer's Cancel pauses the queue.
- **Hardware** section in the README: measured times per song with and without an NVIDIA card, minimum and
  recommended PC, what to expect. `scripts/benchmark.py` measures your own PC.

### Fixed
- NVIDIA cards older than the GTX 10 series (unsupported by PyTorch) made the AI steps fail; the app now detects
  them and uses the processor.

### Changed
- **Renamed launchers:** `instalar.bat` → `install.bat`, `Abrir EncoLibMG.bat` → `EncoLibMG.bat`.
- New front page with an animated demo and screenshots of every screen (from a demo library of invented songs);
  a [user guide](docs/user-guide.md), [architecture](docs/architecture.md), [Encore file format](docs/encore-format.md)
  and an English [roadmap](docs/roadmap.md). The original Portuguese work notes moved to `docs/history/`.
- Code reorganized: `encolibmg/core/` (paths, errors, files, translations) and `encolibmg/library/` (everything
  that reads or writes the library folder); scripts grouped in `scripts/i18n/`, `scripts/brand/` and
  `scripts/screenshots/`; one shared ffmpeg runner; unused code and vendored files removed.

## [0.9.0] — 2026-10-25

First public release.

### Added
- **Add a song from a search:** synced lyrics from LRCLIB, audio from YouTube matched by length, vocals split
  with Demucs (`htdemucs_ft`), saved as an Encore **Multiplex** (instrumental left, vocals right) + `.lrc`.
- **MIDI guide** (`.guide.mid`): melody notes detected with CREPE and word-by-word lyrics aligned with MMS,
  so Encore's pitch guide, scoring and lyric highlighting are accurate. Japanese and Korean are romanized.
- **Karaoke videos (MTV)** when there are no synced lyrics, and official **music videos** behind Multiplex tracks.
- **Library:** filters, multi-select, per-track panel (listen to instrumental/vocals/both, rename, convert to
  Multiplex, build guides, add a video, remove to the Recycle Bin).
- **Sync:** pixel waveform of the vocals, shift and anchor lyric lines, suggest the vocal start, backup + undo.
- **Guide preview:** piano roll of the guide notes with the lyrics filling word by word.
- **Check:** finds what Encore would ignore or show wrong (audio without lyrics, no guide, non-standard
  lyrics, unsupported formats, subfolders, incomplete manifest, missing tags, volume) and fixes it.
- **Import:** CDs/FLAC, CDG collections, `.zip`, `.kar`/`.mid` karaoke, with an editable preview.
- **Look & sound:** background videos by category, idle images, intro video, score narrations, SoundFont.
- **English and Brazilian Portuguese**, following Windows, switchable live.
- Pixel-art interface (pywebview + lit-html) and the "Sung line" brand.
- Tests: fast suite, `-m slow` (real models), `-m ui` (real window); CI on GitHub Actions.

[0.9.0]: https://github.com/pdromguel/encolibmg/releases/tag/v0.9.0
