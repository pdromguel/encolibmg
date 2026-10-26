# Roadmap

## Done — 0.9 (first public release)
Add songs from a search (synced lyrics, vocal split, Multiplex, MIDI guide), karaoke videos and music videos,
Library, Sync, Guide preview, Check, Import, Look & sound, English and Brazilian Portuguese, tests and CI.
See the [changelog](../CHANGELOG.md).

## Done — 1.0
- **Installer**: one Setup.exe that brings its own Python, ffmpeg and the right PyTorch; built by CI for every release.
- **Download queue**: many songs at once (tick several results, paste a list, a YouTube playlist, a Spotify CSV),
  saved between sessions, the next download overlapping the GPU work, a summary at the end.
- **Staying current**: a notice when a new version is out; the YouTube downloader updates from inside the app.

## Next

| | What | Why |
|---|---|---|
| **More lyrics** | More synced-lyrics sources (each result shows where it came from); plain lyrics timed automatically against the vocals; transcription as a last resort, marked "review". | Many songs, Brazilian music especially, end up as karaoke videos only. |
| **Robustness** | Download the AI models up front with a progress bar; duration column; drag and drop to import; remember the window; accessibility pass; a songbook (PDF/HTML) with Encore's 6-digit codes. | Fewer surprises, easier daily use. |
| **Guide editor** | Fix notes and word timing in the Guide preview (move, resize, delete, draw; undo/redo), saved with a backup. | Automatic guides are good, not perfect. |

Ideas and requests are welcome in the [issues](https://github.com/pdromguel/encolibmg/issues).
