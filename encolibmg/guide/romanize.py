"""Split a lyric line into display words + a plain a–z spelling for the MMS aligner.

MMS_FA only knows romanized lowercase letters and the apostrophe, so:
latin → strip accents; Japanese → MeCab (fugashi/UniDic) tokens and readings, romaji via
pykakasi; Korean → Revised Romanization from Hangul jamo.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_KANA = re.compile(r"[぀-ヿ]")
_KANJI = re.compile(r"[一-鿿]")
_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def script_of(text: str) -> str:
    if _KANA.search(text):
        return "ja"
    if _HANGUL.search(text):
        return "ko"
    if _KANJI.search(text):
        return "ja"  # kanji without kana: still read with Japanese readings
    if _LATIN.search(text):
        return "latin"
    return "other"


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("’", "'").replace("ß", "ss").replace("æ", "ae").replace("ø", "o")
    return re.sub(r"[^a-z']", "", s).strip("'")


@lru_cache(maxsize=1)
def _kakasi():
    import pykakasi

    return pykakasi.kakasi()


@lru_cache(maxsize=1)
def _tagger():
    # MeCab + UniDic reads kanji in context (君の名は → きみ の な は); pykakasi alone guesses (くん の めい)
    import fugashi

    return fugashi.Tagger()


def _to_hira(kata: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kata)


def _ja_tokens(text: str) -> list[tuple[str, str, str]]:
    """[(surface, reading in hiragana, pronunciation in kana)] — falls back to pykakasi for unknown words."""
    out = []
    for w in _tagger()(text):
        kana = getattr(w.feature, "kana", None)
        pron = getattr(w.feature, "pron", None) or kana
        if not kana or kana == "*":
            kana = pron = "".join(c["hira"] for c in _kakasi().convert(w.surface))
        out.append((w.surface, _to_hira(kana), pron))
    return out


def _romaji(kana: str) -> str:
    return "".join(c["hepburn"] for c in _kakasi().convert(kana))


# --- Korean: Revised Romanization (simplified, syllable by syllable) ---
_CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
         "yu", "eu", "ui", "i"]
_JONG = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t",
         "ng", "t", "t", "k", "t", "p", "t"]


def _korean(word: str) -> str:
    out = []
    syl = [ord(c) - 0xAC00 for c in word if 0xAC00 <= ord(c) <= 0xD7A3]
    for k, s in enumerate(syl):
        cho, jung, jong = s // 588, (s % 588) // 28, s % 28
        nxt_cho = syl[k + 1] // 588 if k + 1 < len(syl) else None
        if jong and nxt_cho == 11:  # final consonant moves to the next silent initial (사랑해 → sa-rang-hae)
            final = {8: "r", 1: "g", 4: "n", 7: "d", 16: "m", 17: "b", 19: "s", 22: "j"}.get(jong, _JONG[jong])
        else:
            final = _JONG[jong]
        out.append(_CHO[cho] + _JUNG[jung] + final)
    return "".join(out)


def words_for_alignment(line: str) -> list[tuple[str, str]]:
    """[(display text, romanized text)] — romanized may be '' (not alignable)."""
    script = script_of(line)
    if script == "ja":
        return [(surface, _plain(_romaji(pron)))
                for surface, _, pron in _ja_tokens(line) if surface.strip()]
    words = line.split()
    if script == "ko":
        return [(w, _plain(_korean(w)) or _plain(w)) for w in words]
    return [(w, _plain(w)) for w in words]


def furigana(display: str) -> str:
    """'漢字' → '漢字[かんじ]' (Encore draws the reading above); anything else unchanged."""
    if not _KANJI.search(display):
        return display
    hira = "".join(h for _, h, _ in _ja_tokens(display))
    return f"{display}[{hira}]" if hira and hira != display else display
