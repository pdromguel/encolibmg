"""Write/read the companion guide (X.guide.mid) in the shape Encore's player expects.

- 480 PPQ at a fixed 120 BPM, so seconds map exactly to ticks (960/s).
- One track holds melody + lyrics: Encore takes metadata ({#TITLE=…}) and
  lyrics from the track with the most lyric events, and needs > 5 of them
  before it reads the guide notes at all.
- `@IVOCAL-CH=1` pins the melody channel; CC7 = 0 keeps the melody silent
  until the user raises "Guide" in Encore's mixer (M).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mido

from encolibmg.guide.align import Word
from encolibmg.guide.melody import Note
from encolibmg.guide.romanize import furigana, script_of

PPQ = 480
TEMPO = 500_000           # µs per beat = 120 BPM
TICKS_PER_SEC = PPQ * 2   # 960
PROGRAM = 73              # flute: clear when the user turns the guide up
VELOCITY = 100
MIN_LYRIC_EVENTS = 6


@dataclass
class GuideInfo:
    notes: list[Note]
    lyrics: list[tuple[float, str]]
    vocal_channel: int | None
    channel_volume: int | None


def _tick(sec: float) -> int:
    return max(0, round(sec * TICKS_PER_SEC))


def _lyric_text(word: str, line_start: bool, first_line: bool) -> str:
    spaced = script_of(word) != "ja"  # Japanese has no spaces, and the furigana form must end in ']'
    text = furigana(word) if not spaced else word
    if line_start and not first_line:
        text = "/" + text
    return text + (" " if spaced else "")


def write_guide(path: Path, notes: list[Note], lines: list[list[Word]], title: str, artist: str) -> Path:
    n_words = sum(len(l) for l in lines)
    if n_words < MIN_LYRIC_EVENTS:
        raise ValueError(f"A letra tem só {n_words} palavras; o Encore precisa de pelo menos "
                         f"{MIN_LYRIC_EVENTS} para usar o guia.")

    events: list[tuple[int, int, mido.Message | mido.MetaMessage]] = []  # (tick, order, msg)
    for n in notes:
        events.append((_tick(n.start), 2, mido.Message("note_on", channel=0, note=n.pitch, velocity=VELOCITY)))
        events.append((max(_tick(n.end), _tick(n.start) + 1), 0,
                       mido.Message("note_off", channel=0, note=n.pitch, velocity=0)))
    first_line = True
    for line in lines:
        for k, w in enumerate(line):
            events.append((_tick(w.start), 1, mido.MetaMessage("lyrics", text=_lyric_text(w.text, k == 0, first_line))))
        if line:
            first_line = False
    events.sort(key=lambda e: (e[0], e[1]))

    mid = mido.MidiFile(type=1, ticks_per_beat=PPQ, charset="utf-8")
    conductor = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=TEMPO),
                                mido.MetaMessage("time_signature", numerator=4, denominator=4),
                                mido.MetaMessage("end_of_track")])
    head = [
        mido.MetaMessage("track_name", name="Guide"),
        mido.MetaMessage("text", text="@IVOCAL-CH=1"),
        mido.MetaMessage("lyrics", text=f"{{#TITLE={title}}}"),
        mido.MetaMessage("lyrics", text=f"{{#ARTIST={artist}}}"),
        mido.Message("program_change", channel=0, program=PROGRAM),
        mido.Message("control_change", channel=0, control=7, value=0),
        mido.Message("control_change", channel=0, control=11, value=127),
    ]
    guide = mido.MidiTrack(head)
    last = 0
    for tick, _, msg in events:
        guide.append(msg.copy(time=tick - last))
        last = tick
    guide.append(mido.MetaMessage("end_of_track"))
    mid.tracks += [conductor, guide]
    mid.save(str(path))
    return Path(path)


def read_guide(path: Path) -> GuideInfo:
    mid = mido.MidiFile(str(path), charset="utf-8")
    notes, lyrics, vocal_ch, volume = [], [], None, None
    for track in mid.tracks:
        tick, open_notes = 0, {}
        for msg in track:
            tick += msg.time
            sec = tick / TICKS_PER_SEC
            if msg.type == "lyrics" and not msg.text.startswith("{#"):
                lyrics.append((round(sec, 3), msg.text))
            elif msg.type == "text" and msg.text.upper().startswith("@IVOCAL-CH="):
                vocal_ch = int(msg.text.split("=", 1)[1])
            elif msg.type == "control_change" and msg.control == 7:
                volume = msg.value
            elif msg.type == "note_on" and msg.velocity > 0:
                open_notes[msg.note] = sec
            elif msg.type in ("note_off", "note_on") and msg.note in open_notes:
                notes.append(Note(round(open_notes.pop(msg.note), 3), round(sec, 3), msg.note))
    return GuideInfo(sorted(notes, key=lambda n: n.start), lyrics, vocal_ch, volume)
