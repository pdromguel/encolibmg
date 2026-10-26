# Fase 2 — Qualidade e organização: plano de implementação

> Execução: nativa (nesta sessão), TDD por tarefa, revisão do conjunto no fim.

**Goal:** Sincronia, volume uniforme, verificador, importador, edição, clipe+Multiplex, manifest e conversão para Multiplex.
**Architecture:** Módulos puros novos (`lyrics/sync`, `audio/loudness`, `audio/convert`, `manifest`, `checker`, `importer`) testados sem GUI; o `pipeline` ganha operações sobre arquivos locais; a GUI só orquestra pelo `Worker`.
**Tech Stack:** o da Fase 1 + `sounddevice`.
**Spec:** [docs/specs/2026-10-25-fase2-qualidade-design.md](../specs/2026-10-25-fase2-qualidade-design.md)

## Global Constraints
- Loudness alvo −16 LUFS, pico ≤ −1 dBTP, tolerância 1,5 LU, marca `TXXX:EncoreLM-Loudness`.
- Nada é apagado de verdade: Lixeira (`send2trash`); `.lrc` alterado tem backup em `%APPDATA%\EncoLibMG\backups\`.
- Nunca sobrescrever arquivo existente na biblioteca.
- Formatos aceitos pelo Encore: áudio `mp3 m4a ogg wav`, vídeo `mp4 mkv webm avi`.
- Âncora de sincronia: tempo atual − 150 ms.

## Review Focus
1. Letra com uma única linha ou vazia no ajuste por âncoras → sem divisão por zero; teste na Task 1.
2. Faixa já normalizada → não recodifica de novo (marca nas tags); teste na Task 2.
3. Importar a mesma pasta duas vezes → segunda vez tudo "já existe", nada duplicado; teste na Task 5.
4. Renomear para um nome que só muda maiúsculas (`queen` → `Queen`) no Windows (case-insensitive) → funciona; teste na Task 3.
5. Zip com caminhos estranhos (`../x.mp3`) → ignorado, nunca extrai fora da pasta temporária; teste na Task 5.

---

### Task 1: `lyrics/sync.py`
**Produces:** `Line(ms:int, text:str)`, `parse_lrc(text)->list[Line]` (via `normalize_lrc`), `format_lrc(lines)->str`, `shift(lines, ms)->list[Line]`, `apply_anchors(lines, anchors: dict[int,int])->list[Line]`, `vocal_onset(samples: np.ndarray, sr:int)->float|None`.
- Testes: ida-e-volta parse/format; shift não fica negativo; 1 âncora = shift; 2 âncoras = reta exata (incluindo extrapolação antes/depois); 3 âncoras = linear por partes; âncoras em linhas iguais de tempo não dividem por zero; letra vazia → []; onset de 3 s de silêncio + tom ≈ 3,0 s (±0,06); só silêncio → None.

### Task 2: `audio/loudness.py` + ganho no multiplex
**Produces:** `Loudness(i:float, tp:float)`, `measure(path)->Loudness`, `gain_for(l:Loudness, target=-16.0, max_tp=-1.0)->float`, `needs_fix(l, target, tol=1.5)->bool`, `normalize_file(path)->bool` (mp3 ou vídeo; False se já marcado/dentro da tolerância), `is_marked(path)->bool`; `make_multiplex(..., normalize=True)`.
- Testes: tom −30 dBFS medido e ganho calculado ≈ alvo; ganho limitado pelo pico; `make_multiplex` com normalize sai a −16 ±1 LUFS e marcado; `normalize_file` em mp3 já marcado → False sem tocar no arquivo (mtime igual).

### Task 3: `manifest.py` + `library` (rename, clipe)
**Produces:** `read_manifest(lib_path)->dict`, `write_manifest(lib_path, data)`, `FLAGS: list[tuple[key,label]]`; `Track.has_video`, `kind_label(track)->str` (inclui "Multiplex + LRC + clipe"); `Library.rename_track(track, artist, title)->Track` (renomeia irmãos, regrava tags mp3, permite mudar só maiúsculas, `AlreadyExists` em colisão).
- Testes: preserva chaves desconhecidas; rename de 3 arquivos + tags; rename só de maiúsculas; colisão.

### Task 4: `audio/convert.py` + `checker.py`
**Produces:** `convert_audio(src, dest_mp3)`, `convert_video(src, dest_mp4)`; `Issue(kind, path:Path, message, fixable:bool, track:Track|None)`, `check(lib, include_loudness=False, cancel=None, on_progress=None)->list[Issue]`, `fix(lib, issue)->str`.
- Kinds: `orphan`, `bad_lrc`, `unsupported`, `subfolder`, `temp_leftover`, `missing_tags`, `loudness`, `bad_name`, `duplicate`.
- Testes: um arquivo sintético por kind → detectado; fixes de `bad_lrc` (com backup), `unsupported` (flac→mp3), `subfolder`, `temp_leftover`, `missing_tags`; `orphan` com LRCLIB falso.

### Task 5: `importer.py`
**Produces:** `ImportItem(sources: list[Path], artist, title, kind, status, selected=True)`, `clean_title(s)->str`, `infer_name(path)->(artist,title)`, `scan_source(folder, tmp_dir)->list[ImportItem]` (zips extraídos com proteção de caminho), `import_item(lib, item, *, move, find_lyrics, make_multiplex, normalize, cancel, on_progress)->str`.
- Testes: `clean_title` (`01 - X`, `X (Official Audio)`, `[Karaoke]`); inferência por tags/nome/pasta; pareamento mp3+CDG com maiúsculas diferentes; zip + zip-slip; import copia, não sobrescreve, segunda importação = "já existe"; áudio sem letra → "sem letra".

### Task 6: `pipeline` local + clipe
**Produces:** `track_from_local(lib, audio:Path, artist, title, lrc_text, on_progress, cancel, remove_after:Path|None=None)->Track`, `convert_to_multiplex(lib, track, ...)->Track`, `find_clip(artist,title)->list[VideoCandidate]`, `add_clip(lib, track, video, ...)->Track`; `youtube.download_video(..., video_only=False)`.
- Testes com dependências falsas.

### Task 7: `audio/player.py`
**Produces:** `Player(path)`: `play()`, `pause()`, `seek(sec)`, `position->float`, `duration`, `playing`, `channel: 'both'|'left'|'right'`, `close()`. Decodifica com ffmpeg para float32 em memória; `sounddevice.OutputStream`.
- Teste: posição avança com stream falso (callback chamado manualmente); `channel='left'` zera o direito.

### Task 8: GUI
`gui/dialogs.py` (EditTrackDialog, ManifestDialog), `gui/sync_window.py`, `gui/check_tab.py`, `gui/import_tab.py`, botões novos na `library_tab`.
- Fumaça: cada janela/aba abre e fecha com dados sintéticos.

### Task 9: Ponta a ponta
- pytest completo + slow; sincronia, verificar, importar e clipe com arquivos reais; prints da GUI.
