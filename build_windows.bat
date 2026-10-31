@echo off
rem ---------------------------------------------------------------------------
rem Gera o ComicColorConverter.exe portatil para Windows (arquivo unico, roda
rem sem Python instalado na maquina de destino).
rem
rem Uso: de dois cliques neste arquivo, ou rode no Prompt de Comando dentro da
rem pasta do projeto. Precisa de Python 3.10+ instalado (python.org).
rem O resultado fica em dist\ComicColorConverter.exe
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"
set "HERE=%CD%"

if not exist "app.py" (
  echo [X] Nao encontrei app.py nesta pasta. Rode o script na raiz do projeto.
  goto :fim
)

set "PY=python"
where py >nul 2>nul && set "PY=py -3"

if not exist "venv\Scripts\python.exe" (
  echo -^> venv nao encontrado, criando...
  %PY% -m venv venv || goto :erro
)
set "VPY=venv\Scripts\python.exe"

echo -^> Instalando dependencias e PyInstaller...
"%VPY%" -m pip install --disable-pip-version-check --progress-bar on -r requirements.txt py7zr pyinstaller || goto :erro

set "ICON_ARG="
if exist "assets\icon_1024.png" set "ICON_ARG=--icon "%HERE%\assets\icon_1024.png""

echo -^> Rodando o PyInstaller (pode levar alguns minutos)...
if exist "build" rmdir /s /q "build"
if exist "dist\ComicColorConverter.exe" del /q "dist\ComicColorConverter.exe"

"%VPY%" -m PyInstaller --onefile --console --noconfirm --clean ^
  --name ComicColorConverter ^
  --specpath build ^
  --add-data "%HERE%\templates;templates" ^
  --collect-all pymupdf ^
  --collect-all PIL ^
  --collect-all mozjpeg_lossless_optimization ^
  --collect-all cffi ^
  --hidden-import tkinter ^
  --hidden-import tkinter.filedialog ^
  %ICON_ARG% ^
  app.py || goto :erro

if not exist "dist\ComicColorConverter.exe" goto :erro

echo.
echo [OK] Pronto: dist\ComicColorConverter.exe
echo.
echo O .exe e portatil: copie para qualquer pasta ou pendrive.
echo - As preferencias (settings.json) ficam ao lado do .exe; se a pasta nao
echo   aceitar gravacao, vao para %%APPDATA%%\Comic Color Converter.
echo - Para CBR: tenha o 7-Zip instalado, ou coloque 7z.exe + 7z.dll (ou
echo   unrar.exe) na mesma pasta do .exe.
goto :fim

:erro
echo.
echo [X] O build falhou. Veja as mensagens acima.

:fim
echo.
pause
endlocal
