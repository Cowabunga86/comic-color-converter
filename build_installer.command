#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Gera o Comic Color Converter.app e um instalador .dmg pronto para arrastar
# para /Applications — sem precisar de Python instalado na máquina de destino.
#
# Rode este script DENTRO da pasta do projeto (onde ficam app.py, converter.py,
# templates/ etc.), com o venv já criado. Ele mesmo ativa o venv.
#
# Uso:
#   chmod +x build_installer.sh
#   ./build_installer.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_NAME="Comic Color Converter"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "→ Pasta do projeto: $HERE"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "✗ Este script precisa rodar no macOS (é onde o .app é gerado)."
  exit 1
fi

if [[ ! -f "app.py" || ! -d "templates" ]]; then
  echo "✗ Não encontrei app.py / templates/ nesta pasta."
  echo "  Coloque este script na raiz do projeto (junto com app.py) e rode de novo."
  exit 1
fi

if [[ ! -d "venv" ]]; then
  echo "→ venv não encontrado, criando..."
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "→ Garantindo dependências do projeto instaladas..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "→ Instalando PyInstaller (se ainda não estiver no venv)..."
pip install --quiet --upgrade pyinstaller

# ── Ícone ───────────────────────────────────────────────────────────────────
ICON_PNG="assets/icon_1024.png"
ICNS_PATH="build_assets/icon.icns"
mkdir -p build_assets

if [[ -f "$ICON_PNG" ]]; then
  echo "→ Gerando ícone .icns..."
  ICONSET="build_assets/icon.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  sips -z 16 16     "$ICON_PNG" --out "$ICONSET/icon_16x16.png"      >/dev/null
  sips -z 32 32     "$ICON_PNG" --out "$ICONSET/icon_16x16@2x.png"   >/dev/null
  sips -z 32 32     "$ICON_PNG" --out "$ICONSET/icon_32x32.png"      >/dev/null
  sips -z 64 64     "$ICON_PNG" --out "$ICONSET/icon_32x32@2x.png"   >/dev/null
  sips -z 128 128   "$ICON_PNG" --out "$ICONSET/icon_128x128.png"    >/dev/null
  sips -z 256 256   "$ICON_PNG" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$ICON_PNG" --out "$ICONSET/icon_256x256.png"    >/dev/null
  sips -z 512 512   "$ICON_PNG" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$ICON_PNG" --out "$ICONSET/icon_512x512.png"    >/dev/null
  cp "$ICON_PNG" "$ICONSET/icon_512x512@2x.png"
  iconutil -c icns "$ICONSET" -o "$ICNS_PATH"
else
  echo "  (sem ícone customizado — usando o padrão do PyInstaller)"
  ICNS_PATH=""
fi

# ── 7-Zip embutido (para CBR funcionar sem depender do Homebrew) ────────────
SEVENZIP_BIN="assets/7zz"
if [[ ! -f "$SEVENZIP_BIN" ]]; then
  echo "✗ Não achei assets/7zz — o app ainda funciona para CBZ/PDF, mas CBR"
  echo "  só vai funcionar em máquinas que já tenham 7-Zip instalado."
fi

# ── Build ─────────────────────────────────────────────────────────────────
echo "→ Rodando o PyInstaller (pode levar alguns minutos)..."
rm -rf build dist "${APP_NAME}.spec"

PYI_ARGS=(
  --name "$APP_NAME"
  --windowed
  --noconfirm
  --clean
  --add-data "templates:templates"
  --collect-all pymupdf
  --collect-all PIL
  --collect-all mozjpeg_lossless_optimization
  --collect-all cffi
  --hidden-import tkinter
  --hidden-import tkinter.filedialog
)

if [[ -n "$ICNS_PATH" && -f "$ICNS_PATH" ]]; then
  PYI_ARGS+=(--icon "$ICNS_PATH")
fi

if [[ -f "$SEVENZIP_BIN" ]]; then
  PYI_ARGS+=(--add-binary "$SEVENZIP_BIN:.")
fi

pyinstaller "${PYI_ARGS[@]}" app.py

APP_PATH="dist/${APP_NAME}.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "✗ PyInstaller não gerou o .app esperado em $APP_PATH"
  exit 1
fi

# ── Assinatura ad-hoc (evita "app está corrompido" no Apple Silicon) ───────
echo "→ Assinando o app (ad-hoc, sem certificado de desenvolvedor)..."
codesign --force --deep -s - "$APP_PATH"

# ── Empacotando o .dmg ───────────────────────────────────────────────────
echo "→ Montando o instalador .dmg..."
STAGE="dist/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP_PATH" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

if [[ -f "assets/COMO-INSTALAR.txt" ]]; then
  cp "assets/COMO-INSTALAR.txt" "$STAGE/Como instalar.txt"
fi

DMG_PATH="dist/${APP_NAME}.dmg"
rm -f "$DMG_PATH"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG_PATH"

echo ""
echo "✓ Pronto!"
echo "  App:  $APP_PATH"
echo "  DMG:  $DMG_PATH"
echo ""
echo "Para instalar em qualquer Mac: abrir o .dmg e arrastar o app para Applications."
echo "No primeiro uso, o macOS vai avisar que é de 'desenvolvedor não identificado'"
echo "(o app não está notarizado pela Apple) — basta clicar com o botão direito"
echo "no app, escolher 'Abrir' e confirmar uma vez. Depois disso abre normalmente."
