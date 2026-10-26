# EncoLibMG — nova interface e identidade: especificação

Interface nova inspirada na landing page do [Omarchy](https://omarchy.org/): estética de terminal, pixels animados,
detalhes e interações fluidas. É uma criação original na mesma linguagem visual; nenhum código do site é copiado.
Todo o "motor" em Python (Fases 1–7) continua igual. Muda só a casca.

## Nome e identidade
- **Nome:** EncoLibMG (antes "Encore Library Manager"). Pacote `encolibmg`, atalho `Abrir EncoLibMG.bat`,
  configuração em `%APPDATA%\EncoLibMG` (migrada automaticamente da pasta antiga).
- **Marca: "Letra cantada"** (escolhida pelo usuário entre 3 conceitos). Grade 16×16: uma linha de karaokê no meio
  do preenchimento (parte cantada acesa, resto em tom médio) e a próxima linha esperando, entre os colchetes de canto
  do Omarchy.
- **Wordmark:** `ENCOLIB` + `MG` na fonte de pixels 5×7 com traço duplo; `MG` em tom médio (`--field-mid`).
- **Fonte única de verdade:** `scripts/brand.py` desenha tudo a partir das grades:
  - SVGs e `brand.json` em `encolibmg/webui/static/brand/`;
  - `icon.ico` do Windows, de 16 a 256 px, cada tamanho desenhado pixel a pixel;
  - a página de identidade animada em `docs/brand/index.html`.
- **A marca animada é o indicador de carregamento do app**: a linha de cima vai se preenchendo e, quando completa,
  as linhas sobem e a de baixo vira a "cantada", como a tela do Encore.
- **Voz:** curta, direta, em português, como um terminal simpático:
  - diz o resultado ("Pronto: X entrou na biblioteca"), não o processo;
  - todo erro sugere um caminho;
  - mostra o atalho do teclado ao lado das ações.
- **Regras de pixel** (valem para o app inteiro):
  - célula de 10px com intervalo de 1px; quadrados, nunca círculos;
  - colchetes de canto marcam seleção e áreas de soltar arquivos;
  - progresso é sempre um "preenchimento de karaokê", aceso sobre apagado, da esquerda para a direita.

## Decisões
| Tema | Escolha |
|---|---|
| Tecnologia | Janela nativa **pywebview** (WebView2/Edge, já instalado no Windows) desenhando HTML/CSS/JS. Abre com duplo clique, sem navegador. |
| Front-end | ES modules sem build + **lit-html 3** (templates, 3 KB) + Canvas 2D para os efeitos de pixel. Arquivos dentro do pacote; nada é baixado ao abrir. |
| Navegação | Barra no topo + **tela inicial** com logo em pixels e busca grande (escolhido pelo usuário). |
| Tema | **Um só**, monocromático estilo "Solitude" (escolhido pelo usuário). |
| Fonte | JetBrains Mono (OFL), embutida. |
| Interface antiga | Continua disponível com `--tk` até a nova cobrir tudo; depois é removida. |

## Linguagem visual
Paleta (tokens CSS):
```
--bg-deep #0c0e10  --bg #101315  --surface #14181a  --surface-2 #1a1f22
--border #23282b   --border-strong #4b4e55
--text #cacccc     --text-2 #a5aeb4  --muted #8a8d90
--brand #798186    --brand-ink #0c0e10  --brand-soft #7981861f  --selection #343d41
--field-bg #080a0b --field-dim #2a2e30 --field-mid #4e5457 --field-lit #798186
--field-hover #a1a7aa --field-crest #cccfd1
estados (dessaturados, só em selos e ícones):
--ok #8fae8b  --warn #c9b27a  --bad #c98b8b  --info #8ba7c9
```
- Cantos **retos** (raio 0), bordas de 1px, sombras como "anel" (`0 0 0 1px`).
- Títulos 500 de peso, `letter-spacing -0.75px`; texto 15px; `kbd` com borda.
- Botão primário: fundo `--brand`, texto `--brand-ink`; secundário: contorno; foco visível sempre.
- Movimento: entradas "sobem" 14px com fade (stagger de 40 ms), 150–300 ms, `cubic-bezier(.2,.8,.2,1)`.
  Com `prefers-reduced-motion`, as animações viram cortes simples.

## Efeitos de pixel (componentes próprios)
1. **Campo de pixels** (`pixel-field`): canvas de fundo com células de 10px (gap 1px).
   - Bordas com pixels que piscam (densidade maior perto das laterais e da base), cintilação suave.
   - Ondas lentas ("cristas") que atravessam o campo de vez em quando.
   - **Rastro do mouse** em losango (distância de Manhattan) que se apaga em ~600 ms.
   - **Clique** solta um anel de pixels que se expande.
   - Pausa quando a janela está oculta; ~60 fps com orçamento < 2 ms/quadro (só redesenha células que mudaram).
2. **Wordmark ENCOLIBMG em pixels** (a mesma grade da identidade). Na abertura os pixels vêm de pontos aleatórios do
   campo e **se montam** com stagger; perto do mouse tremem e se afastam um pouco; um brilho varre o logo a cada
   ~8 s. A marca na barra do topo "canta" (anima o preenchimento) enquanto há um trabalho rodando.
3. **Barra de progresso em pixels** no rodapé: células enchem da esquerda com um reflexo correndo; indeterminada =
   pixels marchando. Mostra etapa, % e Cancelar.
4. **Transição entre telas**: dissolve em pixels (blocos em ordem aleatória cobrem e revelam, ~280 ms).
5. **Identicon em pixels** para cada faixa: padrão 5×5 simétrico derivado do nome (sem capa disponível, cada
   música ganha uma "arte" própria e estável).
6. **Equalizador em pixels** no mini player enquanto toca; **spinner** em pixels; **confete de pixels** quando uma
   música entra na biblioteca.
7. **Cursor digitando** na busca da tela inicial: exemplos de "Artista - Música" escritos e apagados com caret
   piscando, até você clicar.

## Telas
- **Início**: campo de pixels + logo; busca grande (Enter → Adicionar já com os resultados); linha de números da
  biblioteca (faixas · com guia · problemas, cada um é link); "adicionadas recentemente" com identicons; atalhos.
- **Adicionar**: busca; resultados com selo ✓ sincronizada, álbum, duração; ações **Baixar completa** (com
  "Gerar guia" ligado) e **MTV**. O seletor de vídeo mostra **miniaturas do YouTube**, canal, duração e marca de
  duração compatível.
- **Biblioteca**: filtro instantâneo, ordenação, selos `[MP] [LRC] [GUIA] [CLIPE] [MTV] [MIDI] [⚠]`, seleção
  múltipla com barra de ações em massa (gerar guia, remover). Clicar numa faixa abre um **painel lateral** com:
  identicon grande, arquivos, ▶ ouvir (instrumental/voz), Sincronia, Prévia do guia, Gerar guia, Editar, Clipe,
  Converter, Remover.
- **Sincronia** (tela cheia): **forma de onda** da voz em pixels com as linhas da letra marcadas; playhead; arrastar
  na onda faz seek; deslocar ±; âncoras com `Espaço`; sugerir automaticamente; salvar/desfazer; pergunta de regerar guia.
- **Prévia do guia** (tela cheia): rolo de piano em pixels + linha de karaokê com preenchimento palavra a palavra,
  como no Encore.
- **Verificar**: botão grande, problemas agrupados por tipo com contagem, corrigir selecionados/tudo, resultado
  animado por linha.
- **Importar**: escolher pasta (diálogo do Windows), prévia editável inline, opções, importar com progresso por linha.
- **Visual e som**: categorias de BGV com **miniaturas dos vídeos** (primeiro quadro), grade de imagens de espera,
  player do vídeo de abertura, narrações com ▶, SoundFont.
- **Configurar** (janela sobreposta): nome, descrição, opções do Encore.
- **Ajuda** (`?`): todos os atalhos.
- **Rodapé fixo**: progresso do trabalho atual + mini player.

Atalhos: `/` busca · `1`–`6` telas · `Esc` volta/fecha · `Espaço` tocar/âncora · `?` ajuda · `Ctrl+O` abrir biblioteca.

## Arquitetura
```
encolibmg/webui/
  app.py      cria a janela (pywebview), liga servidor + API, título e fundo escuros
  server.py   HTTP local (127.0.0.1, porta aleatória, token): arquivos da interface + /media com Range
              (seek em áudio/vídeo), restrito à biblioteca aberta e à pasta temporária do importador
  api.py      class Api: métodos que o JS chama (window.pywebview.api.*), sempre devolvem JSON simples
  jobs.py     um trabalho pesado por vez (thread); eventos de progresso para o JS (≤ 20/s), cancelar
  views.py    conversões Track/Issue/ImportItem/... → dicts para o JS
  static/
    index.html
    css/        tokens.css, base.css, components.css, views.css
    js/         app.js (rotas, atalhos), api.js (ponte + eventos), store.js (estado reativo simples),
                fx/ (pixel-field, pixel-logo, pixel-font, pixel-progress, pixel-transition, identicon,
                     equalizer, confetti, typer)
                ui/ (dock, toast, modal, drawer, badges, video-picker)
                views/ (home, add, library, track, sync, guide, check, import, visual, settings, help)
    vendor/     lit-html.js
    fonts/      JetBrains Mono (woff2) + OFL.txt
    brand/      mark.svg, wordmark.svg, brand.json, icon.ico, favicon.png (gerados por scripts/brand.py)
```
- **Ponte JS ↔ Python**: chamadas via `pywebview.api` (assíncronas, devolvem Promise). Eventos de Python → JS por
  `window.evaluate_js("encore.emit(...)")`.
- **Áudio no navegador**: `<audio>` apontando para `/media`; canal instrumental/voz com Web Audio
  (`ChannelSplitter`). Forma de onda calculada em Python (picos reduzidos), mandada como lista.
- Diálogos de arquivo/pasta: nativos do Windows via pywebview.
- Segurança: o servidor só escuta em 127.0.0.1, exige o token da sessão e só serve arquivos dentro das pastas
  permitidas (sem `..`).

## Erros
- Toda chamada da API devolve `{ok, data}` ou `{ok:false, error, kind}`. O JS mostra um **toast** com a mensagem;
  erros inesperados também vão para o log.
- Trabalho cancelado vira toast neutro, não erro.
- Se o WebView2 faltar, o programa avisa e abre a interface antiga (Tk).

## Testes
- **Python**: `api` com biblioteca temporária (cada método devolve o formato esperado), `server` (token, Range,
  bloqueio de `..` e de pastas fora da biblioteca), `jobs` (progresso, cancelar, um por vez).
- **JS** (Node, só para desenvolvimento, `node --test`): fonte de pixels, identicon (determinístico, simétrico),
  matemática de âncoras/forma de onda, store.
- **Fumaça**: abrir a janela de verdade, navegar por todas as telas e tirar prints de cada uma; conferir que não há
  erro no console.
- **Manual**: fluxo completo (buscar → baixar → biblioteca → sincronia → prévia do guia) na janela nova.

## Fora de escopo
- Temas múltiplos (decisão do usuário).
- Reproduzir a música inteira como player do Encore. O mini player serve para conferência.
