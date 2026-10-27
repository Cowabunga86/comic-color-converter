# Histórico de versões

## Não lançado

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
