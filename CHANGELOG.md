# Histórico de versões

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
