# Fases 5, 6 e 7 — Guia MIDI, SoundFont e visual: especificação

Parte do [roadmap](../roadmap.md). As Fases 3 (lote) e 4 (letras sem LRCLIB) foram puladas a pedido do usuário.
A única parte da Fase 4 de que a 5 precisa (tempo de cada palavra) entra aqui.

**Problema que motivou:** nas faixas Multiplex, o guia de afinação e a pontuação ficam ruins.

## Por que o guia está ruim (lido no código do Encore)
- Sem guia MIDI, o Encore analisa o canal da voz **ao vivo**, quadro a quadro (`startStreamingGuideAnalysis`,
  `Playback.js` ~L993). Usa o detector `Pitchy` (2048 amostras, limiar de clareza, nota mínima de 80 ms) e
  tira a média do pitch de cada trecho. Backing vocals, reverb e sobras de instrumento viram notas; notas longas
  com vibrato se quebram; oitavas pulam.
- A pontuação compara o microfone com essas notas (`scoring.activeMidiNotes`). Guia errado = nota errada.
- Com um **MIDI companheiro** (`X.guide.mid`) ao lado do áudio, a análise ao vivo é desligada e o Encore usa as
  notas do arquivo (`hasMidiGuide`, ~L1368).

## Regras do guia MIDI companheiro (confirmadas no código)
| Regra | Onde |
|---|---|
| Nomes aceitos: `X.guide.mid`, `X.guide.kar`, `X.melody.*`, `X.mid`, `X.kar` | `FsSvc.js` ~L695 |
| As notas do guia **só são extraídas se o MIDI tiver mais de 5 eventos de letra** | `Playback.js` ~L635 |
| Se o MIDI tem letra, **ela substitui o `.lrc` na tela**: o realce passa a ser sílaba a sílaba | `LyricsEngine.js` ~L456 vs ~L725 |
| `@IVOCAL-CH=N` (evento de texto) fixa o canal da melodia (1–16) | `Playback.js` ~L655 |
| O MIDI companheiro **toca som** pelo sintetizador; o volume do canal-guia é o controle "Guide" do mixer (`M`) | `setGuideTrackVolume` ~L1903 |
| Letra: eventos *lyric* (0x05); `/` ou `\` no início = nova linha; `{#TITLE=…}{#ARTIST=…}` no começo = metadados | `LyricsEngine.js` ~L476–600 |
| Furigana: `漢字[かんじ]` dentro do evento | ~L578 |
| Dueto: `[m]`, `[f]`, `[m2]`, `[f2]`, `[a]` no texto | ~L560 |
| Cada sílaba é realçada até a próxima (no máximo 1,5 s); contagem regressiva e interlúdios são automáticos | ~L640–700 |
| Codificação do texto detectada automaticamente (UTF-8 funciona) | `detectEncoding` |

Consequência: o guia **precisa** levar a letra com o tempo de cada palavra, e essa letra é a que aparece na tela.
Bem feita, é uma melhora: realce palavra a palavra, como nos karaokês profissionais. Mal alinhada, piora a
experiência. Por isso o alinhamento tem verificação e plano B (abaixo).

---

## Fase 5 — Guia MIDI "Platinum"

### 5.1 Melodia (notas)
Fonte: **canal direito do Multiplex** (a voz já separada; não precisa separar de novo).
1. **CREPE** (`torchcrepe`, modelo `full`, GPU, passo de 10 ms, faixa de voz 65–1100 Hz) → f0 + periodicidade.
2. Vozeado = periodicidade ≥ 0,5 **e** volume ≥ (máx − 40 dB). Filtro de mediana de 5 quadros no pitch.
3. Segmentação em notas: abre nota em trecho vozeado; fecha quando há silêncio ≥ 50 ms **ou** quando o pitch se
   afasta mais de 0,8 semitom da mediana da nota por ≥ 60 ms (troca de nota). Vibrato não quebra a nota.
4. Altura da nota = mediana arredondada para o semitom. Descarta notas < 90 ms. Junta notas vizinhas iguais com
   intervalo < 80 ms.
5. **Correção de oitava**: nota curta (< 250 ms) a 12 semitons das duas vizinhas é trazida para a oitava delas.
6. Só ficam notas dentro da janela cantada da letra (do início de uma linha até o começo da próxima, com folga
   de 0,5 s). Assim, ad-libs e backing vocals nos intervalos não viram guia.

### 5.2 Tempo de cada palavra
Para cada linha do `.lrc`, recorta a voz entre o início da linha e o início da próxima (± 0,3 s) e roda o
alinhador forçado **MMS_FA** do torchaudio (multilíngue, GPU):
- Texto romanizado para o alinhador: sem acento e minúsculo para línguas latinas; japonês via `pykakasi`
  (romaji); coreano via tabela de romanização simples (Revised Romanization por jamo).
- Resultado: início de cada palavra (japonês: de cada trecho do `pykakasi`).
- **Verificação**: a linha é aceita se o score médio do alinhamento for razoável e as palavras ficarem em ordem,
  dentro da janela. Senão entra o **plano B** dessa linha: as palavras são distribuídas pelos inícios de nota
  detectados na linha (uma palavra por nota, proporcional ao número de sílabas); sem notas, espaçamento uniforme.
- A primeira palavra de cada linha começa no tempo do `.lrc`, a não ser que o alinhador a encontre a até 0,5 s
  dele. *(Ajuste após teste real: o `.lrc` do LRCLIB costuma vir ~0,1–0,3 s adiantado; o alinhador ouve o início
  de verdade.)*
- Japonês: leitura dos kanji pelo **MeCab** (`fugashi` + UniDic), que entende o contexto. O `pykakasi` sozinho
  lia 君の名は como "kun no mei ha". O `pykakasi` fica só para converter kana em romaji.

### 5.3 Arquivo `X.guide.mid`
- MIDI formato 1, 480 PPQ, andamento fixo de 120 BPM (1 tick = 1,0417 ms; tempos exatos).
- Trilha 0: andamento, `{#TITLE=…}{#ARTIST=…}` como eventos de letra no tick 0.
- Trilha 1 "Guide": canal 1, programa 73 (flauta). **CC7 = 0** (mudo por padrão; o usuário aumenta no mixer
  `M` → Guide). Evento de texto `@IVOCAL-CH=1`. Notas com velocidade 100. Eventos de letra:
  - uma palavra por evento, com espaço no fim; `/` antes da primeira palavra de cada linha (exceto a primeira);
  - japonês com kanji: `漢字[かんじ]` (furigana em hiragana via `pykakasi`);
  - UTF-8.
- O `.lrc` continua ao lado (usado se o guia for removido).

### 5.4 No programa
- **Faixas novas**: o guia é gerado automaticamente depois do Multiplex (opção ligada por padrão: "Gerar guia
  MIDI"). Custo estimado ~20–40 s por música na RTX.
- **Faixas existentes**: aba Biblioteca → **🎼 Gerar guia** (uma ou várias selecionadas) e aba Verificar →
  novo item "Multiplex sem guia MIDI" (corrigível).
- **Prévia do guia** (janela): rolo de piano simples (notas como barras, letra embaixo) tocando junto com o
  áudio, para conferir antes de ir para o Encore. Botões: tocar/pausar, ouvir voz/instrumental/ambos,
  "Remover guia".
- Ao salvar uma sincronia (`.lrc`) de uma faixa que tem guia: pergunta se quer **regerar o guia** (senão o guia
  fica com a letra antiga).
- Aba Biblioteca: tipo mostra "+ guia".

---

## Fase 6 — MIDI e SoundFont

### 6.1 Importar karaokê MIDI (`.kar`/`.mid`)
O importador já copia MIDIs. Melhorias:
- Nome a partir do próprio arquivo: cabeçalhos `@T` (título) e `@T`/`@A`-like (artista) de `.kar`, ou o
  evento *track name*, antes de cair no nome do arquivo.
- Codificação: mostra o nome corretamente mesmo em Shift-JIS/Windows-1252 (o Encore detecta sozinho no player).
- Verificação: MIDI sem nenhum evento de letra é marcado como "MIDI sem letra" no Verificar (o Encore toca, mas
  sem karaokê).

### 6.2 SoundFont da biblioteca
*(Na implementação, foi para a aba **Visual e som → SoundFont**, porque o download precisa da barra de
progresso e do Cancelar, e a janela Configurar é modal.)*
- Escolher um `.sf2`/`.sf3`/`.dls` do PC. O programa copia para
  `SoundFonts/` dentro da biblioteca e grava `additionalContents.soundFont` (caminho relativo, como o Encore
  espera em `EncoreLoader.js` ~L318).
- Botão **Baixar GeneralUser GS** (SoundFont GM gratuito com licença que permite uso e redistribuição), se o link
  oficial estiver acessível; senão só a opção de escolher arquivo.

### 6.3 Fica de fora (com motivo)
- **`.chorus.ogg` para MIDI**: exigiria sincronizar uma gravação qualquer com o andamento do MIDI, que varia por
  arquivo. Não dá para fazer de forma confiável e automática.

---

## Fase 7 — Visual da biblioteca

Todos os caminhos são relativos à pasta da biblioteca. Subpastas são permitidas para esses arquivos
(`pathJoin(libraryInfo.path, …)`), e o Encore não as confunde com músicas (ele só varre a raiz).

### 7.1 Vídeos de fundo (BGV)
- Aba nova **Visual** → seção "Vídeos de fundo": lista de categorias (`BGV_CATEGORY`) e seus vídeos.
- Adicionar vídeos: **do PC** (copia/converte para `BGV/<categoria>/`, mp4 H.264 ≤1080p, **sem áudio**,
  `-movflags +faststart`) ou **do YouTube** (busca, escolhe, baixa só o vídeo).
- Do YouTube, só um trecho de até 5 min (pulando 30 s de abertura nos vídeos longos): os vídeos de paisagem
  costumam ter de 1 a 12 h, e o Encore repete o BGV em loop. *(Ajuste após teste real.)*
- Criar/renomear/remover categoria; remover vídeo (Lixeira).
- Correção junto: "Mostrar categoria MTV" e "Mostrar categorias padrão" são ligadas por padrão no Encore
  (`?? true`). A janela Configurar passa a gravar `false` ao desmarcar; antes, desmarcar não tinha efeito.
- Grava `additionalContents.bgvCategories = [{BGV_CATEGORY, BGV_LIST: ["BGV/…/x.mp4", …]}]`.

### 7.2 Imagens de espera (bumpers) e vídeo de abertura
- "Imagens de espera": adicionar imagens (png/jpg/webp) → `Bumpers/`, grava `additionalContents.bumperImages`.
  Prévia em miniatura.
- "Vídeo de abertura": escolher um vídeo → `Boot/boot.mp4` (H.264), grava `additionalContents.bootVideo`.

### 7.3 Narração da nota (descoberto no código)
- `additionalContents.scoreNarrations = [{min, max, file}]`: áudio tocado no fim conforme a nota. Seção
  "Narração da nota": faixas de nota (ex.: 0–69, 70–99, 100) com um áudio cada → `Narrations/`.

### 7.4 Correção de manifest
O Encore só cria a categoria automática **MTV** se `additionalContents.bgvCategories` existir
(`EncoreHome.js` ~L500), mesmo vazia. Bibliotecas criadas pelo programa passam a ter
`additionalContents: {bgvCategories: [], bumperImages: []}`; o Verificar adiciona isso nas antigas
("Manifest incompleto", corrigível).

---

## Módulos
```
encolibmg/
  guide/melody.py     f0 (CREPE) → notas (segmentação, oitava, janelas da letra)
  guide/align.py      MMS_FA por linha, romanização, verificação, plano B
  guide/romanize.py   latino sem acento, japonês (pykakasi), coreano (jamo → RR)
  guide/midi.py       escrever/ler X.guide.mid (mido, UTF-8)
  guide/build.py      orquestra: multiplex → notas + palavras → guide.mid
  visual.py           BGV, bumpers, boot, narrações (cópia/conversão + manifest)
  soundfont.py        escolher/baixar SoundFont + manifest
  importer.py         + nome a partir de cabeçalhos .kar
  checker.py          + "Multiplex sem guia", "MIDI sem letra", "Manifest incompleto"
  gui/guide_preview.py, gui/visual_tab.py, (ManifestDialog + SoundFont)
```
Dependências novas: `torchcrepe`, `mido`, `pykakasi`. O modelo do MMS_FA (~1,2 GB) baixa no primeiro uso.

## Testes
- melody: f0 sintético (escada de notas com vibrato ±0,3 st) → notas exatas; buraco de 40 ms não quebra;
  troca de nota quebra; nota de oitava curta corrigida; notas fora das janelas descartadas.
- align: romanização (pt com acento, ja, ko); plano B distribui por inícios de nota; linha sem notas = uniforme;
  primeira palavra presa no tempo do LRC; ordem garantida.
- midi: ida e volta (escrever → ler): notas, letra UTF-8, `/` de linha, `{#TITLE}`, `@IVOCAL-CH=1`, CC7=0,
  furigana; > 5 eventos de letra.
- build: com dependências falsas, gera `X.guide.mid` ao lado; Library mostra "+ guia".
- visual/soundfont: manifest correto, caminhos relativos, conversão sem áudio, chaves desconhecidas preservadas.
- checker: três itens novos detectados e corrigidos.
- importer: nome a partir de `@T`.
- Lento (marcado `slow`): CREPE e MMS_FA de verdade em voz sintética.
- Manual: gerar guia de uma faixa real, ver a prévia, conferir no Encore o pitch guide, a pontuação e o realce
  palavra a palavra.

## Ordem de entrega
Fase 5 primeiro, por ser o problema que você sentiu. Ela entra testada e verificada com uma música real
antes de começar a 6 e a 7.
