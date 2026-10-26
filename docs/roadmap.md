# EncoLibMG — Roadmap

> **Estado:** Fases 1, 2, 5, 6 e 7 entregues, mais a nova interface com a identidade EncoLibMG.
> Fases 3 (download em lote) e 4 (letras quando o LRCLIB não tem) foram adiadas a pedido do usuário;
> da 4, entrou só o alinhamento palavra a palavra, que a 5 precisava.

Programa em Python (janela Tkinter) para montar e manter uma `EncoreLibrary`
que aproveite o máximo de recursos do [Encore Karaoke](https://github.com/Encore-Karaoke-Labs/Encore-Karaoke).
Cada fase entrega algo utilizável sozinho; a próxima só começa depois que a anterior estiver aprovada.

---

## O que o Encore entende (lido no código-fonte)

| Arquivo (mesmo nome-base) | O que habilita | Onde no código |
|---|---|---|
| `manifest.json` | Torna a pasta uma biblioteca; título, flags, BGVs, SoundFont, bumpers, vídeo de abertura | `main.ts` (`LibraryManifest`) |
| `Artista - Música.mp3/.m4a/.ogg/.wav` | Faixa de áudio — **só aparece se tiver `.lrc`, `.cdg` ou guia MIDI** | `FsSvc.js` ~L719 |
| `….multiplexed.mp3` | Pan ◀/▶ voz-guia (esquerda = instrumental, direita = voz; começa em -1) + análise de afinação ao vivo | `Playback.js` ~L1368, `State.js` |
| `….lrc` | Letra por linha + romanização JP/KR + overlay OBS. **Parser só aceita `[mm:ss.xx]` no início da linha**: sem `[offset:]`, sem palavra-a-palavra, uma marcação por linha | `LyricsEngine.js` `parseLrc` |
| `….cdg` | Letra gráfica CD+G | `FsSvc.js` |
| `….guide.kar` / `.guide.mid` / `.melody.*` / `.mid` / `.kar` | **Guia MIDI companheiro**: notas exatas para o pitch guide + letra sílaba a sílaba; funciona também com vídeo (MTV) | `FsSvc.js` ~L695, `PlaybackManager.js` ~L366 |
| `.mp4/.mkv/.webm/.avi` | MTV (aparece sozinho) | `FsSvc.js` |
| `.mid/.kar` sozinho | Karaokê MIDI tocado com SoundFont, furigana | `LyricsEngine.js` |
| `….chorus.ogg` | Backing vocals para faixas MIDI (tecla `C`) | `FsSvc.js` ~L690 |
| `songdb.json` | Cache + **códigos numéricos de 6 dígitos** das músicas | `FsSvc.js` |

Níveis de qualidade de uma faixa, do pior para o melhor:

1. **MTV** — vídeo de karaokê com letra embutida.
2. **Áudio + LRC** — letras do Encore, romanização.
3. **Multiplex + LRC** — + voz-guia liga/desliga, pitch guide estimado, pontuação.
4. **Multiplex + LRC + `.guide.kar`** ("Platinum") — + realce palavra a palavra e pitch guide com notas exatas.

---

## Fase 1 — Núcleo (MVP)
Objetivo: adicionar uma música e ela aparecer no Encore no nível 3.

- Criar/abrir a `EncoreLibrary` e o `manifest.json`.
- Buscar letra sincronizada no LRCLIB; mostrar candidatos com duração.
- Buscar no YouTube o áudio com duração mais próxima da letra; baixar com `yt-dlp`.
- Demucs (GPU) → `Artista - Música.multiplexed.mp3` (L instrumental / R voz).
- Gravar `.lrc` **normalizado para o parser do Encore** (expande linhas com várias marcações, aplica `[offset:]` nos tempos, remove tags/linhas vazias, `[mm:ss.xx]`).
- Tags ID3 (artista, título).
- Fallback: sem letra → buscar vídeo de karaokê → salvar MTV.
- Aba Biblioteca: lista com etiquetas (Multiplex / LRC / MTV / ⚠ invisível), remover, abrir pasta.
- `instalar.bat` (venv Python 3.12 + PyTorch CUDA + Demucs + yt-dlp + mutagen) e `Abrir EncoLibMG.bat`.

## Fase 2 — Qualidade e organização
- **Ajuste de sincronia**: tocar a faixa na janela com a letra rolando, deslocar tudo ± ms e salvar (o Encore não lê `[offset:]`).
- **Normalização de volume** (EBU R128) para todas as faixas soarem iguais.
- **Verificador da biblioteca**: áudio sem par (invisível no Encore), nomes fora do padrão, duplicatas, LRC inválido, arquivos órfãos — com botão "corrigir".
- **Importar pasta bagunçada**: renomear para `Artista - Música`, parear MP3+CDG (inclusive `.zip` de CDG), converter formatos, opcionalmente gerar Multiplex.
- **Editor do manifest**: título, descrição e flags (`enableMtvCategory`, `enableDefaultCategories`, `flipArtistTitle`, `skipToFirstNoteOn`).
- Editar artista/título de uma faixa (renomeia todos os arquivos irmãos + tags).

## Fase 3 — Download em lote
- Fila com progresso, pausa e retomada após fechar o programa.
- Entradas: lista em texto (`Artista - Música` por linha), playlist do YouTube, CSV exportado do Spotify (ex.: Exportify).
- Relatório final: o que entrou em qual nível, o que falhou e por quê.
- Download e separação em paralelo (rede e GPU ao mesmo tempo).

## Fase 4 — Letras quando o LRCLIB não tem
- Mais fontes de letra sincronizada (biblioteca `syncedlyrics`: NetEase, Megalobiz, Musixmatch…).
- **Gerar LRC por alinhamento**: letra simples (LRCLIB `plainLyrics`, ou colada por você) + WhisperX/stable-ts sobre a faixa de voz separada.
- Último recurso: transcrever a letra direto da voz (Whisper) e marcar a faixa como "revisar".
- Com isso, o fallback para MTV vira exceção.

## Fase 5 — Guia MIDI "Platinum"
- Gerar `Artista - Música.guide.kar` a partir da voz separada:
  - notas da melodia com Basic Pitch (monofônico, limpo e quantizado);
  - letra sílaba a sílaba com os tempos de palavra do alinhamento da Fase 4.
- Resultado: realce palavra a palavra + pitch guide exato (nível 4).
- Também para MTVs: vídeo + `.guide.kar`.
- Japonês: furigana automático (pykakasi/fugashi) no MIDI, que o Encore exibe como ruby.
- Pré-visualização do guia na janela antes de salvar.

## Fase 6 — MIDI, SoundFont e chorus
- Importar coleções `.mid`/`.kar` existentes (detectar título/artista, corrigir codificação de texto).
- Escolher/baixar SoundFont (`.sf2/.sf3`) e registrar em `additionalContents.soundFont`.
- `.chorus.ogg` para faixas MIDI (a partir de uma gravação original separada pelo Demucs).

## Fase 7 — Visual da biblioteca
- **BGVs**: baixar vídeos de fundo por categoria (paisagens, cidade, anime…), cortar/comprimir e registrar em `bgvCategories` (`BGV_CATEGORY` / `BGV_LIST`).
- `bumperImages` e `bootVideo` (vídeo de abertura) pelo editor do manifest.

## Fase 8 — Extras
- **Songbook imprimível** (PDF/HTML) com os códigos de 6 dígitos do `songdb.json`, por artista e por título — igual ao livrinho do karaokê.
- Estatísticas: quantas faixas por nível, idiomas, tamanho em disco.
- Cópia/sincronização para pendrive ou HD externo (o Encore procura `EncoreLibrary` em todos os drives).
- Várias bibliotecas (ex.: "Anime", "Sertanejo") com troca rápida.
- Atualização do `yt-dlp` com um clique (o YouTube muda com frequência).

---

## Arquitetura (cresce por fase, sem reescrever)

```
encolibmg/
  library.py     pasta, manifest, nomes, varredura, verificador        (F1, F2)
  lyrics/        lrclib.py, normalize.py, providers.py, align.py        (F1, F4)
  youtube.py     busca e download                                       (F1, F3)
  audio/         separate.py (Demucs), multiplex.py, loudness.py        (F1, F2)
  tags.py        ID3                                                    (F1)
  midi/          guide.py (Basic Pitch → .guide.kar), furigana.py       (F5, F6)
  queue.py       fila persistente                                       (F3)
  pipeline.py    orquestra os passos, reporta progresso                 (F1+)
  extras/        songbook.py, bgv.py, sync.py                           (F7, F8)
  gui/           app.py + uma aba por área                              (F1+)
tests/
```

Dependências pesadas (WhisperX, Basic Pitch) só entram na fase que as usa.

## Fora de escopo
- Modificar o próprio Encore.
- Hospedar ou compartilhar músicas. A biblioteca é para uso pessoal, e o conteúdo baixado é responsabilidade do usuário.
