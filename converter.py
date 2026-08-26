"""
Comic Color Converter — motor de conversão próprio para e-readers
Formatos de entrada : CBZ, PDF, CBR (requer rarfile+unrar), CB7 (requer py7zr)
Formato de saída    : EPUB 3 (pre-paginated, compatível com Kindle)
"""
from __future__ import annotations

import html
import io
import os
import re
import zipfile
from pathlib import Path
from typing import Iterator
from uuid import uuid4

VERSION = '1.1.0'

# ── Dependências opcionais ────────────────────────────────────────────────────
try:
    from PIL import Image, ImageFile
    # Scans de quadrinhos costumam ter JPEGs levemente truncados — sem isso
    # a página inteira seria descartada em vez de aproveitada.
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import pymupdf
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

import shutil as _shutil
import subprocess as _subprocess
import tempfile as _tempfile


def _find_unrar() -> str | None:
    """Procura o unrar na pasta do programa, no WinRAR instalado ou no PATH."""
    here = Path(__file__).parent
    for name in ('unrar.exe', 'UnRAR.exe', 'unrar'):
        p = here / name
        if p.is_file():
            return str(p)

    # WinRAR instalado no Windows já traz o UnRAR.exe
    for p_str in (r'C:\Program Files\WinRAR\UnRAR.exe',
                  r'C:\Program Files (x86)\WinRAR\UnRAR.exe'):
        if Path(p_str).is_file():
            return p_str

    return _shutil.which('unrar') or _shutil.which('unrar.exe')


def _find_7z() -> str | None:
    """Procura o 7-Zip na pasta do programa, nos caminhos padrão do Windows ou no PATH."""
    here = Path(__file__).parent
    for name in ('7z.exe', '7z'):
        p = here / name
        if p.is_file():
            return str(p)
    for p_str in (r'C:\Program Files\7-Zip\7z.exe',
                  r'C:\Program Files (x86)\7-Zip\7z.exe'):
        if Path(p_str).is_file():
            return p_str
    return _shutil.which('7z') or _shutil.which('7z.exe')


UNRAR_PATH = _find_unrar()
SEVENZIP_PATH = _find_7z()

try:
    import rarfile

    # O unrar é a única ferramenta que fala a sintaxe esperada por UNRAR_TOOL.
    # O 7-Zip usa sintaxe própria — configurá-lo aqui gera dados corrompidos.
    if UNRAR_PATH:
        rarfile.UNRAR_TOOL = UNRAR_PATH
    if SEVENZIP_PATH and hasattr(rarfile, 'SEVENZIP_TOOL'):
        rarfile.SEVENZIP_TOOL = SEVENZIP_PATH

    RAR_OK = True
except ImportError:
    RAR_OK = False

try:
    import py7zr
    SEVENZ_OK = True
except ImportError:
    SEVENZ_OK = False


# ── Perfis de dispositivo ─────────────────────────────────────────────────────
PROFILES: dict[str, dict] = {
    'KCC':  {'name': 'Kindle Colorsoft',         'width': 1264, 'height': 1680},
    'K11':  {'name': 'Kindle 11ª geração',       'width': 1072, 'height': 1448},
    'KPW5': {'name': 'Kindle Paperwhite 5',      'width': 1236, 'height': 1648},
    'KV':   {'name': 'Kindle Voyage / Oasis',    'width': 1072, 'height': 1448},
    'KoMT': {'name': 'Kobo Mini / Touch',        'width': 600,  'height': 800},
    'KoH':  {'name': 'Kobo HD / Glo HD',         'width': 1080, 'height': 1429},
}

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}


# ── Extração de imagens ───────────────────────────────────────────────────────

def _natural_key(s: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]


_JUNK_BASENAMES = {'thumbs.db', '.ds_store', 'desktop.ini'}


def _is_junk(name: str) -> bool:
    """
    Descarta lixo de empacotamento que se disfarça de imagem:
    resource forks do macOS (__MACOSX/._pagina.jpg), miniaturas do Windows, etc.
    """
    parts = name.replace('\\', '/').split('/')
    if '__MACOSX' in parts:
        return True
    base = parts[-1]
    return base.startswith('._') or base.lower() in _JUNK_BASENAMES


def _is_image(name: str) -> bool:
    if _is_junk(name):
        return False
    return Path(name).suffix.lower() in IMAGE_EXTS


def _extract_cbz(path: Path) -> Iterator[tuple[str, bytes]]:
    with zipfile.ZipFile(path) as zf:
        names = sorted([n for n in zf.namelist() if _is_image(n)], key=_natural_key)
        for name in names:
            yield name, zf.read(name)


def _extract_pdf(path: Path, dpi: int = 150) -> Iterator[tuple[str, bytes]]:
    if not PYMUPDF_OK:
        raise RuntimeError('PyMuPDF não instalado: pip install PyMuPDF')
    doc = pymupdf.open(str(path))
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    try:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat, colorspace=pymupdf.csRGB)
            # PNG (sem perdas) aqui — o JPEG é aplicado uma única vez no final,
            # evitando comprimir duas vezes e degradar a imagem à toa.
            yield f'page_{i+1:04d}.png', pix.tobytes('png')
    finally:
        doc.close()


def _extract_cbr_7z(path: Path) -> Iterator[tuple[str, bytes]]:
    """Extrai o CBR chamando o 7-Zip diretamente (sintaxe própria dele)."""
    if not SEVENZIP_PATH:
        raise RuntimeError('7-Zip não encontrado')

    with _tempfile.TemporaryDirectory(prefix='cbr_') as tmp:
        proc = _subprocess.run(
            [SEVENZIP_PATH, 'x', str(path), f'-o{tmp}', '-y', '-bso0', '-bsp0'],
            stdout=_subprocess.PIPE,
            stderr=_subprocess.PIPE,
            creationflags=getattr(_subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if proc.returncode != 0:
            err = proc.stderr.decode('utf-8', 'replace').strip() or 'erro desconhecido'
            raise RuntimeError(f'7-Zip falhou: {err}')

        files = [p for p in Path(tmp).rglob('*')
                 if p.is_file() and _is_image(str(p.relative_to(tmp)))]
        files.sort(key=lambda p: _natural_key(str(p.relative_to(tmp))))
        if not files:
            raise RuntimeError('Nenhuma imagem encontrada dentro do CBR')
        for p in files:
            yield p.name, p.read_bytes()


def _extract_cbr_unrar(path: Path) -> Iterator[tuple[str, bytes]]:
    """Extrai o CBR via rarfile + unrar oficial."""
    if not (RAR_OK and UNRAR_PATH):
        raise RuntimeError('unrar não encontrado')
    with rarfile.RarFile(path) as rf:
        names = sorted([n for n in rf.namelist() if _is_image(n)], key=_natural_key)
        if not names:
            raise RuntimeError('Nenhuma imagem encontrada dentro do CBR')
        for name in names:
            yield name, rf.read(name)


def _extract_cbr(path: Path) -> Iterator[tuple[str, bytes]]:
    """
    Extrai um CBR. Tenta o 7-Zip primeiro; se não houver 7-Zip
    (ou se ele falhar), tenta o unrar via rarfile.
    """
    tried: list[str] = []

    # Caminho 1 — 7-Zip
    if SEVENZIP_PATH:
        try:
            yield from _extract_cbr_7z(path)
            return
        except Exception as e:
            tried.append(f'7-Zip: {e}')

    # Caminho 2 — unrar via rarfile
    if RAR_OK and UNRAR_PATH:
        try:
            yield from _extract_cbr_unrar(path)
            return
        except Exception as e:
            tried.append(f'unrar: {e}')

    if tried:
        raise RuntimeError('Falha ao abrir o CBR — ' + ' | '.join(tried))

    raise RuntimeError(
        'Nenhum extrator de RAR encontrado. Instale o 7-Zip (7-zip.org) '
        'ou coloque o unrar.exe na pasta do programa (rarlab.com).'
    )


def _extract_cb7(path: Path) -> Iterator[tuple[str, bytes]]:
    if not SEVENZ_OK:
        raise RuntimeError('Suporte CB7 requer: pip install py7zr')
    with py7zr.SevenZipFile(path, mode='r') as z:
        names = sorted([n for n in z.getnames() if _is_image(n)], key=_natural_key)
        data = z.read(names)
        for name in names:
            yield name, data[name].read()


def extract_images(path: Path) -> Iterator[tuple[str, bytes]]:
    ext = path.suffix.lower()
    if ext in ('.cbz', '.zip'):
        yield from _extract_cbz(path)
    elif ext == '.pdf':
        yield from _extract_pdf(path)
    elif ext == '.cbr':
        yield from _extract_cbr(path)
    elif ext in ('.cb7', '.7z'):
        yield from _extract_cb7(path)
    else:
        raise ValueError(f'Formato não suportado: {ext}')


# ── Processamento de imagem ───────────────────────────────────────────────────

def _resize_to_fit(img: 'Image.Image', max_w: int, max_h: int) -> 'Image.Image':
    """Redimensiona para caber em max_w×max_h, podendo ampliar até 2×."""
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    scale = min(scale, 2.0)   # não ampliar mais que 2× para não perder qualidade
    if abs(scale - 1.0) > 0.01:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def _is_spread(img: 'Image.Image') -> bool:
    w, h = img.size
    return w > h * 1.2   # margem para não quebrar imagens quase quadradas


def _split_spread(img: 'Image.Image', manga: bool) -> tuple['Image.Image', 'Image.Image']:
    """
    Divide página dupla em dois retratos.
    manga=True  → direita primeiro (RTL)
    manga=False → esquerda primeiro (LTR)
    """
    w, h = img.size
    mid = w // 2
    left  = img.crop((0,   0, mid, h))
    right = img.crop((mid, 0, w,   h))
    return (right, left) if manga else (left, right)


def _to_jpeg(img: 'Image.Image', quality: int) -> tuple[bytes, int, int]:
    img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=quality, optimize=True, progressive=True)
    return buf.getvalue(), img.width, img.height


def process_image(raw: bytes, profile: dict, params: dict) -> list[tuple[bytes, int, int]]:
    """
    Retorna lista de (jpeg_bytes, width, height).
    Pode retornar 2 tuplas se for spread e spread_shift=True.
    """
    img = Image.open(io.BytesIO(raw)).convert('RGB')
    max_w = profile['width']
    max_h = profile['height']
    try:
        quality = int(params.get('quality') or 90)
    except (TypeError, ValueError):
        quality = 90
    quality = max(40, min(100, quality))
    spread_shift = params.get('spread_shift', True)
    manga        = params.get('manga', False)

    if spread_shift and _is_spread(img):
        p1, p2 = _split_spread(img, manga)
        results = []
        for p in (p1, p2):
            p = _resize_to_fit(p, max_w, max_h)
            results.append(_to_jpeg(p, quality))
        return results

    img = _resize_to_fit(img, max_w, max_h)
    return [_to_jpeg(img, quality)]


# ── Construção do EPUB ────────────────────────────────────────────────────────

class EmptyBookError(RuntimeError):
    """Nenhuma página aproveitável no arquivo de origem."""



_CONTAINER = '''\
<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:schemas:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''


def _build_opf(title: str, uid: str, n: int, manga: bool) -> str:
    direction = 'rtl' if manga else 'ltr'
    # Nomes de quadrinhos costumam trazer & e < — sem escape o OPF vira XML inválido
    title = html.escape(title, quote=False)
    # Primeira imagem é a capa (cover-image) — necessário para o Kindle gerar thumbnail
    manifest_img   = (
        '<item id="img0000" href="Images/page0000.jpg" media-type="image/jpeg" properties="cover-image"/>\n    '
        + '\n    '.join(
            f'<item id="img{i:04d}" href="Images/page{i:04d}.jpg" media-type="image/jpeg"/>'
            for i in range(1, n))
    ) if n > 0 else ''
    manifest_xhtml = '\n    '.join(
        f'<item id="pg{i:04d}" href="Text/page{i:04d}.xhtml" media-type="application/xhtml+xml"/>'
        for i in range(n))
    spine = '\n    '.join(f'<itemref idref="pg{i:04d}"/>' for i in range(n))
    return f'''\
<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf"
         unique-identifier="BookId" dir="{direction}">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{uid}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>{'ja' if manga else 'pt'}</dc:language>
    <meta name="cover" content="img0000"/>
    <meta property="rendition:layout">pre-paginated</meta>
    <meta property="rendition:orientation">auto</meta>
    <meta property="rendition:spread">auto</meta>
  </metadata>
  <manifest>
    {manifest_img}
    {manifest_xhtml}
  </manifest>
  <spine page-progression-direction="{direction}">
    {spine}
  </spine>
</package>'''


def _build_xhtml(idx: int, vp_w: int, vp_h: int) -> str:
    return f'''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Página {idx + 1}</title>
  <meta name="viewport" content="width={vp_w}, height={vp_h}"/>
  <style>
    html, body {{ margin: 0; padding: 0; width: {vp_w}px; height: {vp_h}px;
                  overflow: hidden; background: #000; }}
    img {{ display: block; width: {vp_w}px; height: {vp_h}px;
           object-fit: contain; }}
  </style>
</head>
<body>
  <img src="../Images/page{idx:04d}.jpg" alt="Página {idx + 1}"/>
</body>
</html>'''


def build_epub(pages: Iterator[tuple[bytes, int, int]], title: str,
               out_path: Path, profile: dict, manga: bool) -> int:
    """
    Grava o EPUB consumindo as páginas uma a uma (sem acumular o livro na memória).

    A escrita vai para um arquivo temporário e só substitui o destino no final,
    então uma falha no meio do caminho nunca deixa um EPUB truncado no lugar
    de um arquivo bom. Devolve o número de páginas gravadas.
    """
    vp_w = profile['width']
    vp_h = profile['height']
    uid  = str(uuid4())
    tmp_path = out_path.parent / (out_path.name + '.parcial')
    n = 0

    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as epub:
            # mimetype — obrigatório ser o primeiro e não-comprimido
            epub.writestr(
                zipfile.ZipInfo('mimetype'),
                'application/epub+zip',
                compress_type=zipfile.ZIP_STORED,
            )
            epub.writestr('META-INF/container.xml', _CONTAINER)

            for jpeg, img_w, img_h in pages:
                epub.writestr(
                    f'OEBPS/Images/page{n:04d}.jpg', jpeg,
                    compress_type=zipfile.ZIP_STORED,   # JPEG já é comprimido
                )
                epub.writestr(f'OEBPS/Text/page{n:04d}.xhtml',
                              _build_xhtml(n, vp_w, vp_h))
                n += 1

            if n == 0:
                raise EmptyBookError('Nenhuma imagem válida encontrada no arquivo')

            # o OPF vai por último porque só agora sabemos o total de páginas
            epub.writestr('OEBPS/content.opf', _build_opf(title, uid, n, manga))

        os.replace(tmp_path, out_path)      # substituição atômica
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise

    return n


# ── Ponto de entrada ──────────────────────────────────────────────────────────

class ExtractError(RuntimeError):
    """Falha ao ler o arquivo de origem (formato, ferramenta ausente, corrupção)."""


def _page_stream(src: Path, profile: dict, params: dict,
                 stats: dict) -> Iterator[tuple[bytes, int, int]]:
    """Produz as páginas processadas uma a uma, contando as que falharem."""
    it = extract_images(src)
    while True:
        try:
            name, raw = next(it)
        except StopIteration:
            return
        except Exception as e:
            raise ExtractError(str(e)) from e
        try:
            yield from process_image(raw, profile, params)
        except Exception:
            stats['errors'] += 1   # imagem corrompida — pular e continuar


def convert(fp: str, output_dir: str, params: dict) -> dict:
    """
    Converte um arquivo de quadrinho para EPUB.
    Retorna {'ok': bool, 'msg': str, 'epub': str}.
    """
    if not PIL_OK:
        return {'ok': False, 'msg': 'Pillow não instalado: pip install Pillow'}

    src = Path(fp)
    profile_id = params.get('profile', 'KCC')
    profile    = PROFILES.get(profile_id, PROFILES['KCC'])
    manga      = bool(params.get('manga', False))

    out_dir  = Path(output_dir) if output_dir and os.path.isdir(output_dir) else src.parent
    out_path = out_dir / (src.stem + '.epub')

    stats = {'errors': 0}
    try:
        pages = _page_stream(src, profile, params, stats)
        n = build_epub(pages, src.stem, out_path, profile, manga)
    except (ExtractError, EmptyBookError) as e:
        return {'ok': False, 'msg': str(e)}
    except Exception as e:
        return {'ok': False, 'msg': f'Erro ao gerar EPUB: {e}'}

    msg = f'EPUB gerado — {n} páginas'
    if stats['errors']:
        msg += f' ({stats["errors"]} imagem(ns) ignorada(s))'
    return {'ok': True, 'msg': msg, 'epub': str(out_path.resolve())}
