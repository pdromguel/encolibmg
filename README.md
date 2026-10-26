<p align="center"><img src="encolibmg/webui/static/brand/wordmark.svg" alt="EncoLibMG" width="440"></p>

<p align="center"><b>Your karaoke library, in tune.</b><br>
Type a song name. Get a complete karaoke track for
<a href="https://github.com/Encore-Karaoke-Labs/Encore-Karaoke">Encore Karaoke</a>: synced lyrics, a guide vocal you can
switch on and off, and a MIDI pitch guide with word-by-word lyrics.</p>

<p align="center">
  <a href="https://github.com/pdromguel/encolibmg/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/pdromguel/encolibmg/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/pdromguel/encolibmg/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/pdromguel/encolibmg?color=798186"></a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows-10%20%7C%2011-4e5457">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-4e5457">
  <a href="LICENSE"><img alt="License: GPL-3.0" src="https://img.shields.io/badge/license-GPL--3.0-4e5457"></a>
</p>

<p align="center"><b>English</b> · <a href="docs/README.pt-BR.md">Português (Brasil)</a></p>

<p align="center"><img src="docs/screens/demo.gif" alt="EncoLibMG: home, adding a song, library, sync and guide preview" width="900"></p>

## What every song gets

| File | What it does in Encore |
|---|---|
| `Artist - Song.multiplexed.mp3` | Instrumental on the left, vocals on the right: **◀/▶ turns the guide vocal on and off**. Vocals split with Demucs on your GPU. |
| `Artist - Song.lrc` | **Synced lyrics** in the exact format Encore reads, matched to the audio by length. Japanese and Korean are romanized. |
| `Artist - Song.guide.mid` | **MIDI guide**: the real melody notes (CREPE) and word-by-word lyrics (MMS), so the pitch guide, scoring and highlighting are accurate. |
| `Artist - Song.mp4` *(optional)* | The music video playing muted behind the lyrics, without losing the guide vocal. |

No synced lyrics anywhere? It grabs a **karaoke video** instead. Every track ends up at the same loudness.

## Screens

<table>
  <tr>
    <td width="50%"><img src="docs/screens/en/add.png" alt="Add"><br><b>Add</b>: pick the lyrics, the rest is automatic.</td>
    <td width="50%"><img src="docs/screens/en/library.png" alt="Library"><br><b>Library</b>: filters, multi-select and a panel per track.</td>
  </tr>
  <tr>
    <td><img src="docs/screens/en/sync.png" alt="Sync"><br><b>Sync</b>: fix lyric timing on the vocal waveform.</td>
    <td><img src="docs/screens/en/guide.png" alt="Guide preview"><br><b>Guide preview</b>: the notes and word-by-word lyrics Encore will use.</td>
  </tr>
  <tr>
    <td><img src="docs/screens/en/check.png" alt="Check"><br><b>Check</b>: finds what Encore would ignore and fixes it in one click.</td>
    <td><img src="docs/screens/en/home.png" alt="Home"><br><b>And more</b>: import CDs, CDG packs and .kar files; background videos, intro, score narrations, SoundFont.</td>
  </tr>
</table>

<sub>Screenshots use a demo library of invented songs, built by <a href="scripts/screenshots/demo_library.py">scripts/screenshots/demo_library.py</a>.</sub>

## Quick start

1. Install **Python 3.12** and **ffmpeg** (`winget install Gyan.FFmpeg`). Windows 10/11 already has WebView2.
2. Download the [latest release](https://github.com/pdromguel/encolibmg/releases/latest) (or clone the repo) and
   double-click **`install.bat`**. It's ~3 GB because of PyTorch and the AI models; with an NVIDIA card,
   everything runs on the GPU.
3. Double-click **`EncoLibMG.bat`**, open or create a library, and search for a song.

Then point Encore's Setup (F2) at the library folder. The app speaks English and Brazilian Portuguese
(it follows Windows; switch any time with **EN/PT**).

## Learn more

- [User guide](docs/user-guide.md): every screen, shortcuts, tips.
- [What Encore reads](docs/encore-format.md): the file formats this app is built around.
- [Roadmap](docs/roadmap.md): download queue, more lyrics sources, guide editor, installer.
- [Architecture](docs/architecture.md) and [contributing](.github/CONTRIBUTING.md): for developers.
- [Changelog](CHANGELOG.md).

## License

Free software under the [GPL-3.0](LICENSE). Third-party licenses are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Note: the MMS alignment model (Meta), downloaded the first time a
guide is built, is **CC BY-NC 4.0**, for non-commercial use only.

**Disclaimer.** EncoLibMG organizes **your own personal karaoke library**. It does not host or distribute any
music, lyrics or videos. Downloading copyrighted content may not be allowed where you live or by the terms of the
sites involved: you are responsible for what you download and how you use it. EncoLibMG is not affiliated with
Encore Karaoke, LRCLIB or YouTube.
