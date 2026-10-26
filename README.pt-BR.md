<p align="center"><img src="encolibmg/webui/static/brand/wordmark.svg" alt="EncoLibMG" width="480"></p>

<p align="center"><b>Sua biblioteca de karaokê, afinada.</b><br>
Monta e organiza uma <code>EncoreLibrary</code> para o
<a href="https://github.com/Encore-Karaoke-Labs/Encore-Karaoke">Encore Karaoke</a>, aproveitando tudo que o player oferece.</p>

<p align="center"><a href="README.md">English</a> · <b>Português (Brasil)</b></p>

![Tela inicial do EncoLibMG](docs/screens/pt-BR/home.png)

## O que cada música ganha

| Arquivo | O que faz no Encore |
|---|---|
| `Artista - Música.multiplexed.mp3` | Instrumental no canal esquerdo e voz no direito. ◀/▶ liga e desliga a voz-guia. |
| `Artista - Música.lrc` | Letra sincronizada, no formato exato que o Encore lê. Romanização automática de japonês e coreano. |
| `Artista - Música.guide.mid` | **Guia MIDI**: notas da melodia (detectadas com o CREPE) e letra palavra a palavra. O guia de afinação, a pontuação e o realce da letra ficam precisos. No Encore, `M` → Guide toca a melodia. |
| `Artista - Música.mp4` (opcional) | Clipe oficial tocando mudo atrás da letra, sem perder a voz-guia. |

Sem letra sincronizada disponível, o EncoLibMG baixa um **vídeo de karaokê (MTV)**. Todas as faixas saem
com volume uniforme (−16 LUFS), sem comprimir a dinâmica.

## Instalar
1. Precisa de **Python 3.12** e **ffmpeg** (`winget install Gyan.FFmpeg`). O Windows 10/11 já traz o
   WebView2, que desenha a janela.
2. Dê dois cliques em `instalar.bat`. São ~3 GB por causa do PyTorch, do Demucs e dos modelos.
   Com placa NVIDIA, tudo roda na GPU.

## Usar
1. Dê dois cliques em `Abrir EncoLibMG.bat`.
2. No topo, clique no nome da biblioteca → **Abrir ou criar** (ou `Ctrl O`). Se a pasta ainda não for uma
   biblioteca, o app cria a `EncoreLibrary` com o `manifest.json`.
3. Na tela **Início**, digite `Artista - Música` e aperte `Enter`.
4. Escolha a versão da letra com ✓ e clique em **Baixar completa**. O app procura o áudio com a mesma duração
   da letra, separa a voz, monta o Multiplex e gera o guia MIDI.
5. No Encore, aponte o Setup (F2) para a pasta da biblioteca. O Encore também acha sozinho qualquer pasta
   chamada `EncoreLibrary` nos seus drives.

O app segue o idioma do Windows (português do Brasil ou inglês). Troque quando quiser no botão **PT/EN** do
topo, sem reiniciar.

## Telas

**Início**: o logo em pixels, a busca e os números da biblioteca.

**Adicionar**: os resultados de letra, com as 5 etapas do processo acendendo enquanto a música é preparada.
Para MTV e clipes, há um seletor com miniaturas do YouTube.

**Biblioteca**: filtros (Multiplex, com guia, sem guia, MTV, MIDI, invisíveis), seleção múltipla e um painel
por faixa. Pelo painel você ouve com instrumental/voz/ambos, abre a sincronia e a prévia do guia,
gera o guia, edita, adiciona clipe, converte para Multiplex ou remove.

![Biblioteca](docs/screens/pt-BR/library.png)

**Sincronia**: a onda da voz em pixels, com cada linha da letra marcada. Arraste a onda para ir e voltar.
- **Deslocar tudo:** ±1 s ou ±0,1 s.
- **Âncoras:** com a música tocando, aperte `Espaço` quando a linha selecionada começar a ser cantada.
  Com duas ou mais, a letra é esticada entre elas.
- **Sugerir:** acha sozinho onde a voz começa.
- Sempre fica backup, com **Desfazer**. Ao salvar, o app oferece regerar o guia.

**Prévia do guia**: o rolo de piano com as notas que o Encore vai usar e a letra acendendo palavra a palavra,
como no Encore.

**Verificar**: acha o que o Encore ignoraria ou mostraria errado e corrige com um clique. Cobre:
- áudio sem letra;
- faixa sem guia MIDI;
- letra fora do padrão;
- formatos não aceitos (FLAC, WMA, MOV…);
- arquivos em subpasta;
- manifest incompleto;
- tags faltando;
- volume (opcional).

![Verificar](docs/screens/pt-BR/check.png)

**Importar**: traz o que você já tem: CDs/FLAC, coleções CDG, `.zip` e karaokês `.kar`/`.mid` (título lido
de dentro do arquivo, inclusive em japonês). Antes de importar, você confere os nomes numa prévia editável.
O app pode gerar o Multiplex **a partir do seu arquivo**, com a qualidade da sua fonte.

**Visual e som**:
- **Vídeos de fundo** por categoria, do PC ou do YouTube. Do YouTube, só um trecho de até 5 minutos.
- **Imagens de espera** da tela entre músicas.
- **Vídeo de abertura** da biblioteca.
- **Narração da nota**: um áudio por faixa de pontuação.
- **SoundFont**: inclui o download do GeneralUser GS, gratuito.

**Configurar** (⚙ no topo): nome, descrição e opções da biblioteca no Encore.

### Atalhos
| Tecla | Ação |
|---|---|
| `/` | Buscar uma música |
| `1`–`6` | Início, Adicionar, Biblioteca, Verificar, Importar, Visual e som |
| `Espaço` | Tocar/pausar · na Sincronia: marcar âncora |
| `←` `→` | Voltar/avançar 5 s |
| `Esc` | Fechar janela, painel ou voltar |
| `Ctrl O` | Abrir ou criar biblioteca |
| `?` | Todos os atalhos |

Nada é apagado de verdade: o que sai vai para a Lixeira, e toda letra alterada ganha backup.

## Identidade
Marca **"Letra cantada"**: uma linha de karaokê no meio do preenchimento, entre colchetes de canto. A estética
é inspirada no [Omarchy](https://omarchy.org/), com desenho original. Tudo (marca, wordmark, ícone do Windows)
é gerado a partir de grades de pixels por [scripts/brand.py](scripts/brand.py). A página da identidade está em
[docs/brand/index.html](docs/brand/index.html).

## Desenvolvimento
```
.venv\Scripts\python -m pytest            # testes rápidos (inclui os de JS, se o Node estiver instalado)
.venv\Scripts\python -m pytest -m slow    # inclui Demucs e CREPE de verdade
.venv\Scripts\python -m pytest -m ui      # abre a janela de verdade e roda os fluxos principais
.venv\Scripts\python -m encolibmg --debug # abre a janela com as ferramentas de desenvolvedor
```
- **Estrutura:** motor em Python (`encolibmg/`); interface em `encolibmg/webui/` (pywebview + lit-html, sem
  etapa de build); efeitos de pixel em `encolibmg/webui/static/js/fx/`.
- **Traduções:** todos os textos ficam em `scripts/catalog_engine.py` (motor) e `scripts/catalog_ui.py`
  (interface) como `(chave, pt-BR, en)`. Rode `python scripts/i18n_build.py` para gerar `encolibmg/locales/`.
  Os testes falham se faltar uma chave, sobrar uma sem uso ou um idioma perder um `{parâmetro}`.
- **Prints da janela real:** `ENCOLIB_TEST_LIB=<biblioteca> ENCOLIB_LANG=pt-BR python scripts/snap_app.py <pasta> home library …`.
- **Documentação:** [roadmap](docs/roadmap.md) · [especificação da interface](docs/specs/2026-10-26-nova-ui-design.md).
- **Log:** `%APPDATA%\EncoLibMG\log.txt`.

## Licença
EncoLibMG é software livre sob a [GPL-3.0](LICENSE). As licenças dos componentes de terceiros estão em
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Atenção: o modelo de alinhamento MMS (Meta), baixado na
primeira geração de guia, é **CC BY-NC 4.0**, só para uso não comercial.

Uso pessoal. O conteúdo que você baixar é de sua responsabilidade.
