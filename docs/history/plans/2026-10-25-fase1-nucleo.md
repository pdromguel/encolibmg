# Fase 1 — Núcleo: plano de implementação

> Execução: nativa (nesta sessão), TDD por tarefa, revisão do conjunto no fim.

**Goal:** App Tkinter que adiciona músicas à `EncoreLibrary` como Multiplex + LRC, com fallback MTV.
**Architecture:** Pacote `encolibmg/` com módulos puros e testáveis (library, lyrics, youtube, audio, tags) orquestrados por `pipeline.py`; a GUI só chama o pipeline numa thread e recebe eventos por fila.
**Tech Stack:** Python 3.12, Tkinter/ttk, yt-dlp, Demucs (torch 2.8 cu128), ffmpeg, mutagen, requests, send2trash, pytest.
**Spec:** [docs/specs/2026-10-25-fase1-nucleo-design.md](../specs/2026-10-25-fase1-nucleo-design.md)

## Global Constraints
- Arquivos sempre na raiz da biblioteca; nome-base `Artista - Música`; sem `<>:"/\|?*`; sem ponto/espaço final; ≤150 chars.
- Multiplex: esquerda = instrumental, direita = voz; `libmp3lame` 320k; arquivo `X.multiplexed.mp3` + `X.lrc`.
- LRC de saída: `[mm:ss.xx] texto`, UTF-8 sem BOM, `\n`, uma marcação por linha, ordenado.
- `manifest.json` existente nunca é sobrescrito.
- Nada é escrito na biblioteca até todos os passos terminarem (pasta temporária + mover no fim).
- Config/log em `%APPDATA%\EncoLibMG\`.

## Review Focus
1. Nomes com acentos/CJK (`宇多田ヒカル - First Love`) → preservados, NFC; teste em Task 2.
2. LRC com BOM, `\r\n` ou linhas `[00:00.00]` vazias → normalizado sem perder linhas; teste em Task 3.
3. Música já existente na biblioteca → erro antes de baixar qualquer coisa; teste em Task 7.
4. Nenhum vídeo com duração dentro de 8 s → `pick_audio` devolve `None` e o pipeline lança `NoAudioMatch`; testes em Task 4 e 7.
5. Cancelar no meio → pasta temporária removida, biblioteca intacta; teste em Task 7.

---

### Task 1: Esqueleto + ambiente
**Files:** `requirements.txt`, `instalar.bat`, `Abrir EncoLibMG.bat`, `encolibmg/__init__.py`, `encolibmg/__main__.py`, `encolibmg/paths.py`, `tests/conftest.py`
- `paths.py`: `app_dir() -> Path` (`%APPDATA%\EncoLibMG`, criada se não existir), `load_config() -> dict`, `save_config(dict)`, `setup_logging()`.
- [ ] Criar `.venv` com `py -3.12`; instalar `torch==2.8.* torchaudio==2.8.*` (cu128) + requirements.
- [ ] Verificar: `python -c "import torch;print(torch.cuda.is_available())"` → `True`; `python -m demucs --help` sai 0.

### Task 2: `library.py`
**Produces:** `base_name(artist:str, title:str)->str`, `Track` (dataclass: `base, artist, title, files: list[Path], kind: str`), `Library.create(path:Path, title:str)->Library`, `Library.open(path:Path)->Library`, `Library.scan()->list[Track]`, `Library.exists(base:str)->bool`, `Library.remove(track:Track)->None`, `LibraryError`.
- [ ] Testes: `test_base_name_strips_invalid` (`'AC/DC', 'T.N.T.'` → `'AC-DC - T.N.T'`), `test_base_name_keeps_unicode`, `test_base_name_max_len` (≤150), `test_create_writes_manifest`, `test_create_keeps_existing_manifest`, `test_open_requires_manifest`, `test_scan_kinds` (multiplex_lrc, audio_lrc, mtv, midi, orphan com arquivos vazios), `test_exists_case_insensitive`.
- [ ] Implementar; `scan` agrupa por nome-base sem extensão e sem `.multiplexed`, comparação case-insensitive NFC; artista/título vêm de dividir no primeiro `" - "`.
- [ ] `pytest tests/test_library.py` verde.

### Task 3: `lyrics/normalize.py` + `lyrics/lrclib.py`
**Produces:** `normalize_lrc(text:str, offset_ms:int=0)->str`, `LyricsCandidate` (dataclass: `id:int, artist, title, album:str, duration:float, synced:str|None, plain:str|None`), `lrclib.search(query:str, session=None)->list[LyricsCandidate]`.
- [ ] Testes de normalize: formatos `[01:02]`, `[01:02.3]`, `[01:02.34]`, `[01:02.345]` → `[01:02.00]`, `[01:02.30]`, `[01:02.34]`, `[01:02.34]`; multi-marcação `[00:10.00][00:20.00]oi` → duas linhas; `[offset:500]` subtrai 500 ms; `<00:10.50>` removido; tags `[ar:..]` removidas; BOM e `\r\n`; tempo negativo vira `00:00.00`.
- [ ] Teste de lrclib com session falsa devolvendo JSON gravado: sincronizadas primeiro; mapeia `trackName/artistName/albumName/duration/syncedLyrics/plainLyrics`; envia `User-Agent`.
- [ ] Implementar; `pytest tests/test_lyrics.py` verde.

### Task 4: `youtube.py`
**Produces:** `VideoCandidate` (dataclass: `id, title, channel:str, duration:float|None, url:str`), `search(query:str, n:int=10)->list[VideoCandidate]`, `pick_audio(cands, target:float, query:str="")->VideoCandidate|None`, `download_audio(url:str, dest_dir:Path, cancel:Event|None=None)->Path`, `download_video(url:str, dest_dir:Path, cancel=None)->Path`.
- [ ] Testes de `pick_audio`: escolhe menor diferença; ignora >8 s; ignora título com `karaoke`/`live` etc.; aceita `live` se a query contém `live`; sem duração → ignorado; nada compatível → `None`.
- [ ] Teste de `search` com `YoutubeDL` mockado (`extract_info` devolvendo entries).
- [ ] Implementar (yt-dlp API Python; `progress_hooks` checam `cancel` e levantam `Cancelled`).

### Task 5: `audio/multiplex.py` + `audio/separate.py` + `tags.py`
**Produces:** `make_multiplex(instrumental:Path, vocals:Path, dest:Path)->Path`, `separate(wav:Path, work_dir:Path, cancel=None, on_progress=None)->tuple[Path,Path]`, `write_tags(mp3:Path, artist:str, title:str)`, `Cancelled` (em `encolibmg/errors.py`, junto com `NoAudioMatch`, `AlreadyExists`).
- [ ] Teste `test_multiplex_channels`: gera seno 440 Hz (instrumental) e 880 Hz (voz) com ffmpeg, mixa, decodifica o mp3 e confere frequência dominante: L≈440, R≈880 (FFT com numpy — numpy já vem com torch).
- [ ] Teste `test_write_tags_roundtrip` com mp3 sintético.
- [ ] `separate`: `sys.executable -m demucs --two-stems=vocals -n htdemucs -o work_dir [-d cpu se sem CUDA]`; progresso pela % do tqdm no stderr; devolve `work/htdemucs/<stem>/no_vocals.wav`, `vocals.wav`. Teste marcado `slow` com 5 s de áudio sintético.

### Task 6: `pipeline.py`
**Consumes:** tudo acima. **Produces:** `add_song(lib:Library, lyr:LyricsCandidate, on_progress, cancel:Event)->Track`, `add_mtv(lib, artist, title, video:VideoCandidate, on_progress, cancel)->Track`, `find_mtv(artist, title)->list[VideoCandidate]`.
- [ ] Testes com dependências mockadas (monkeypatch em `youtube`, `separate`, `make_multiplex`): `test_add_song_writes_pair` (cria `X.multiplexed.mp3` e `X.lrc` normalizado), `test_add_song_existing_raises` (nenhum download chamado), `test_add_song_no_match_raises`, `test_cancel_cleans_temp` (biblioteca sem arquivos novos, temp apagado), `test_add_mtv_writes_mp4`.
- [ ] Implementar com `tempfile.TemporaryDirectory(dir=lib.path.parent)` → mover com `shutil.move` no fim.

### Task 8: GUI
**Files:** `encolibmg/gui/app.py`, `gui/add_tab.py`, `gui/library_tab.py`, `gui/worker.py`.
- `worker.py`: `Worker(root)` roda função em thread, eventos `("progress", step, frac) | ("done", result) | ("error", exc)` numa `queue.Queue` lida com `root.after(100, …)`.
- [ ] Aba Adicionar e aba Biblioteca conforme a spec; seleção/criação de biblioteca na barra superior com `filedialog`.
- [ ] Teste de fumaça: `test_app_builds` cria `App` com Tk, chama `update()` e destrói (pula se não houver display).

### Task 9: Ponta a ponta
- [ ] Rodar `pytest` completo.
- [ ] Criar biblioteca de teste, adicionar 1 música real pela GUI, conferir arquivos, canais e `.lrc`.
- [ ] Revisão final do código.
