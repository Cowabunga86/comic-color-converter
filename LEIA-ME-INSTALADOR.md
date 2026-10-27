# Gerando o instalador (.dmg) do Comic Color Converter

Este guia é para quem quer **gerar** o instalador a partir do código. Quem só vai
usar o app encontra as instruções em `assets/COMO-INSTALAR.txt`, que o script
copia para dentro do `.dmg`.

## O que há no projeto para o instalador

- `build_installer.sh` — o script que gera o `.app` e o `.dmg`.
- `build_installer.command` — o mesmo script, para abrir com duplo clique no
  Finder. Se o macOS recusar por "desenvolvedor não identificado" na primeira
  vez, use botão direito → Abrir → Abrir.
- `Comic Color Converter.spec` — configuração do PyInstaller.
- `build_assets/` — ícone do app (`icon.icns` e o `icon.iconset` de onde ele sai).
- `assets/icon_1024.png` — o logo do cabeçalho do app (grid 2×2 de quadrados
  amarelo, laranja, rosa e azul sobre o fundo escuro), ampliado para formato de
  ícone. Para trocar, substitua o arquivo mantendo o nome.
- `assets/COMO-INSTALAR.txt` — instruções para o usuário final, incluídas no
  `.dmg` ao lado do app.
- `assets/7zz` — o 7-Zip para macOS, embutido no app para converter CBR sem
  exigir Homebrew. **Este arquivo não está no repositório**: veja o passo 1.

Mudanças no código que tornam o empacotamento possível:

- `converter.py` reconhece o 7-Zip pelo nome `7zz` (o Homebrew instala assim, não
  como `7z`), inclusive em `/opt/homebrew/bin` e `/usr/local/bin`.
- `app.py` acha os `templates` e grava o `settings.json` corretamente quando roda
  de dentro de um `.app` (as preferências ficam em
  `~/Library/Application Support/Comic Color Converter`).
- O seletor de pasta no macOS usa `osascript`, porque o tkinter derrubava o
  processo fora da thread principal.

## Passo a passo

1. **Obtenha o `7zz` e coloque em `assets/7zz`.** O arquivo não é versionado
   porque é um binário de terceiros.
   - Baixe o 7-Zip para macOS em <https://www.7-zip.org/download.html> (pacote
     "mac", `7zz`) e extraia o executável `7zz` para dentro de `assets/`; ou
   - se você já tem o 7-Zip pelo Homebrew (`brew install sevenzip`), copie-o:
     ```
     cp "$(which 7zz)" assets/7zz
     ```
   Depois, garanta que ele é executável:
   ```
   chmod +x assets/7zz
   ```
   Sem esse arquivo o build ainda roda, mas o app empacotado só converte CBR em
   máquinas que já tenham o 7-Zip instalado. O binário oficial é universal
   (Apple Silicon e Intel).

2. **Rode o build.** O script cria o `venv` se não existir e instala sozinho as
   dependências de `requirements.txt` e o PyInstaller.
   ```
   chmod +x build_installer.sh
   ./build_installer.sh
   ```
   Para o app empacotado aceitar `.cb7`, o `py7zr` precisa estar no `venv`
   **antes** do build (`source venv/bin/activate && pip install py7zr`); ele não
   está em `requirements.txt`.

3. Aguarde. O PyInstaller demora alguns minutos na primeira vez. No final
   aparece:
   ```
   ✓ Pronto!
     App:  dist/Comic Color Converter.app
     DMG:  dist/Comic Color Converter.dmg
   ```

4. `dist/Comic Color Converter.dmg` é o instalador. Quem abrir vê a janela padrão
   do macOS com o ícone do app e um atalho para Applications: é só arrastar um
   para o outro. As pastas `build/` e `dist/` não vão para o git.

## Sobre o aviso de "desenvolvedor não identificado"

O app não é assinado com certificado pago da Apple (US$99/ano, com notarização).
Por isso, na primeira vez que alguém abrir o app, o macOS bloqueia com um aviso.
A solução é feita uma vez por máquina:

1. Clique com o **botão direito** no app → **Abrir**.
2. Na janela de aviso, clique em **Abrir** de novo.

Depois disso o app abre normalmente com duplo clique.

## Refazer o build depois de alterar o código

Rode `./build_installer.sh` de novo: ele apaga `build/` e `dist/` e gera tudo do
zero. Se você editar `templates/index.html`, é preciso refazer o build, porque o
app empacotado não recarrega o layout como o `python app.py`.

## Limitações

- O app fica pesado (o PyInstaller embute Python, PyMuPDF, numpy etc.): entre
  150 e 300 MB é normal.
- O script remove e regenera `Comic Color Converter.spec` a cada build. Se o
  `git status` mostrar esse arquivo modificado depois, confira o diff antes de
  comitar.
