# Histórico de versões

## 1.3.1 — 31/10/2026

Une a versão 1.3.0 (instalador para macOS) com os ajustes que já faziam o `.exe`
portátil funcionar no Windows. O mesmo código agora empacota certo nos dois sistemas.

### Windows

- Novo `build_windows.bat`: gera `dist\ComicColorConverter.exe` (arquivo único, sem
  precisar de Python na máquina de destino), já com suporte a CB7 e ícone
- No `.exe`, o `settings.json` fica ao lado do executável (portátil); se a pasta não
  aceitar gravação, vai para `%APPDATA%\Comic Color Converter`. Antes, a 1.3.0
  empacotada no Windows gravava num caminho de Mac (`~/Library/Application Support`)
- O `7z.exe`/`unrar.exe` colocado ao lado do `.exe` volta a ser encontrado (a 1.3.0
  procurava só na pasta temporária do PyInstaller)
- O console do `.exe` usa UTF-8, então o aviso de abertura não derruba mais o programa
  em Windows com codepage cp1252

### EPUB

- O `META-INF/container.xml` usava um namespace inválido
  (`urn:oasis:schemas:container`); agora usa o oficial
  (`urn:oasis:names:tc:opendocument:xmlns:container`). Os EPUBs gerados passam no
  EPUBCheck sem erros

### macOS

- Sem mudança de comportamento: o `7zz` embutido no `.app` continua sendo achado, e
  as preferências seguem em `~/Library/Application Support/Comic Color Converter`

## 1.3.0 — 26/10/2026

### Correções

- EPUBs de mesmo nome (`Vol 1.cbz` e `Vol 1.pdf`) não se sobrescrevem mais: a
  extensão entra no nome do arquivo quando há conflito
- O EPUB agora inclui o documento de navegação (`nav.xhtml`) e `dcterms:modified`,
  exigidos pelo EPUB 3
- O idioma lido do ComicInfo é escapado no OPF
- CB7 é lido página a página, sem carregar o volume inteiro na memória
- O navegador só abre depois que o servidor sobe; se a porta já estiver em uso, o
  app abre a instância existente

### Instalador para macOS

- `build_installer.sh` (e `.command`) gera o `.app` e o `.dmg` com PyInstaller
- O seletor de pasta no macOS passa a usar `osascript`; o tkinter derrubava o processo
- Dentro do `.app`, os `templates` são lidos de `_MEIPASS` e o `settings.json` fica em
  `~/Library/Application Support/Comic Color Converter`
- O conversor reconhece o `7zz` (nome do 7-Zip no Homebrew) para abrir CB7/CBR

## 1.2.0 — 26/08/2026

Dois recursos que fecham lacunas conhecidas do motor.

### Metadados do ComicInfo.xml

O conversor agora lê o `ComicInfo.xml` de dentro do CBZ, CBR e CB7, quando existe.

- O título do EPUB passa a ser `Série #Número — Título` em vez do nome do arquivo
- Autor, ano, idioma e sinopse vão para o OPF
- A série é declarada como coleção (`belongs-to-collection` e `calibre:series`),
  que é o que faz o leitor agrupar os volumes em vez de espalhá-los
- `Manga: YesAndRightToLeft` liga a leitura da direita para a esquerda sozinho

Sem `ComicInfo.xml`, o nome do arquivo continua valendo. Dá para desligar a leitura
nos parâmetros.

### Aparar margens (opcional, desligado por padrão)

Corta a moldura uniforme em volta da arte — margem branca de scan ou tarja preta —
para a página ocupar a tela inteira.

A detecção é conservadora de propósito, com três travas: a cor de fundo precisa ser
quase branca ou quase preta, os quatro cantos precisam concordar entre si, e o corte
precisa preservar pelo menos metade de cada dimensão. Splash pages sangradas, páginas
escuras e fundos texturizados passam intactos.

## 1.1.0 — 26/08/2026

Projeto renomeado para **Comic Color Converter**, deixando as marcas de terceiros
apenas na descrição de compatibilidade, e não no nome do produto.

Revisão completa do código, com todas as correções verificadas contra o caso que falhava.

### Correções

- **Nomes de arquivo com `&` ou `<` geravam EPUB inválido.** O título ia direto para o OPF sem escape, quebrando o XML — comum em títulos como "Batman & Robin".
- **Uma falha durante a gravação destruía o EPUB anterior.** A escrita agora é atômica: grava em `.parcial` e só substitui o destino no final.
- **JPEGs truncados eram descartados.** Comuns em scans; agora são aproveitados via `LOAD_TRUNCATED_IMAGES`.
- **Resíduos de empacotamento contavam como páginas.** `__MACOSX/._*`, `Thumbs.db` e `.DS_Store` agora são filtrados.
- **O livro inteiro ficava em memória** antes de ser gravado. Agora é escrito página a página, com o OPF por último.
- **PDFs eram comprimidos em JPEG duas vezes.** O intermediário passou a ser PNG, sem perdas.
- **Dois cliques rápidos no seletor de pasta** podiam travar o processo (dois roots do tkinter simultâneos).
- **O histórico de jobs crescia sem limite.** Mantém os 20 mais recentes.
- **Qualquer site aberto no navegador podia chamar a API local.** Bloqueado por verificação de origem e host.
- **`/api/thumb` lia qualquer arquivo do disco.** Restrito a `.epub`.

## 1.0.0 — 26/08/2026

Primeira versão com motor de conversão próprio, substituindo a dependência do KCC.

- Conversão para EPUB 3 *pre-paginated* nos perfis Kindle e Kobo
- Capa declarada como `cover-image`, para o Kindle gerar a miniatura na biblioteca
- Detecção e divisão de páginas duplas, com modo mangá
- Suporte a CBZ, CBR (7-Zip ou unrar), CB7 (py7zr) e PDF (PyMuPDF)
- Interface web com conversão em lote e progresso em tempo real
- Seletor de pasta nativo, miniaturas das capas e modo galeria
- Memória da última pasta e das preferências
