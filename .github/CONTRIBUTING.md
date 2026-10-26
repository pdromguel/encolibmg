# Contributing

Thanks for helping! Bug reports, translations and pull requests are welcome, in English or Portuguese.

## Reporting a bug
Open an issue with the **Bug** template. Please attach the relevant part of the log:
`%APPDATA%\EncoLibMG\log.txt`. Remove anything private from it first (folder names can contain your user name).

## Setting up
Start with [docs/architecture.md](../docs/architecture.md): how the code is laid out and the rules it follows.

```
install.bat                               # creates .venv with Python 3.12, PyTorch and the requirements
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m encolibmg --debug # the window with developer tools
```
Requires Windows 10/11 (WebView2), Python 3.12 and ffmpeg on `PATH`.

## Before opening a pull request
```
.venv\Scripts\python -m pyflakes encolibmg tests scripts
.venv\Scripts\python -m pytest            # fast tests, Python + JS (CI runs these)
.venv\Scripts\python -m pytest -m ui      # opens the real window; run it when you touch the interface
.venv\Scripts\python -m pytest -m slow    # real Demucs/CREPE/network; run it when you touch the engine
```
- Keep pull requests focused, with a test for the behavior you change.
- **Texts:** never hard-code a sentence. Add it to `scripts/i18n/strings_engine.py` (engine) or
  `scripts/i18n/strings_ui.py` (interface) as `(key, pt-BR, en)` and run `python scripts/i18n/build.py`.
  The tests fail on missing, unused or mismatched keys.
- **No copyrighted content** in the repository: no songs, videos, lyrics or screenshots that show lyrics.
  Tests generate their own audio and use placeholder words.
- Match the surrounding code: small modules, comments that explain *why*.

## License
By contributing you agree that your contribution is licensed under the [GPL-3.0](../LICENSE).
