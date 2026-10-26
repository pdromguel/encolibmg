# What Encore reads

How [Encore Karaoke](https://github.com/Encore-Karaoke-Labs/Encore-Karaoke) understands a library folder, read
from its source code. EncoLibMG is built around these rules.

Files of the same track share a **base name**: `Artist - Song`.

| File | What it enables | Where in Encore's code |
|---|---|---|
| `manifest.json` | Makes the folder a library: title, options, background videos, SoundFont, idle images, intro video | `main.ts` (`LibraryManifest`) |
| `Artist - Song.mp3/.m4a/.ogg/.wav` | An audio track. **Only shown if it has an `.lrc`, a `.cdg` or a MIDI guide** | `FsSvc.js` ~L719 |
| `….multiplexed.mp3` | Guide vocal on/off with ◀/▶ (left = instrumental, right = vocals; starts at -1) and live pitch analysis | `Playback.js` ~L1368, `State.js` |
| `….lrc` | Lyrics by line, Japanese/Korean romanization, OBS overlay. **The parser only accepts `[mm:ss.xx]` at the start of the line**: no `[offset:]`, no word timing, one timestamp per line | `LyricsEngine.js` `parseLrc` |
| `….cdg` | CD+G graphic lyrics | `FsSvc.js` |
| `….guide.kar` / `.guide.mid` / `.melody.*` | **Companion MIDI guide**: exact notes for the pitch guide and syllable-by-syllable lyrics; also works with videos | `FsSvc.js` ~L695, `PlaybackManager.js` ~L366 |
| `.mp4/.mkv/.webm/.avi` | A karaoke video (MTV), shown on its own | `FsSvc.js` |
| `.mid/.kar` on its own | MIDI karaoke played with the SoundFont, with furigana | `LyricsEngine.js` |
| `….chorus.ogg` | Backing vocals for MIDI tracks (`C` key) | `FsSvc.js` ~L690 |
| `songdb.json` | Encore's cache, including the **6-digit song codes** | `FsSvc.js` |

## Track levels, from basic to best

1. **MTV**: a karaoke video with the lyrics burned in.
2. **Audio + LRC**: Encore's own lyrics display, romanization.
3. **Multiplex + LRC**: adds the guide vocal on/off, an estimated pitch guide and scoring.
4. **Multiplex + LRC + MIDI guide**: adds word-by-word highlighting and a pitch guide with exact notes.
   This is what EncoLibMG builds by default.

## MIDI guide details EncoLibMG follows

- More than 5 lyric events, or Encore ignores the guide's lyrics.
- `@IVOCAL-CH=1` marks the vocal channel; channel volume (CC7) is 0, so the melody only plays when the singer
  asks for it (`M` → Guide); program 73 (flute).
- Furigana is written inside the event: `漢字[かんじ]`.
