# Guia de uso

<p><a href="user-guide.md">English</a> · <b>Português (Brasil)</b></p>

## Primeiros passos
1. Dê dois cliques em `EncoLibMG.bat`.
2. No topo, clique no nome da biblioteca → **Abrir ou criar** (ou `Ctrl O`). Se a pasta ainda não for uma
   biblioteca, o app cria a `EncoreLibrary` com o `manifest.json`.
3. No Encore, aponte o Setup (F2) para a pasta da biblioteca. O Encore também acha sozinho qualquer pasta
   chamada `EncoreLibrary` nos seus drives.

O app segue o idioma do Windows (português do Brasil ou inglês). Troque quando quiser no botão **PT/EN** do topo,
sem reiniciar.

## Telas

### Início
O logo em pixels, a busca e os números da biblioteca. Digite `Artista - Música` e aperte `Enter`.

### Adicionar
![Adicionar](screens/pt-BR/add.png)

Escolha a versão da letra e clique em **Baixar completa**, ou marque várias e clique em **Adicionar N à fila**. Para
cada música o app procura o áudio com a mesma duração da letra (para ela bater), separa a voz do instrumental na sua
GPU, monta o Multiplex e gera o guia MIDI. As cinco etapas acendem conforme avança.
Sem letra sincronizada? **Buscar um vídeo de karaokê (MTV)** abre um seletor com miniaturas do YouTube.

### Fila de downloads
Toda música adicionada entra na **fila**: o botão **Fila** no rodapé abre ela. Enquanto a GPU trabalha numa música,
a próxima já está baixando.
- **Adicionar lista…** (na tela Adicionar ou na fila) aceita uma lista colada (um `Artista - Música` por linha), o
  link de uma **playlist pública do YouTube** ou uma **playlist do Spotify** exportada em CSV com o
  [Exportify](https://exportify.net) (qualquer CSV com colunas de artista e título também serve). A letra
  sincronizada é escolhida sozinha, só quando artista, título (e duração, no Spotify) batem de verdade.
- Cada música mostra onde está: na fila, procurando a letra, baixando, esperando a GPU, processando, pronta.
- As que **falharam** dizem o motivo. Sem letra sincronizada, **MTV** busca um vídeo de karaokê no lugar; **Tentar de
  novo** volta a música para a fila.
- **Pausar** (ou Cancelar no rodapé) para e guarda o que já foi baixado. Adicionar músicas faz a fila andar de novo.
- A fila fica salva: feche o app e ela continua lá na próxima vez, **pausada** até você clicar em **Continuar**.
- Quando acaba, um resumo diz quantas entraram com guia, sem guia, quantas já existiam e quantas falharam.

### Biblioteca
![Biblioteca](screens/pt-BR/library.png)

Filtros (Multiplex, com guia, sem guia, MTV, MIDI, invisíveis), ordenação, seleção múltipla e um painel por
faixa. Pelo painel você ouve instrumental/voz/ambos, abre a Sincronia e a Prévia do guia, gera o guia, edita o
nome, adiciona clipe, converte para Multiplex ou remove.

### Sincronia
![Sincronia](screens/pt-BR/sync.png)

A onda da voz em pixels, com cada linha da letra marcada. Arraste a onda para ir e voltar.
- **Deslocar tudo:** ±1 s ou ±0,1 s.
- **Âncoras:** com a música tocando, aperte `Espaço` quando a linha selecionada começar a ser cantada.
  Com duas ou mais, a letra é esticada entre elas.
- **Sugerir:** acha sozinho onde a voz começa.
- Sempre fica backup, com **Desfazer**. Ao salvar, o app oferece regerar o guia.

### Prévia do guia
![Prévia do guia](screens/pt-BR/guide.png)

O rolo de piano com as notas que o Encore usa no guia de afinação e na pontuação, e a letra acendendo palavra a
palavra, como no Encore. Ouça só a **Voz** para conferir se as notas acompanham o canto.

### Verificar
![Verificar](screens/pt-BR/check.png)

Acha o que o Encore ignoraria ou mostraria errado e corrige com um clique:
áudio sem letra, faixa sem guia MIDI, letra fora do padrão, formatos não aceitos (FLAC, WMA, MOV…), arquivos em
subpasta, manifest incompleto, tags faltando e, opcionalmente, volume.

### Importar
Traz o que você já tem: CDs/FLAC, coleções CDG, `.zip` e karaokês `.kar`/`.mid` (título lido de dentro do arquivo,
inclusive em japonês). Antes de importar, você confere os nomes numa prévia editável. O app pode gerar o Multiplex
**a partir do seu arquivo**, com a qualidade da sua fonte.

### Visual e som
- **Vídeos de fundo** por categoria, do PC ou do YouTube (só um trecho de até 5 minutos).
- **Imagens de espera** da tela entre músicas.
- **Vídeo de abertura** da biblioteca.
- **Narração da nota**: um áudio por faixa de pontuação.
- **SoundFont**: inclui o download do GeneralUser GS, gratuito.

### Configurar
⚙ no topo: nome, descrição e opções da biblioteca no Encore.

## Atalhos
| Tecla | Ação |
|---|---|
| `/` | Buscar uma música |
| `1`–`6` | Início, Adicionar, Biblioteca, Verificar, Importar, Visual e som |
| `Espaço` | Tocar/pausar · na Sincronia: marcar âncora |
| `←` `→` | Voltar/avançar 5 s |
| `Esc` | Fechar janela, painel ou voltar |
| `Ctrl O` | Abrir ou criar biblioteca |
| `?` | Todos os atalhos |

## Bom saber
- **Nada é apagado de verdade:** o que sai vai para a Lixeira, e toda letra alterada ganha backup.
- **A primeira música demora mais:** os modelos de IA (Demucs, CREPE, MMS, 1,6 GB) são baixados na primeira vez.
- **Qual a velocidade no meu PC?** Veja [Hardware](README.pt-BR.md#hardware-o-que-você-precisa-e-o-que-esperar) ou rode
  `python scripts/benchmark.py`.
- **Log:** `%APPDATA%\EncoLibMG\log.txt`, útil para relatar um problema.

## Identidade
Marca **"Letra cantada"**: uma linha de karaokê no meio do preenchimento, entre colchetes de canto. A estética é
inspirada no [Omarchy](https://omarchy.org/), com desenho original. Tudo (marca, wordmark, ícone do Windows) é
gerado a partir de grades de pixels por [scripts/brand/build.py](../scripts/brand/build.py); veja a
[página da identidade](brand/index.html).
