# Changelog

All notable changes to EncoLibMG. Versions follow [Semantic Versioning](https://semver.org/).

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
