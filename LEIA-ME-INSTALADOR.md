# Gerando o instalador (.dmg) do Comic Color Converter

## O que veio nesta pasta

- `app.py` e `converter.py` — versões corrigidas dos originais. Substitua os
  seus por estes (mesma pasta do projeto). Duas mudanças:
  1. **Bug corrigido**: o conversor só procurava o 7-Zip com o nome `7z`, mas
     o Homebrew instala como `7zz`. CBR provavelmente não estava convertendo
     na sua máquina por causa disso — agora ele acha os dois nomes.
  2. O app agora sabe salvar as preferências e achar os templates mesmo
     rodando de dentro de um `.app` empacotado (fora do modo terminal).
- `build_installer.sh` — o script que gera o `.app` e o `.dmg`.
- `build_installer.command` — o mesmo script, só que dá pra abrir com
  duplo clique no Finder (ele já roda como executável). Se o macOS ainda
  assim recusar por "desenvolvedor não identificado" na primeira vez, é o
  mesmo jeito de sempre: botão direito → Abrir → Abrir.
- `assets/7zz` — o 7-Zip oficial para macOS, embutido no instalador. Assim
  quem receber o app não precisa instalar Homebrew nem nada para converter CBR.
- `assets/icon_1024.png` — o mesmo logo do cabeçalho do app: o grid 2×2 de
  quadrados (amarelo, laranja, rosa, azul) sobre o fundo escuro do programa,
  só que ampliado para o formato de ícone. Cores e proporções idênticas às
  do CSS em `templates/index.html`. Se quiser trocar, é só substituir esse
  arquivo (mantendo o nome).
- `assets/COMO-INSTALAR.txt` — documento para quem for **usar** o app (não
  confundir com este aqui, que é para você gerar o instalador). Explica em
  passos simples como instalar e liberar o aviso de "desenvolvedor não
  identificado". O script já copia esse arquivo para dentro do `.dmg`
  automaticamente, do lado do app.

## Passo a passo

1. Copie `app.py`, `converter.py`, `build_installer.sh` e a pasta `assets/`
   para dentro de `/Users/renatopedreira/Desktop/Projetos/comic-color-converter-main`
   (substituindo os arquivos existentes).

2. No Terminal:
   ```
   cd /Users/renatopedreira/Desktop/Projetos/comic-color-converter-main
   chmod +x build_installer.sh
   ./build_installer.sh
   ```

3. Aguarde — o PyInstaller demora alguns minutos na primeira vez. No final
   aparece:
   ```
   ✓ Pronto!
     App:  dist/Comic Color Converter.app
     DMG:  dist/Comic Color Converter.dmg
   ```

4. O arquivo `dist/Comic Color Converter.dmg` é o instalador. Dá pra copiar
   para qualquer Mac (Apple Silicon ou Intel — o binário do 7-Zip embutido é
   universal). Quem abrir o `.dmg` vê a janela padrão do macOS com o ícone do
   app e um atalho para a pasta Applications — é só arrastar um para o outro.

## Sobre o aviso de "desenvolvedor não identificado"

Este app não está assinado com um certificado pago da Apple (isso custa
US$99/ano e exige notarização). Por isso, na primeira vez que alguém abrir o
app, o macOS vai bloquear com um aviso. A solução é simples e só precisa ser
feita uma vez por pessoa/máquina:

1. Clique com o **botão direito** no app → **Abrir**.
2. Na janela de aviso, clique em **Abrir** de novo.

Depois disso, o app abre normalmente com duplo clique, para sempre.

## Se quiser refazer o build depois de alterar o código

Basta rodar `./build_installer.sh` de novo — ele limpa o build anterior
(`build/`, `dist/`) e gera tudo do zero.

## Limitações que vale saber

- O app fica bem pesado (o PyInstaller embute o Python inteiro, o PyMuPDF,
  numpy etc.) — normal ficar entre 150–300 MB.
- `py7zr` (suporte a `.cb7`) só entra no app empacotado se estiver instalado
  no `venv` **antes** de rodar o build (`pip install py7zr`).
- Se você editar `templates/index.html`, precisa rodar o build de novo — o
  app empacotado não vê mudanças ao vivo como no modo `python app.py`.
