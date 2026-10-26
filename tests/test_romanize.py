from encolibmg.guide.romanize import furigana, script_of, words_for_alignment


def test_script_detection():
    assert script_of("Águas de Março") == "latin"
    assert script_of("君の名は") == "ja"
    assert script_of("サクラ") == "ja"
    assert script_of("사랑해") == "ko"
    assert script_of("♪ ♪") == "other"


def test_latin_words_keep_display_and_strip_accents():
    assert words_for_alignment("São as Águas de Março!") == [
        ("São", "sao"), ("as", "as"), ("Águas", "aguas"), ("de", "de"), ("Março!", "marco")]


def test_apostrophes_and_symbols():
    assert words_for_alignment("I'm (oh) ♪") == [("I'm", "i'm"), ("(oh)", "oh"), ("♪", "")]


def test_japanese_chunks_with_romaji():
    out = words_for_alignment("君の名は")
    assert "".join(d for d, _ in out) == "君の名は"
    assert all(r and r.isascii() for _, r in out)
    assert "".join(r for _, r in out).replace("'", "") in ("kiminonaha", "kiminonawa")


def test_korean_romanization():
    assert words_for_alignment("사랑해 너를") == [("사랑해", "saranghae"), ("너를", "neoreul")]


def test_furigana():
    assert furigana("漢字") == "漢字[かんじ]"
    assert furigana("さくら") == "さくら"
    assert furigana("hello") == "hello"


def test_japanese_uses_context_readings():
    assert words_for_alignment("君の名は") == [("君", "kimi"), ("の", "no"), ("名", "na"), ("は", "wa")]
    assert furigana("君") == "君[きみ]"
    assert furigana("咲く") == "咲く[さく]"
