# Third-party notices

EncoLibMG is licensed under the GNU General Public License v3.0 (see [LICENSE](LICENSE)).
It bundles, depends on or downloads the components below. Each keeps its own license.

## Bundled in this repository

| Component | Where | License |
|---|---|---|
| [lit-html](https://github.com/lit/lit) 3.3.3 | `encolibmg/webui/static/vendor/` | BSD-3-Clause ([text](encolibmg/webui/static/vendor/lit-html.LICENSE)) |
| [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) (variable, latin + latin-ext) | `encolibmg/webui/static/fonts/` | SIL Open Font License 1.1 ([text](encolibmg/webui/static/fonts/OFL.txt)) |

## Python dependencies (installed by `instalar.bat`, not bundled)

| Package | License |
|---|---|
| PyTorch, torchaudio | BSD-3-Clause |
| Demucs | MIT |
| torchcrepe | MIT |
| yt-dlp | Unlicense |
| mutagen | GPL-2.0-or-later |
| pykakasi | GPL-3.0-or-later |
| fugashi | MIT |
| unidic-lite (UniDic dictionary) | MIT (package); UniDic itself is BSD-3-Clause / LGPL / GPL |
| pywebview | BSD-3-Clause |
| mido | MIT |
| Send2Trash | BSD-3-Clause |
| sounddevice | MIT |
| soundfile | BSD-3-Clause |
| requests | Apache-2.0 |
| Pillow | MIT-CMU (HPND) |
| NumPy | BSD-3-Clause |

## Models downloaded at runtime (not bundled)

| Model | Used for | License |
|---|---|---|
| Demucs `htdemucs_ft` weights | Vocal / instrumental separation | MIT |
| CREPE (`torchcrepe` full) weights | Melody (pitch) detection for the MIDI guide | MIT |
| **MMS forced aligner** (Meta, via `torchaudio.pipelines.MMS_FA`) | Word timing for the MIDI guide | **CC BY-NC 4.0 (non-commercial use only)** |

The MMS aligner is downloaded by torchaudio the first time a MIDI guide is generated. Its non-commercial license
applies to that model; if you need commercial use, generate guides without word alignment or replace the aligner.

## Content downloaded on request (not bundled)

| Content | License |
|---|---|
| [GeneralUser GS](https://github.com/mrbumpy409/GeneralUser-GS) SoundFont | GeneralUser GS License v2.0. Its license text is saved next to the SoundFont. |
| Lyrics from [LRCLIB](https://lrclib.net) and audio/video from YouTube | Rights belong to their owners. EncoLibMG is meant for personal use; you are responsible for what you download. |

## External formats

EncoLibMG writes files in the formats read by [Encore Karaoke](https://github.com/Encore-Karaoke-Labs/Encore-Karaoke)
(MIT). No Encore code is included; the formats were studied from its public source.
