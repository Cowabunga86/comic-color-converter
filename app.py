"""
Comic Color Converter — backend local
Roda em http://localhost:5432
"""
from __future__ import annotations
from flask import Flask, render_template, jsonify, request, Response
import threading, os, json, uuid, queue, sys
from pathlib import Path

# ── Conversor próprio ──────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from converter import convert as _do_convert, PROFILES, VERSION as CONVERTER_VERSION

app = Flask(__name__)
# Recarrega o HTML a cada requisição — basta atualizar a página após editar o layout
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

SUPPORTED = {'.cbr', '.cbz', '.cb7', '.pdf'}
_jobs: dict = {}
_queues: dict = {}
_lock = threading.Lock()
_browse_lock = threading.Lock()   # o tkinter não aceita dois diálogos ao mesmo tempo
MAX_JOBS_KEPT = 20                # histórico de jobs mantido em memória


# ── Proteção do servidor local ─────────────────────────────────────────────────

@app.before_request
def _block_foreign_requests():
    """
    O servidor é local e de uso pessoal, mas qualquer site aberto no navegador
    consegue chamar http://localhost:5432/... Aqui recusamos o que não veio
    da nossa própria página (e o que não chegou por localhost).
    """
    site = request.headers.get('Sec-Fetch-Site')
    if site and site not in ('same-origin', 'none'):
        return jsonify({'error': 'Requisição externa bloqueada'}), 403

    host = (request.host or '').split(':')[0].lower()
    if host not in ('localhost', '127.0.0.1', '[::1]', '::1', ''):
        return jsonify({'error': 'Host não permitido'}), 403
    return None


# ── Preferências persistentes ──────────────────────────────────────────────────

SETTINGS_FILE = Path(__file__).parent / 'settings.json'
_DEFAULT_SETTINGS = {
    'src_path': '',
    'out_path': '',
    'view':     'list',
    'params':   {},
}


def _load_settings() -> dict:
    data = dict(_DEFAULT_SETTINGS)
    try:
        if SETTINGS_FILE.is_file():
            saved = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                data.update({k: v for k, v in saved.items() if k in _DEFAULT_SETTINGS})
    except Exception:
        pass          # arquivo corrompido — usa os padrões
    return data


def _save_settings(patch: dict) -> dict:
    data = _load_settings()
    data.update({k: v for k, v in patch.items() if k in _DEFAULT_SETTINGS})
    try:
        SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass          # sem permissão de escrita — segue sem persistir
    return data


@app.route('/api/settings', methods=['GET'])
def get_settings():
    s = _load_settings()
    # informa se a pasta lembrada ainda existe
    s['src_exists'] = bool(s['src_path']) and os.path.isdir(s['src_path'])
    return jsonify(s)


@app.route('/api/settings', methods=['POST'])
def set_settings():
    return jsonify(_save_settings(request.json or {}))


# ── Seletor de pasta nativo ────────────────────────────────────────────────────

@app.route('/api/browse')
def browse_folder():
    """Abre diálogo nativo de seleção de pasta via tkinter."""
    initial = request.args.get('initial', '').strip()

    # dois roots do tkinter ao mesmo tempo travam o processo
    if not _browse_lock.acquire(blocking=False):
        return jsonify({'error': 'Já existe um seletor de pasta aberto'}), 409

    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()                       # janela principal invisível
        root.wm_attributes('-topmost', True)  # diálogo aparece na frente
        kwargs = {'title': 'Selecionar pasta com quadrinhos'}
        if initial and os.path.isdir(initial):
            kwargs['initialdir'] = initial
        folder = filedialog.askdirectory(**kwargs)
        return jsonify({'path': folder or None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
        _browse_lock.release()


# ── Arquivos ───────────────────────────────────────────────────────────────────

def _find_epub(src: Path, out_dir: str) -> Path | None:
    """Procura o EPUB já convertido para este arquivo (pasta de saída ou de origem)."""
    candidates = []
    if out_dir and os.path.isdir(out_dir):
        candidates.append(Path(out_dir) / (src.stem + '.epub'))
    candidates.append(src.parent / (src.stem + '.epub'))
    for c in candidates:
        if c.is_file():
            return c
    return None


@app.route('/api/scan')
def scan():
    path    = request.args.get('path', '').strip()
    out_dir = request.args.get('out', '').strip()
    if not path or not os.path.isdir(path):
        return jsonify({'error': 'Diretório inválido ou não encontrado'}), 400
    try:
        files = []
        for f in sorted(Path(path).iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                epub = _find_epub(f, out_dir)
                files.append({
                    'name':      f.name,
                    'path':      str(f.resolve()),
                    'size':      f.stat().st_size,
                    'ext':       f.suffix.lower().lstrip('.'),
                    'converted': epub is not None,
                    'epub':      str(epub.resolve()) if epub else None,
                })
        # lembra a pasta para a próxima abertura
        _save_settings({'src_path': path, 'out_path': out_dir})
        return jsonify({'files': files, 'count': len(files)})
    except PermissionError:
        return jsonify({'error': 'Sem permissão para ler o diretório'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Capa do EPUB ───────────────────────────────────────────────────────────────

_thumb_cache: dict = {}
_THUMB_W = 220


def _cover_bytes(epub_path: Path) -> bytes | None:
    """Extrai a imagem de capa de um EPUB."""
    import zipfile, re as _re
    with zipfile.ZipFile(epub_path) as z:
        names = z.namelist()

        # 1. Layout gerado por nós
        if 'OEBPS/Images/page0000.jpg' in names:
            return z.read('OEBPS/Images/page0000.jpg')

        # 2. Procura o item marcado como cover-image no OPF
        opf_name = next((n for n in names if n.lower().endswith('.opf')), None)
        if opf_name:
            opf = z.read(opf_name).decode('utf-8', 'replace')
            m = _re.search(r'<item[^>]*properties="[^"]*cover-image[^"]*"[^>]*>', opf)
            if not m:
                mid = _re.search(r'<meta[^>]*name="cover"[^>]*content="([^"]+)"', opf)
                if mid:
                    m = _re.search(r'<item[^>]*id="%s"[^>]*>' % _re.escape(mid.group(1)), opf)
            if m:
                href = _re.search(r'href="([^"]+)"', m.group(0))
                if href:
                    base = opf_name.rsplit('/', 1)[0] if '/' in opf_name else ''
                    target = (base + '/' + href.group(1)) if base else href.group(1)
                    target = target.replace('//', '/')
                    for n in names:
                        if n == target or n.endswith('/' + href.group(1)):
                            return z.read(n)

        # 3. Primeira imagem do arquivo
        imgs = sorted(n for n in names
                      if n.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')))
        if imgs:
            return z.read(imgs[0])
    return None


@app.route('/api/thumb')
def thumb():
    """Serve a miniatura da capa de um EPUB já convertido."""
    p = request.args.get('path', '').strip()
    if not p or not p.lower().endswith('.epub'):
        return jsonify({'error': 'Apenas arquivos .epub'}), 400
    if not os.path.isfile(p):
        return jsonify({'error': 'Arquivo não encontrado'}), 404

    epub = Path(p)
    try:
        key = (str(epub.resolve()), epub.stat().st_mtime_ns)
    except OSError:
        return jsonify({'error': 'Arquivo inacessível'}), 404

    if key in _thumb_cache:
        return Response(_thumb_cache[key], mimetype='image/jpeg',
                        headers={'Cache-Control': 'private, max-age=300'})

    try:
        raw = _cover_bytes(epub)
        if not raw:
            return jsonify({'error': 'Capa não encontrada'}), 404

        import io
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert('RGB')
        ratio = _THUMB_W / img.width
        img = img.resize((_THUMB_W, max(1, int(img.height * ratio))), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=82, optimize=True)
        data = buf.getvalue()

        if len(_thumb_cache) > 300:
            _thumb_cache.clear()
        _thumb_cache[key] = data
        return Response(data, mimetype='image/jpeg',
                        headers={'Cache-Control': 'private, max-age=300'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Info do conversor ──────────────────────────────────────────────────────────

@app.route('/api/kcc')
def kcc_info():
    profiles = [{'id': k, 'label': v['name']} for k, v in PROFILES.items()]
    return jsonify({
        'version':  f'Comic Color Converter v{CONVERTER_VERSION}',
        'profiles': profiles,
    })


# ── Jobs ───────────────────────────────────────────────────────────────────────

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    with _lock:
        return jsonify(list(_jobs.values()))


@app.route('/api/jobs', methods=['POST'])
def create_job():
    data       = request.json or {}
    files      = data.get('files', [])
    output_dir = data.get('output_dir', '').strip()
    params     = data.get('params', {})

    if not files:
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    job_id = uuid.uuid4().hex[:8]
    q = queue.Queue()

    with _lock:
        # descarta o histórico mais antigo para a memória não crescer sem limite
        finished = [j for j, v in _jobs.items() if v['status'] != 'running']
        while len(_jobs) >= MAX_JOBS_KEPT and finished:
            old = finished.pop(0)
            _jobs.pop(old, None)
            _queues.pop(old, None)

        _queues[job_id] = q
        _jobs[job_id] = {
            'id':        job_id,
            'total':     len(files),
            'done':      0,
            'failed':    0,
            'index':     0,
            'current':   None,
            'status':    'running',
            'results':   [],
            'cancelled': False,
        }

    threading.Thread(
        target=_worker,
        args=(job_id, files, output_dir, params),
        daemon=True,
    ).start()
    return jsonify({'job_id': job_id}), 201


@app.route('/api/jobs/<jid>/cancel', methods=['POST'])
def cancel_job(jid):
    with _lock:
        if jid not in _jobs:
            return jsonify({'error': 'Job não encontrado'}), 404
        _jobs[jid]['cancelled'] = True
    return jsonify({'ok': True})


@app.route('/api/jobs/<jid>/events')
def job_events(jid):
    if jid not in _queues:
        def _err():
            yield f"data: {json.dumps({'error': 'Job não encontrado'})}\n\n"
        return Response(_err(), mimetype='text/event-stream')

    q = _queues[jid]

    def _stream():
        while True:
            try:
                msg = q.get(timeout=20)
                yield f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                if msg['event'] in ('done', 'cancelled'):
                    break
            except queue.Empty:
                yield ': ping\n\n'

    return Response(
        _stream(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Worker ─────────────────────────────────────────────────────────────────────

def _emit(jid: str, event: str, extra: dict | None = None):
    with _lock:
        data = dict(_jobs[jid])
    if extra:
        data.update(extra)
    if jid in _queues:
        _queues[jid].put({'event': event, 'data': data})


def _worker(jid: str, files: list, output_dir: str, params: dict):
    for i, fp in enumerate(files):
        with _lock:
            if _jobs[jid]['cancelled']:
                break
            _jobs[jid]['index']   = i + 1
            _jobs[jid]['current'] = fp

        _emit(jid, 'progress')
        result = _do_convert(fp, output_dir, params)

        with _lock:
            ok = result['ok']
            _jobs[jid]['done' if ok else 'failed'] += 1
            _jobs[jid]['results'].append({
                'name':   Path(fp).name,
                'path':   fp,
                'status': 'done' if ok else 'failed',
                'msg':    result.get('msg', ''),
                'epub':   result.get('epub'),
            })

        _emit(jid, 'progress')

    with _lock:
        cancelled = _jobs[jid]['cancelled']
        _jobs[jid]['status']  = 'cancelled' if cancelled else 'done'
        _jobs[jid]['current'] = None

    _emit(jid, 'cancelled' if cancelled else 'done')


# ── Frontend ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    import webbrowser
    PORT = 5432
    print(f'\n  ◆ Comic Color Converter v{CONVERTER_VERSION}  →  http://localhost:{PORT}\n')
    webbrowser.open(f'http://localhost:{PORT}')
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True)
