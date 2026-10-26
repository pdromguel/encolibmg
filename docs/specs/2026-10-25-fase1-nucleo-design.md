# Fase 1 — Núcleo: especificação

Parte do [roadmap](../roadmap.md). Meta: digitar `Artista - Música`, escolher uma versão e, em poucos minutos,
a faixa aparecer no Encore como **Multiplex + LRC** (nível 3). Sem letra sincronizada → **MTV** (nível 1).

## Ambiente
- Windows, Python **3.12** num `venv` dentro da pasta do projeto (`.venv`).
- `torch==2.8.*` + `torchaudio==2.8.*` (índice `cu128`, necessário para a RTX 5070 Ti/Blackwell),
  `demucs`, `soundfile`, `yt-dlp`, `mutagen`, `requests`, `pytest`.
  torchaudio 2.8 fixado porque a partir da 2.9 o `torchaudio.save` usado pelo Demucs depende do `torchcodec`.
- `ffmpeg` no PATH (já instalado). O instalador avisa se faltar.
- Sem GPU CUDA → Demucs roda em CPU (mais lento, funciona).

## Regras de arquivo (confirmadas no `FsSvc.js`)
- Todos os arquivos ficam **na raiz** da biblioteca (o Encore não varre subpastas).
- Nome-base: `Artista - Música`, sem `< > : " / \ | ? *`, sem ponto/espaço no final, máx. 150 caracteres.
- Faixa completa: `Artista - Música.multiplexed.mp3` + `Artista - Música.lrc` (o `.lrc` usa o nome **sem** `.multiplexed`).
- MTV: `Artista - Música.mp4`.
- Áudio sem par (`.lrc`/`.cdg`/MIDI) é invisível no Encore → nunca é deixado assim pelo programa.
- `manifest.json` mínimo criado pelo programa: `{"title": "<nome>", "description": "Criada pelo EncoLibMG"}`.
  Manifest existente nunca é sobrescrito.

## Módulos

### `library.py`
- `Library(path)`: `create(path, title)` cria pasta + manifest; `open(path)` exige `manifest.json`.
- `base_name(artist, title) -> str` (sanitização acima).
- `scan() -> list[Track]`: agrupa arquivos por nome-base (removendo `.multiplexed`) e devolve
  `Track(base, artist, title, files, kind)` com `kind` ∈ `multiplex_lrc | audio_lrc | mtv | midi | orphan`.
  `orphan` = áudio sem par.
- `exists(base) -> bool`, `remove(track)` (apaga todos os arquivos do nome-base, manda para a Lixeira via `send2trash`).

### `lyrics/lrclib.py`
- `search(query) -> list[LyricsCandidate]` via `GET https://lrclib.net/api/search?q=`,
  com `User-Agent: EncoLibMG/0.1`. Candidato: `id, artist, title, album, duration, synced, plain`.
- Ordena: com `syncedLyrics` primeiro, depois por proximidade do texto buscado.

### `lyrics/normalize.py`
- `normalize_lrc(text, offset_ms=0) -> str`:
  - aceita `[mm:ss]`, `[mm:ss.x]`, `[mm:ss.xx]`, `[mm:ss.xxx]`;
  - linha com várias marcações vira várias linhas;
  - aplica `[offset:]` do arquivo + `offset_ms` (positivo = letra aparece antes, como no padrão LRC);
  - remove tags de metadados, marcações palavra-a-palavra `<mm:ss.xx>` e linhas vazias;
  - ordena por tempo; saída `[mm:ss.xx] texto`, UTF-8 sem BOM, `\n`.

### `youtube.py`
- `search(query, n=10) -> list[VideoCandidate]` (`yt-dlp` `ytsearchN:`, `extract_flat`): `id, title, channel, duration, url`.
- `pick_audio(candidates, target_duration)`: menor |duração − alvo|, ignorando > 8 s de diferença e títulos com
  `karaoke|instrumental|cover|live|ao vivo|8d|slowed|sped up|nightcore|reverb` (a menos que a busca os contenha).
  Busca usada: `"{artista} {título} audio"`.
- `download_audio(url, dest_dir) -> Path` (melhor áudio → WAV via ffmpeg).
- `download_video(url, dest) -> Path` (≤1080p, mp4 h264/aac, `merge_output_format=mp4`).
- Busca de MTV: `"{artista} {título} karaoke"`.

### `audio/separate.py`
- `separate(wav, work_dir, device="auto") -> (instrumental, vocals)`: `python -m demucs --two-stems=vocals -n htdemucs`
  em subprocesso, com progresso lido do stderr.
### `audio/multiplex.py`
- `make_multiplex(instrumental, vocals, dest_mp3)`: cada stem vira mono e entra num canal
  (**esquerda = instrumental, direita = voz**), `libmp3lame` 320 kbps.

### `tags.py`
- `write_tags(mp3, artist, title)` com `mutagen` (ID3v2.3, para o `jsmediatags` do Encore ler bem).

### `pipeline.py`
- `add_song(lib, lyrics: LyricsCandidate, on_progress)`:
  1. se `lib.exists(base)` → erro "já existe";
  2. busca áudio pela duração da letra → baixa → Demucs → multiplex → `.lrc` normalizado → tags;
  3. tudo é gerado numa pasta temporária e **só movido para a biblioteca no fim** (nunca deixa faixa pela metade).
- `add_mtv(lib, artist, title, video: VideoCandidate, on_progress)`.
- `on_progress(step: str, fraction: float | None)`. Etapas: `buscando áudio`, `baixando`, `separando voz`,
  `mixando`, `salvando`.
- Cancelamento: `threading.Event` checado entre etapas e no subprocesso do Demucs.

### `gui/` (Tkinter + ttk)
- **Aba Adicionar**: campo de busca → lista de letras (artista, título, álbum, duração, ✓ sincronizada).
  Botões: *Baixar completa* (Multiplex+LRC) e *Sem letra → buscar MTV* (lista de vídeos de karaokê,
  escolher um). Barra de progresso + etapa atual + Cancelar. Trabalho roda numa thread; a GUI recebe eventos por `queue`.
- **Aba Biblioteca**: tabela (artista, título, tipo, arquivos); filtro de texto; Remover (com confirmação),
  Abrir pasta, Atualizar. Faixas `orphan` em destaque com ⚠.
- Barra superior: biblioteca atual + Trocar/Criar. Último caminho salvo em `%APPDATA%\EncoLibMG\config.json`.

## Scripts
- `instalar.bat`: cria `.venv` com `py -3.12`, instala dependências (`requirements.txt` + torch cu128), checa `ffmpeg`.
- `Abrir EncoLibMG.bat`: `.venv\Scripts\pythonw -m encolibmg`.

## Erros
- Rede/LRCLIB/YouTube fora → mensagem clara na janela, nada é escrito na biblioteca.
- Nenhum áudio com duração compatível → oferece buscar MTV.
- Demucs/ffmpeg falha → mostra as últimas linhas do log; pasta temporária apagada.
- Log completo em `%APPDATA%\EncoLibMG\log.txt`.

## Testes (pytest, sem rede)
- `base_name`: caracteres inválidos, espaços, tamanho.
- `normalize_lrc`: formatos de tempo, várias marcações, offset, palavra-a-palavra, ordenação.
- `scan`: classificação de cada `kind` com arquivos vazios de mentira.
- `pick_audio`: duração e filtros de título.
- `make_multiplex`: dois senos sintéticos (440 Hz / 880 Hz) → confere que o canal esquerdo é o instrumental.
- `lrclib.search` e `youtube.search` com respostas gravadas (mock).
- Manual: uma música real ponta a ponta + abrir no Encore.

## Ideia anotada para depois
O `FsSvc.js` associa `X.mp4` a `X.multiplexed.mp3`: o vídeo vira o fundo da faixa multiplex.
Dá para ter **clipe oficial + voz-guia + letra** (Fase 2).
