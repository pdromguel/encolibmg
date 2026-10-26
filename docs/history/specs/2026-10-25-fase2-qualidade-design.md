# Fase 2 — Qualidade e organização: especificação

Parte do [roadmap](../roadmap-phases.md). Construída sobre a [Fase 1](2026-10-25-fase1-nucleo-design.md).
Meta: deixar cada faixa **certa** (letra no tempo, volume igual, nome correto) e trazer para a biblioteca
o que você já tem no PC.

## Fatos do Encore que guiam esta fase (lidos no código)
- `X.mp4` + `X.multiplexed.mp3` → o vídeo toca **mudo como fundo** e o áudio vem do Multiplex
  (`PlaybackManager.js` ~L336–376). A faixa ganha clipe, voz-guia, letra e pontuação ao mesmo tempo.
  O Encore tem ajuste de sincronia do vídeo nas teclas `[`/`]`.
- O `.lrc` só é lido como `[mm:ss.xx] texto`, uma marcação por linha, **sem `[offset:]`**. Ajuste de tempo
  precisa ser gravado nos próprios tempos.
- Formatos aceitos: áudio `mp3 m4a ogg wav`, vídeo `mp4 mkv webm avi`. Qualquer outro (`flac`, `wma`,
  `aac`, `opus`, `mov`…) é ignorado e precisa ser convertido.
- Só a raiz da pasta é lida; subpastas são ignoradas.
- O `songdb.json` guarda o código de 6 dígitos pelo nome do arquivo: **renomear uma faixa muda o código dela**.
  O programa avisa antes de renomear.

## 1. Ajuste de sincronia (janela "Sincronia")
Abre a partir da aba Biblioteca, para faixas com `.lrc`.

- Toca o áudio da faixa dentro do programa (`sounddevice` + `soundfile`, decodificado para memória).
  Botão **Ouvir: Instrumental / Voz / Ambos**: no Multiplex, escolhe o canal.
- Lista de linhas da letra com o tempo de cada uma; a linha atual fica destacada enquanto toca.
  Clicar numa linha pula para 1 s antes dela.
- **Deslocar tudo**: botões −1 s, −0,1 s, +0,1 s, +1 s e campo numérico. O resultado aparece na hora.
- **Âncoras (para letras que "escorregam" ao longo da música)**: tocando, aperte `Espaço` quando a linha
  selecionada começar a ser cantada. A linha recebe o tempo atual menos 150 ms (tempo de reação).
  - 1 âncora → desloca tudo.
  - 2 ou mais → ajuste linear (deslocamento + esticamento) pelas âncoras. Entre âncoras, interpolação linear;
    fora delas, extrapola a reta da âncora mais próxima.
  - `Backspace` remove a âncora da linha selecionada.
- **Sugerir automaticamente**: acha o início da voz na faixa de voz (canal direito do Multiplex) e propõe
  o deslocamento que alinha a primeira linha com ele. Detecção: RMS em janelas de 50 ms; o início é a
  primeira janela acima de `max(RMS) − 30 dB` que fica acima disso por ≥ 300 ms. Só para Multiplex.
- **Salvar**: grava o `.lrc` normalizado. O original vai antes para
  `%APPDATA%\EncoLibMG\backups\<data>\`. **Desfazer** restaura o último backup da faixa.

## 2. Volume uniforme (normalização)
- Alvo **−16 LUFS integrado**, pico verdadeiro **≤ −1 dBTP**. Ganho fixo, sem compressão: preserva a
  dinâmica. Se o ganho necessário estourar o pico, ele é limitado até o pico caber.
- Medido com o filtro `ebur128` do ffmpeg no arquivo estéreo inteiro (instrumental + voz no Multiplex).
- **Faixas novas** (Fase 1 em diante): o ganho é aplicado na hora de gerar o mp3 → nenhuma recompressão a mais.
  `make_multiplex` passa a gerar um WAV intermediário, medir e então codificar com o ganho.
- **Faixas existentes**: pela aba Verificar. mp3 → recodifica a 320 kbps com o ganho; vídeo → recodifica só o
  áudio (AAC 256 kbps) e copia o vídeo.
- Marca `TXXX:EncoreLM-Loudness=-16` nas tags (mp3) para não normalizar de novo. Vídeos ficam com a marca
  no metadado `comment` do mp4.
- Tolerância: só corrige se estiver a mais de 1,5 LU do alvo.

## 3. Aba "Verificar"
Botão **Verificar biblioteca** → lista de problemas (tipo, faixa, descrição) com **Corrigir selecionados**
e **Corrigir tudo que for automático**. Checagem de volume é opcional (caixa "incluir volume — lento", ~1 s/faixa).

| Problema | Correção automática |
|---|---|
| Áudio sem letra (invisível no Encore) | Busca no LRCLIB por artista/título com duração a ±3 s do arquivo; achou → grava `.lrc` |
| `.lrc` fora do formato do Encore | Normaliza (com backup) |
| Arquivo em formato não aceito (`flac`, `wma`, `mov`…) | Converte (áudio → mp3 320k; vídeo → mp4 H.264/AAC) e manda o original para a Lixeira |
| Mídia dentro de subpasta (o Encore ignora) | Move para a raiz se o nome não colidir |
| Pasta temporária esquecida (`.encore-tmp-*`) | Apaga |
| mp3 sem tags artista/título | Grava a partir do nome do arquivo |
| Volume fora do alvo (opcional) | Normaliza |
| Nome sem `Artista - Título` | — (sugere usar **Editar**) |
| Possível duplicata (mesmo artista+título ignorando maiúsculas/pontuação) | — (só avisa) |

Correções rodam no `Worker` com progresso e Cancelar. Cada correção é independente: uma falha não para as outras;
o resultado aparece na linha (✔ / ✖ motivo).

## 4. Aba "Importar"
Traz arquivos que você já tem (CDs, coleções de karaokê, downloads antigos).

1. Escolhe a pasta de origem (com subpastas, e dentro de `.zip`).
2. O programa monta uma **prévia**: arquivo de origem → nome final, o que vai acontecer, situação.
   - Nome: tags (artista/título) → senão nome do arquivo `Artista - Título` (limpando número de faixa
     `01 - `, `01.` e sufixos como `(Official Audio)`, `[Karaoke]`, `(Lyrics)`) → senão pasta-mãe como artista.
   - Pareia `mp3`+`cdg`, áudio+`lrc`, áudio+`kar/mid` pelo mesmo nome-base (sem diferenciar maiúsculas),
     inclusive dentro de zips.
   - Duplo clique numa linha edita artista/título. Linhas podem ser desmarcadas.
3. Opções:
   - **Copiar** (padrão) ou **Mover**.
   - **Buscar letra sincronizada para áudios sem letra** (ligado).
   - **Converter áudios com letra para Multiplex** (desligado: lento, ~50 s/faixa). Usa o arquivo local,
     não o YouTube, então mantém a qualidade da sua fonte.
   - **Normalizar volume** (ligado).
4. **Importar**: executa linha a linha com progresso; não sobrescreve nada que já existe (marca "já existe").
   Áudio sem letra e sem letra encontrada **não é importado** (ficaria invisível); aparece como "sem letra".

## 5. Editar faixa
Aba Biblioteca → **Editar…**: muda artista e título. Renomeia todos os arquivos irmãos (`.multiplexed.mp3`,
`.lrc`, `.mp4`, `.cdg`, `.kar`…) e regrava as tags. Aviso sobre o código do `songdb.json`. Recusa se o novo nome
já existir.

## 6. Adicionar clipe a uma faixa Multiplex
Aba Biblioteca → **Adicionar clipe…** (só faixas Multiplex sem vídeo).
- Busca `"{artista} {título} official video"`, lista com duração; marca com ✓ os vídeos a ±2 s da duração
  do áudio (os que têm mais chance de estar no tempo).
- Baixa **só o vídeo** (sem áudio, ≤1080p, H.264) como `X.mp4`. Menor e o Encore toca mudo de qualquer jeito.
- Na Biblioteca a faixa aparece como **Multiplex + LRC + clipe**.

## 7. Configurar biblioteca (manifest)
Botão na barra superior → janela com:
- Título, Descrição.
- Opções (flags do Encore):
  - `enableMtvCategory` — "Mostrar categoria MTV"
  - `enableDefaultCategories` — "Mostrar categorias padrão"
  - `flipArtistTitle` — "Inverter artista/título na exibição"
  - `skipToFirstNoteOn` — "MIDI: pular silêncio inicial"
- Preserva qualquer outra chave que o manifest já tenha (BGVs, SoundFont etc.).

## 8. Converter para Multiplex
Aba Biblioteca → **Converter para Multiplex** em faixas `Áudio + LRC`: separa o próprio arquivo
(sem YouTube), gera `X.multiplexed.mp3` e manda o áudio antigo para a Lixeira.

## Módulos novos / alterados
```
encolibmg/
  lyrics/sync.py        parse/format LRC em memória, shift, âncoras, início da voz
  audio/loudness.py     medir (ebur128) e calcular ganho; aplicar em mp3/vídeo
  audio/multiplex.py    + ganho embutido (WAV intermediário → medir → mp3)
  audio/player.py       tocar array em memória com posição, pausa, seek, canal
  audio/convert.py      converter formatos (ffmpeg)
  library.py            + rename_track, has_video em Track, kind_label
  manifest.py           ler/gravar manifest preservando chaves
  checker.py            Issue + checagens + correções
  importer.py           varrer origem, inferir nomes, parear, prévia, importar
  pipeline.py           + track_from_local(...) (separa arquivo local), + add_clip(...)
  gui/sync_window.py, gui/check_tab.py, gui/import_tab.py, gui/dialogs.py (editar, manifest)
```
Dependência nova: `sounddevice`.

## Erros
- Tudo que apaga vai para a **Lixeira** (`send2trash`); `.lrc` alterado sempre tem backup.
- Renomear/mover nunca sobrescreve: colisão vira erro explicado.
- Importação e verificação continuam após falha em uma faixa e mostram o motivo na linha.

## Testes
- `sync`: parse/format ida-e-volta; shift; 1 âncora = shift; 2 âncoras = linear exato; extrapolação;
  tempos nunca negativos; início da voz em sinal sintético (silêncio 3 s + tom).
- `loudness`: ganho para tom sintético medido; limite de pico; tolerância.
- `multiplex`: com ganho, saída medida ≈ −16 LUFS (±1).
- `manifest`: preserva chaves desconhecidas; flags.
- `checker`: cada tipo de problema detectado com arquivos sintéticos; cada correção automática.
- `importer`: inferência de nome (tags, nome, número de faixa, sufixos, pasta-mãe); pareamento mp3+cdg
  com maiúsculas diferentes; zip; prévia não toca no disco; import copia/move e não sobrescreve.
- `library.rename_track`: renomeia irmãos e tags; recusa colisão.
- `pipeline.add_clip` e `track_from_local` com dependências falsas.
- GUI: fumaça de cada aba/janela nova.
- Manual: ajustar sincronia de uma faixa real e conferir no Encore; importar uma pasta real; clipe + Multiplex no Encore.
