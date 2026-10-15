"""
The studio: a small web server on 127.0.0.1 and the page it serves.

Why a local server and not a page opened from disk: VOICEVOX refuses
requests from a file:// page (its CORS rule allows localhost origins only),
and the English-to-katakana model is Python. So the studio is served from
http://127.0.0.1:<port>, and the page talks only to this server.

Nobody else may talk to it. The server binds to 127.0.0.1, and every API
call must carry a token that is generated at start-up and written only into
the page itself:

  * a web page on the internet cannot read our page (same-origin policy),
    so it cannot learn the token;
  * the Host header must be 127.0.0.1 or localhost, which defeats DNS
    rebinding (a hostile domain pointed at 127.0.0.1);
  * a POST must be JSON and, when the browser sends an Origin, ours.

Files are only ever read or written inside the user's data folder, and
names that come from the page are checked to stay there.
"""

import hmac
import json
import logging
import logging.handlers
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
import uuid
import zipfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import NAME, VERSION, RELEASE_DATE, HOMEPAGE
from . import config as cfgmod
from .engine import EngineError, normalize_url
from .paths import layout as get_layout, STUDIO_DIR, BRAND_DIR, FONTS_DIR, GUIDE, ROOT_DIR, WINDOWS
from .script import parse_script, cast_line
from .voices import FAMILIES, FAMILY_OF, ALIASES, policy_summary
from . import system

log = logging.getLogger('vocana')

MIME = {
    '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
    '.png': 'image/png', '.webp': 'image/webp', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.ico': 'image/x-icon', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.woff': 'font/woff',
    '.ttf': 'font/ttf', '.wav': 'audio/wav', '.txt': 'text/plain; charset=utf-8',
    '.srt': 'text/plain; charset=utf-8', '.vtt': 'text/vtt; charset=utf-8', '.zip': 'application/zip',
    '.md': 'text/plain; charset=utf-8',
}
RENDER_FILE = re.compile(r'^[\w\-. ]+\.(wav|srt|vtt|json|txt)$')
HEARTBEAT_TIMEOUT = 180        # seconds without any open studio window before --auto-exit quits
FIRST_WINDOW_TIMEOUT = 600     # ... or without the first window ever appearing


class ApiError(Exception):
    def __init__(self, status, code, message='', **extra):
        Exception.__init__(self, message or code)
        self.status = status
        self.code = code
        self.message = message or code
        self.extra = extra


# ==================================================================
# Background jobs (renders, the install)
# ==================================================================
class Job:
    def __init__(self, kind, target):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.status = 'running'
        self.progress = {'stage': 'start', 'i': 0, 'total': 1}
        self.result = None
        self.error = None
        self.cancel = threading.Event()
        self.started = time.time()
        self.finished = None
        self.thread = threading.Thread(target=self._run, args=(target,), daemon=True)

    def _run(self, target):
        from .render import Cancelled, RenderError
        try:
            self.result = target(self)
            self.status = 'done'
        except Cancelled:
            self.status = 'cancelled'
        except (RenderError, EngineError) as e:
            self.status = 'error'
            self.error = {'code': getattr(e, 'code', None) or 'render_failed', 'message': str(e),
                          'kind': getattr(e, 'kind', 'error'), 'n': getattr(e, 'n', None)}
        except Exception as e:
            self.status = 'error'
            self.error = {'code': 'internal', 'message': '%s: %s' % (type(e).__name__, e)}
            log.error('job %s failed\n%s', self.kind, traceback.format_exc())
        self.finished = time.time()

    def view(self):
        return {'id': self.id, 'kind': self.kind, 'status': self.status, 'progress': self.progress,
                'result': self.result, 'error': self.error, 'elapsed': (self.finished or time.time()) - self.started}


# ==================================================================
# The studio's state
# ==================================================================
class Studio:
    def __init__(self, data_dir=None, auto_exit=False):
        self.layout = get_layout(data_dir).ensure()
        self.token = secrets.token_urlsafe(24)
        self.instance = uuid.uuid4().hex
        self.auto_exit = auto_exit
        self.started = time.time()
        self.last_beat = None
        self.lock = threading.RLock()
        self.jobs = OrderedDict()
        self.previews = OrderedDict()
        self.engine_proc = None
        self.engine_starting = None
        self.port = None
        self.server = None
        self.page = ''
        self.script = ''
        from .render import Vocana
        self.vt = Vocana(data_dir=self.layout.data)
        from .update import Checker
        self.updates = Checker(self.settings, self.save_settings)

    # -- settings ---------------------------------------------------
    def settings(self):
        return cfgmod.load_settings(self.layout.settings)

    def save_settings(self, values):
        with self.lock:
            return cfgmod.save_settings(self.layout.settings, values)

    # -- engine -----------------------------------------------------
    def engine_state(self):
        ver = self.vt.engine.alive(timeout=1.5)
        st = self.settings()
        found = system.find_voicevox(st.get('voicevox_path', ''))
        starting = None
        if self.engine_starting:
            if ver or time.time() - self.engine_starting['at'] > 120:
                self.engine_starting = None
            else:
                starting = self.engine_starting
        if ver is None and self.engine_proc is not None and self.engine_proc.poll() is not None:
            self.engine_proc = None
        return {'url': self.vt.engine.url, 'version': ver, 'starting': starting,
                'ours': self.engine_proc is not None,
                'found': {'app': found['app'], 'engine': found['engine']}}

    def start_engine(self, mode=None):
        st = self.settings()
        if self.vt.engine.alive(timeout=1):
            return {'started': None, 'reason': 'running'}
        port = urllib.parse.urlsplit(self.vt.engine.url).port or 50021
        kind, proc = system.start_voicevox(mode or (st['engine_start'] if st['engine_start'] != 'off' else 'auto'),
                                           st.get('voicevox_path', ''), port)
        if kind is None:
            return {'started': None, 'reason': proc}
        if kind == 'engine':
            self.engine_proc = proc
        self.engine_starting = {'kind': kind, 'at': time.time()}
        log.info('started VOICEVOX (%s)', kind)
        return {'started': kind}

    def stop(self):
        if self.engine_proc is not None:
            system.stop_process(self.engine_proc)
            self.engine_proc = None

    # -- jobs -------------------------------------------------------
    def add_job(self, kind, target):
        with self.lock:
            for j in self.jobs.values():
                if j.status == 'running' and j.kind == kind:
                    raise ApiError(409, 'busy', 'A %s is already running.' % kind, job=j.id)
            job = Job(kind, target)
            self.jobs[job.id] = job
            while len(self.jobs) > 20:
                self.jobs.popitem(last=False)
        job.thread.start()
        return job

    def busy(self):
        return any(j.status == 'running' for j in self.jobs.values())


# ==================================================================
# Request handling
# ==================================================================
def within(base, *parts):
    """The real path of base/parts, refusing anything that leaves base."""
    b = os.path.realpath(base)
    p = os.path.realpath(os.path.join(base, *parts))
    try:
        if os.path.commonpath([p, b]) != b:
            raise ApiError(403, 'forbidden', 'outside the data folder')
    except ValueError:
        raise ApiError(403, 'forbidden', 'outside the data folder')
    return p


def boot_json(studio):
    st = studio.settings()
    lay = studio.layout
    data = {'token': studio.token, 'version': VERSION, 'date': RELEASE_DATE, 'name': NAME,
            'homepage': HOMEPAGE, 'lang': st['lang'], 'theme': st['theme'], 'page': studio.page,
            'script': studio.script, 'platform': sys.platform, 'installed': lay.installed,
            'windows': WINDOWS}
    return json.dumps(data, ensure_ascii=False).replace('</', '<\\/')


class Handler(BaseHTTPRequestHandler):
    server_version = 'Vocana/' + VERSION
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    @property
    def studio(self):
        return self.server.studio

    def log_message(self, fmt, *args):            # quiet; errors go to the log file
        pass

    # -- plumbing ---------------------------------------------------
    def send(self, status, body, ctype='application/json; charset=utf-8', headers=None, cache=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        if status >= 400:
            # The request body may not have been read; on a kept-alive
            # connection it would be parsed as the next request.
            self.close_connection = True
            self.send_header('Connection', 'close')
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'max-age=3600' if cache else 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    def send_file(self, path, download=None, cache=False):
        if not os.path.isfile(path):
            raise ApiError(404, 'not_found')
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        rng = self.headers.get('Range')
        start, end = 0, size - 1
        status = 200
        m = re.match(r'bytes=(\d*)-(\d*)$', rng or '')
        if m and size:
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            elif m.group(2):
                start = max(0, size - int(m.group(2)))
            end = min(end, size - 1)
            if start > end:
                self.send_response(416)
                self.send_header('Content-Range', 'bytes */%d' % size)
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', MIME.get(ext, 'application/octet-stream'))
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'max-age=3600' if cache else 'no-store')
        if status == 206:
            self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        if download:
            quoted = urllib.parse.quote(download)
            self.send_header('Content-Disposition', "attachment; filename=\"%s\"; filename*=UTF-8''%s"
                             % (re.sub(r'[^\x20-\x7e]|"', '_', download), quoted))
        self.end_headers()
        if self.command == 'HEAD':
            return
        with open(path, 'rb') as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > 20 * 2**20:
            raise ApiError(413, 'too_large')
        raw = self.rfile.read(n) if n else b''
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'bad_json')
        if not isinstance(data, dict):
            raise ApiError(400, 'bad_json')
        return data

    def check_host(self):
        host = (self.headers.get('Host') or '').lower()
        allowed = {'127.0.0.1:%d' % self.studio.port, 'localhost:%d' % self.studio.port}
        if host not in allowed:
            raise ApiError(403, 'bad_host', 'Vocana only answers on 127.0.0.1.')

    def check_token(self, query):
        sent = self.headers.get('X-Vocana-Token') or (query.get('t', [''])[0] if self.command in ('GET', 'HEAD') else '')
        if not sent or not hmac.compare_digest(sent, self.studio.token):
            raise ApiError(403, 'bad_token', 'This page is from an older start of Vocana. Reload it.')

    def check_post(self):
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:%d' % self.studio.port, 'http://localhost:%d' % self.studio.port):
            raise ApiError(403, 'bad_origin')
        if not (self.headers.get('Content-Type') or '').startswith('application/json'):
            raise ApiError(415, 'json_only')

    # -- dispatch ---------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.handle_any('GET')

    def do_POST(self):
        self.handle_any('POST')

    def handle_any(self, method):
        url = urllib.parse.urlsplit(self.path)
        path = urllib.parse.unquote(url.path)
        query = urllib.parse.parse_qs(url.query)
        try:
            self.check_host()
            if not path.startswith('/api/'):
                if method != 'GET':
                    raise ApiError(405, 'method')
                return self.static(path)
            if path == '/api/ping':
                return self.send(200, {'app': NAME, 'version': VERSION, 'instance': self.studio.instance,
                                       'data': self.studio.layout.data})
            self.check_token(query)
            if method == 'POST':
                self.check_post()
                data = self.body()
            else:
                data = {}
            out = route(self, method, path, query, data)
            if out is not None:
                self.send(200, out)
        except ApiError as e:
            self.send(e.status, dict(e.extra, error=e.code, message=e.message))
        except EngineError as e:
            if e.kind == 'down':
                self.send(503, {'error': 'engine_down', 'message': str(e)})
            else:
                self.send(502, {'error': 'engine_error', 'message': str(e), 'detail': e.detail, 'code': e.code})
        except Exception as e:
            log.error('%s %s failed\n%s', method, path, traceback.format_exc())
            self.send(500, {'error': 'internal', 'message': '%s: %s' % (type(e).__name__, e)})

    def static(self, path):
        if path in ('/', '/index.html'):
            with open(os.path.join(STUDIO_DIR, 'index.html'), encoding='utf-8') as f:
                html = f.read().replace('__BOOT__', boot_json(self.studio))
            return self.send(200, html, 'text/html; charset=utf-8', {
                'Content-Security-Policy': "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; "
                                           "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
                                           "font-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})
        if path == '/favicon.ico':
            return self.send_file(os.path.join(BRAND_DIR, 'vocana.ico'), cache=True)
        if path == '/guide' or path == '/Guide.html':
            return self.send_file(GUIDE)
        for prefix, base in (('/static/', STUDIO_DIR), ('/brand/', BRAND_DIR), ('/fonts/', FONTS_DIR)):
            if path.startswith(prefix):
                name = path[len(prefix):]
                if not re.fullmatch(r'[\w\-.]+', name) or name.startswith('.'):
                    raise ApiError(404, 'not_found')
                return self.send_file(os.path.join(base, name), cache=prefix != '/static/')
        if path.startswith('/renders/') and re.fullmatch(r'/renders/[\w\-. ]+/[\w\-. ]+', path):
            # The sample render that ships in the folder: Guide.html, opened
            # through the studio, plays renders/Sample/full.wav by this path.
            return self.send_file(within(os.path.join(ROOT_DIR, 'renders'), *path.split('/')[2:]))
        raise ApiError(404, 'not_found')


# ==================================================================
# The API
# ==================================================================
def route(h, method, path, query, data):
    st = h.studio
    vt = st.vt
    parts = [p for p in path[len('/api/'):].split('/') if p]
    head = parts[0] if parts else ''

    if head == 'status':
        vt.reload_if_changed()
        st.updates.maybe_check()
        return {'version': VERSION, 'name': NAME, 'layout': st.layout.as_dict(), 'settings': st.settings(),
                'engine': st.engine_state(), 'model': vt.kana.c2k is not None,
                'warnings': vt.cfg_warnings, 'update': st.updates.info(), 'busy': st.busy(),
                'platform': sys.platform}

    if head == 'heartbeat':
        st.last_beat = time.time()
        return {'ok': True, 'busy': st.busy()}

    if head == 'quit' and method == 'POST':
        threading.Thread(target=shutdown, args=(st,), daemon=True).start()
        return {'ok': True}

    if head == 'engine':
        if parts[1:] == ['start'] and method == 'POST':
            return st.start_engine(data.get('mode'))
        if parts[1:] == ['url'] and method == 'POST':
            url = normalize_url(str(data.get('url') or ''))
            with st.lock:
                cfg, _w = cfgmod.load_moods(st.layout.moods)
                cfg['engine'] = url
                cfgmod.save_moods(st.layout.moods, cfg)
            vt.load()
            return st.engine_state()
        return st.engine_state()

    if head == 'voices':
        voices = vt.voices(refresh=bool(query.get('refresh')))
        chars = []
        for sp in voices.speakers:
            chars.append({'name': sp['name'], 'uuid': sp['speaker_uuid'], 'aliases': ALIASES.get(sp['name'], []),
                          'styles': [{'name': s['name'], 'id': s['id'], 'family': FAMILY_OF.get(s['name'])}
                                     for s in sp['styles']]})
        return {'characters': chars, 'families': list(FAMILIES)}

    if head == 'voice':
        uuid_ = (query.get('uuid') or [''])[0]
        voices = vt.voices()
        sp = next((s for s in voices.speakers if s['speaker_uuid'] == uuid_), None)
        if sp is None:
            raise ApiError(404, 'no_character')
        info = vt.engine.speaker_info(uuid_)
        res = lambda u: res_url(st, u)
        styles = []
        by_id = {si.get('id'): si for si in info.get('style_infos', [])}
        for s in sp['styles']:
            si = by_id.get(s['id'], {})
            styles.append({'id': s['id'], 'name': s['name'], 'family': FAMILY_OF.get(s['name']),
                           'icon': res(si.get('icon')), 'portrait': res(si.get('portrait')),
                           'samples': [res(v) for v in (si.get('voice_samples') or []) if v]})
        summary = policy_summary(sp['name'], info.get('policy', ''))
        return dict(summary, name=sp['name'], uuid=uuid_, portrait=res(info.get('portrait')), styles=styles,
                    aliases=ALIASES.get(sp['name'], []))

    if head == 'res':
        p = (query.get('p') or [''])[0]
        body, ctype = vt.engine.resource(p)
        h.send(200, body, ctype if ctype.split('/')[0] in ('image', 'audio') else 'application/octet-stream', cache=True)
        return None

    if head == 'plan' and method == 'POST':
        text = str(data.get('text') or '')
        if len(text) > 400000:
            raise ApiError(413, 'too_large')
        return vt.plan_script(text, offline=bool(data.get('offline')))

    if head == 'preview':
        if method == 'POST':
            return preview(st, data)
        m = re.fullmatch(r'([0-9a-f]{16})\.wav', parts[1] if len(parts) > 1 else '')
        hit = st.previews.get(m.group(1)) if m else None
        if hit is None:
            raise ApiError(404, 'not_found')
        h.send(200, hit['wav'], 'audio/wav')
        return None

    if head == 'render' and method == 'POST':
        return start_render(st, data)

    if head == 'jobs':
        job = st.jobs.get(parts[1] if len(parts) > 1 else '')
        if job is None:
            raise ApiError(404, 'no_job')
        if len(parts) > 2 and parts[2] == 'cancel' and method == 'POST':
            job.cancel.set()
        return job.view()

    if head == 'renders':
        return renders(h, st, method, parts[1:], data)

    if head == 'scripts':
        return scripts(st, method, parts[1:], data)

    if head == 'open' and method == 'POST':
        return open_thing(st, data)

    if head == 'words':
        return words(st, method, parts[1:], data)

    if head == 'moods':
        return moods(st, method, parts[1:], data)

    if head == 'cast-line' and method == 'POST':
        spec = data.get('spec') or {}
        if not isinstance(spec, dict) or not spec.get('speaker'):
            raise ApiError(400, 'bad_spec')
        return {'line': cast_line(str(data.get('who') or 'ME').upper(), spec)}

    if head == 'settings':
        if method == 'POST':
            clean = {k: v for k, v in data.items() if not k.startswith('_')}
            s = st.save_settings(clean)
            return s
        return st.settings()

    if head == 'doctor':
        from .doctor import report
        return {'rows': report(st.layout.data)}

    if head == 'update':
        if method == 'POST':
            st.updates.maybe_check(force=True)
            time.sleep(0.1)
        return st.updates.info()

    if head == 'install':
        from . import installer
        if method == 'POST' and parts[1:] == ['run']:
            opts = {'desktop': bool(data.get('desktop', True)), 'start_menu': bool(data.get('start_menu', True)),
                    'lang': str(data.get('lang') or 'en')}
            job = st.add_job('install', lambda job: installer.install(job=job, **opts))
            return job.view()
        if method == 'POST' and parts[1:] == ['launch']:
            job = st.jobs.get(str(data.get('job') or ''))
            if job is None or job.kind != 'install' or job.status != 'done':
                raise ApiError(400, 'not_installed')
            installer.launch_detached(job.result['launch'])
            threading.Thread(target=shutdown, args=(st, 1.0), daemon=True).start()
            return {'ok': True}
        if method == 'POST' and parts[1:] == ['uninstall']:
            res = installer.uninstall(keep_running=False)
            threading.Thread(target=shutdown, args=(st, 1.0), daemon=True).start()
            return res
        return installer.info()

    raise ApiError(404, 'not_found')


def res_url(st, u):
    """Engine resource URL (or base64 data) -> something the page can load."""
    if not u:
        return None
    if isinstance(u, str) and u.startswith('http'):
        p = urllib.parse.urlsplit(u).path
        return '/api/res?p=%s&t=%s' % (urllib.parse.quote(p), st.token)
    if isinstance(u, str) and len(u) > 100:          # base64 from an engine without resource URLs
        kind = 'audio/wav' if u.startswith('UklGR') else 'image/png'
        return 'data:%s;base64,%s' % (kind, u)
    return None


# ------------------------------------------------------------------
def preview(st, data):
    """Say one line of the script that is open in the editor, with that
    script's cast. data: {text, n} - or {line, character?} for a snippet."""
    from .render import wav_bytes, normalize
    vt = st.vt
    vt.reload_if_changed()
    if 'n' in data:
        sc = parse_script(str(data.get('text') or ''))
        n = int(data['n'])
        item = next((it for it in sc['items'] if it['kind'] == 'line' and it['n'] == n), None)
        if item is None:
            raise ApiError(404, 'no_line', 'There is nothing to say on line %d.' % n)
    else:
        line = str(data.get('line') or '').strip()
        if not line:
            raise ApiError(400, 'empty')
        sc = parse_script(line)
        item = next((it for it in sc['items'] if it['kind'] == 'line'), None)
        if item is None:
            raise ApiError(400, 'empty')
        if data.get('character'):
            sc['cast'][item['who']] = {'speaker': str(data['character'])}
        if data.get('moods'):
            item['moods'] = [str(m).lower() for m in data['moods']]
    voices = vt.voices()
    char = vt.character(item['who'], sc['cast'], voices)
    key_src = json.dumps([sc['cast'].get(item['who']), item['who'], item['moods'], item['text'], sc['sentence_gap'],
                          vt._stamp, vt.engine.url, data.get('character')], ensure_ascii=False, default=str)
    import hashlib
    key = hashlib.sha256(key_src.encode('utf-8')).hexdigest()[:16]
    hit = st.previews.get(key)
    if hit is None:
        notes = []
        x, sr, sentences = vt.speak_timed(item['text'], item['moods'], sc['sentence_gap'], item['who'], char,
                                          voices, notes)
        x = normalize(x)
        hit = {'wav': wav_bytes(x, sr), 'sentences': sentences, 'duration': len(x) / sr, 'notes': notes,
               'character': char.get('name')}
        with st.lock:
            st.previews[key] = hit
            while len(st.previews) > 60:
                st.previews.popitem(last=False)
    else:
        st.previews.move_to_end(key)
    return {'id': key, 'url': '/api/preview/%s.wav?t=%s' % (key, st.token), 'sentences': hit['sentences'],
            'duration': hit['duration'], 'character': hit['character'], 'warnings': hit['notes'],
            'n': item['n'], 'who': item['who']}


def start_render(st, data):
    from .render import safe_name
    text = str(data.get('text') or '')
    name = safe_name(data.get('name') or 'Untitled', 'Untitled')
    if not parse_script(text)['items']:
        raise ApiError(400, 'empty_script', 'The script has no lines to say.')
    out = within(st.layout.renders, name)

    def run(job):
        def progress(ev):
            job.progress = ev
        return st.vt.render_script(text, out, progress=progress, cancel=job.cancel, script_name=name)
    job = st.add_job('render', run)
    return job.view()


# ------------------------------------------------------------------
def list_renders(st):
    out = []
    base = st.layout.renders
    if not os.path.isdir(base):
        return out
    for name in os.listdir(base):
        d = os.path.join(base, name)
        full = os.path.join(d, 'full.wav')
        if name.startswith('.') or not os.path.isfile(full):
            continue
        item = {'name': name, 'mtime': os.path.getmtime(full), 'size': os.path.getsize(full)}
        try:
            with open(os.path.join(d, 'timing.json'), encoding='utf-8') as f:
                tj = json.load(f)
            item['length'] = tj.get('length')
            item['lines'] = len(tj.get('lines') or [])
            item['characters'] = sorted({ln.get('character') for ln in tj.get('lines', []) if ln.get('character')})
        except (OSError, ValueError):
            pass
        out.append(item)
    out.sort(key=lambda r: -r['mtime'])
    return out


def renders(h, st, method, parts, data):
    if not parts:
        return {'renders': list_renders(st), 'folder': st.layout.renders}
    name = parts[0]
    d = within(st.layout.renders, name)
    if not os.path.isdir(d):
        raise ApiError(404, 'no_render')
    if len(parts) == 1:
        files = sorted(f for f in os.listdir(d) if RENDER_FILE.match(f))
        return {'name': name, 'files': files}
    what = parts[1]
    if what == 'delete' and method == 'POST':
        if os.path.realpath(d) == os.path.realpath(st.layout.renders):
            raise ApiError(403, 'forbidden')
        shutil.rmtree(d)
        return {'ok': True}
    if what == 'zip':
        tmp = tempfile.NamedTemporaryFile(prefix='vocana-', suffix='.zip', delete=False)
        try:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
                for f in sorted(os.listdir(d)):
                    if RENDER_FILE.match(f):
                        z.write(os.path.join(d, f), '%s/%s' % (name, f),
                                compress_type=zipfile.ZIP_STORED if f.endswith('.wav') else zipfile.ZIP_DEFLATED)
            tmp.close()
            h.send_file(tmp.name, download=name + '.zip')
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass
        return None
    if not RENDER_FILE.match(what):
        raise ApiError(404, 'not_found')
    dl = (h.path.find('download=1') >= 0)
    h.send_file(within(d, what), download=(name + '-' + what) if dl else None)
    return None


# ------------------------------------------------------------------
def scripts(st, method, parts, data):
    from .render import safe_name
    base = st.layout.scripts
    os.makedirs(base, exist_ok=True)
    if not parts and method == 'GET':
        out = []
        for f in os.listdir(base):
            p = os.path.join(base, f)
            if f.lower().endswith('.txt') and os.path.isfile(p):
                out.append({'name': f[:-4], 'mtime': os.path.getmtime(p), 'size': os.path.getsize(p)})
        out.sort(key=lambda r: -r['mtime'])
        return {'scripts': out, 'folder': base}
    if parts == ['save'] and method == 'POST':
        name = safe_name(data.get('name') or 'Untitled', 'Untitled')
        text = str(data.get('text') or '')
        path = within(base, name + '.txt')
        if os.path.exists(path) and not data.get('overwrite'):
            old, _e = cfgmod.read_text(path)
            if old.replace('\r\n', '\n') != text.replace('\r\n', '\n'):
                raise ApiError(409, 'exists', 'A script with this name already exists.', name=name)
        cfgmod.write_text(path, text.replace('\r\n', '\n').replace('\n', '\r\n') if WINDOWS else text)
        st.save_settings({'last_script': name})
        return {'name': name, 'mtime': os.path.getmtime(path)}
    if parts == ['delete'] and method == 'POST':
        path = within(base, safe_name(data.get('name') or '') + '.txt')
        if os.path.isfile(path):
            os.remove(path)
        return {'ok': True}
    if parts == ['rename'] and method == 'POST':
        src = within(base, safe_name(data.get('name') or '') + '.txt')
        new = safe_name(data.get('to') or '', '')
        if not new:
            raise ApiError(400, 'bad_name')
        dst = within(base, new + '.txt')
        if os.path.exists(dst):
            raise ApiError(409, 'exists', name=new)
        os.replace(src, dst)
        return {'name': new}
    if len(parts) == 1 and method == 'GET':
        path = within(base, parts[0] + '.txt')
        if not os.path.isfile(path):
            raise ApiError(404, 'no_script')
        text, enc = cfgmod.read_text(path)
        st.save_settings({'last_script': parts[0]})
        return {'name': parts[0], 'text': text.replace('\r\n', '\n'), 'encoding': enc, 'mtime': os.path.getmtime(path)}
    raise ApiError(404, 'not_found')


def open_thing(st, data):
    lay = st.layout
    what = data.get('what')
    targets = {'renders': lay.renders, 'scripts': lay.scripts, 'data': lay.data, 'words': lay.words,
               'moods': lay.moods, 'logs': lay.logs}
    if what == 'render':
        path = within(lay.renders, str(data.get('name') or ''))
        f = data.get('file')
        if f and RENDER_FILE.match(str(f)):
            path = within(path, str(f))
    elif what in targets:
        path = targets[what]
        os.makedirs(path if what not in ('words', 'moods') else lay.data, exist_ok=True)
    else:
        raise ApiError(400, 'bad_target')
    if not os.path.exists(path):
        raise ApiError(404, 'not_found')
    return {'ok': bool(system.open_path(path)), 'path': path}


# ------------------------------------------------------------------
def words(st, method, parts, data):
    from .kana import Kana, moras_of
    vt = st.vt
    if parts == ['test'] and method == 'POST':
        out = []
        for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*|[ァ-ヴーぁ-ゖ]+", str(data.get('text') or ''))[:200]:
            k, src = vt.kana.lookup(w)
            out.append({'word': w, 'kana': k, 'moras': moras_of(k), 'source': src,
                        'model': (Kana.model()(w.lower()) if Kana.model() and w.isalpha() else None)})
        return {'words': out}
    if method == 'POST' and not parts:
        entries = data.get('words')
        if not isinstance(entries, dict):
            raise ApiError(400, 'bad_words')
        clean = {}
        for k, v in entries.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                if len(k) > 80 or len(v) > 80:
                    continue
                clean[k.strip().lower()] = v.strip()
        with st.lock:
            cfgmod.save_words(st.layout.words, clean)
        vt.load()
    w, warnings = cfgmod.load_words(st.layout.words)
    return {'words': w, 'warnings': warnings, 'path': st.layout.words, 'count': len(w)}


def moods(st, method, parts, data):
    vt = st.vt
    default = cfgmod.default_json('moods.json')
    if method == 'POST':
        with st.lock:
            cfg, _w = cfgmod.load_moods(st.layout.moods)
            if parts == ['reset']:
                name = data.get('name')
                if name:
                    if name in default['moods']:
                        cfg['moods'][name] = cfgmod.clean_mood(name, default['moods'][name], [])
                    else:
                        cfg['moods'].pop(name, None)
                else:
                    cfg['moods'] = {k: cfgmod.clean_mood(k, v, []) for k, v in default['moods'].items()}
            else:
                if isinstance(data.get('moods'), dict):
                    warn = []
                    new = {}
                    for k, v in data['moods'].items():
                        k = re.sub(r'[^a-z0-9_\-]', '', str(k).lower())[:30]
                        if k:
                            new[k] = cfgmod.clean_mood(k, v, warn)
                    if 'normal' not in new:
                        raise ApiError(400, 'normal_required', 'The "normal" mood cannot be removed.')
                    cfg['moods'] = new
                for k in ('speaker', 'style'):
                    if isinstance(data.get(k), str) and data[k].strip():
                        cfg[k] = data[k].strip()
                if isinstance(data.get('cast'), dict):
                    warn = []
                    cfg['cast'] = {}
                    for tag, spec in data['cast'].items():
                        e = cfgmod.clean_cast(tag, spec, warn)
                        if e:
                            cfg['cast'][str(tag).strip().upper()] = e
            cfgmod.save_moods(st.layout.moods, cfg)
        vt.load()
    cfg, warnings = cfgmod.load_moods(st.layout.moods)
    return {'moods': cfg['moods'], 'speaker': cfg['speaker'], 'style': cfg['style'], 'cast': cfg['cast'],
            'engine': cfg['engine'], 'families': list(FAMILIES), 'defaults': list(default['moods']),
            'warnings': warnings, 'path': st.layout.moods}


# ==================================================================
# Start and stop
# ==================================================================
def setup_logging(lay):
    try:
        os.makedirs(lay.logs, exist_ok=True)
        hnd = logging.handlers.RotatingFileHandler(os.path.join(lay.logs, 'vocana.log'), maxBytes=512 * 1024,
                                                   backupCount=2, encoding='utf-8')
        hnd.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        log.addHandler(hnd)
        log.setLevel(logging.INFO)
    except OSError:
        pass


def instance_file(lay):
    return os.path.join(lay.data, '.vocana-instance.json')


def find_running(lay):
    """The port of a studio already running on this data folder, or None."""
    import urllib.request
    try:
        with open(instance_file(lay), encoding='utf-8') as f:
            info = json.load(f)
        port = int(info['port'])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://127.0.0.1:%d/api/ping' % port, timeout=1.5) as r:
            d = json.loads(r.read().decode('utf-8'))
        if d.get('app') == NAME and os.path.realpath(d.get('data', '')) == os.path.realpath(lay.data):
            return port
    except Exception:
        return None
    return None


class Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second program bind a port that is
    # already in use, and the two then split the requests between them.
    # Exclusive use instead: a busy port fails, and the next one is tried.
    allow_reuse_address = not WINDOWS
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A browser that closes a tab mid-answer is not an error worth a
        # traceback; anything else goes to the log.
        exc = sys.exc_info()[1]
        if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
            return
        log.error('request from %s failed\n%s', client_address, traceback.format_exc())

    def server_bind(self):
        if WINDOWS:
            import socket
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_EXCLUSIVEADDRUSE', -5), 1)
            except OSError:
                pass
        ThreadingHTTPServer.server_bind(self)


def bind(studio, preferred):
    for port in [preferred] + list(range(preferred + 1, preferred + 12)) + [0]:
        try:
            srv = Server(('127.0.0.1', port), Handler)
            srv.daemon_threads = True
            srv.studio = studio
            studio.port = srv.server_address[1]
            return srv
        except OSError:
            continue
    raise OSError('no free port')


def shutdown(st, delay=0.3):
    time.sleep(delay)
    try:
        st.stop()
    finally:
        try:
            os.remove(instance_file(st.layout))
        except OSError:
            pass
        if st.server is not None:
            st.server.shutdown()


def watchdog(st):
    while True:
        time.sleep(10)
        if not st.auto_exit or st.busy():
            continue
        now = time.time()
        if st.last_beat is None:
            if now - st.started > FIRST_WINDOW_TIMEOUT:
                log.info('no studio window ever opened; quitting')
                return shutdown(st, 0)
        elif now - st.last_beat > HEARTBEAT_TIMEOUT:
            log.info('studio window closed; quitting')
            return shutdown(st, 0)


def import_script(lay, path):
    """A .txt dropped on Vocana.bat: copied into scripts/ (unless it is
    already there) and opened. Returns the script's name."""
    from .render import safe_name
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        return ''
    scripts_dir = os.path.realpath(lay.scripts)
    if os.path.dirname(os.path.realpath(path)) == scripts_dir and path.lower().endswith('.txt'):
        return os.path.splitext(os.path.basename(path))[0]
    text, _enc = cfgmod.read_text(path)
    base = safe_name(os.path.splitext(os.path.basename(path))[0], 'Imported')
    name, k = base, 1
    while True:
        target = os.path.join(lay.scripts, name + '.txt')
        if not os.path.exists(target):
            break
        old, _e = cfgmod.read_text(target)
        if old.replace('\r\n', '\n') == text.replace('\r\n', '\n'):
            return name
        k += 1
        name = '%s (%d)' % (base, k)
    os.makedirs(lay.scripts, exist_ok=True)
    cfgmod.write_text(target, text)
    return name


def run_studio(port=None, open_browser=True, auto_exit=False, page='', script=None, data_dir=None):
    lay = get_layout(data_dir).ensure()
    setup_logging(lay)
    name = import_script(lay, script) if script else ''
    st_settings = cfgmod.load_settings(lay.settings)
    running = find_running(lay)
    frag = ''
    if name:
        frag = '#script=' + urllib.parse.quote(name)
    elif page:
        frag = '#' + page
    if running:
        url = 'http://127.0.0.1:%d/%s' % (running, frag)
        if open_browser:
            system.open_browser(url, st_settings.get('app_window', True))
        print('Vocana is already running: ' + url)
        return 0
    studio = Studio(data_dir=lay.data, auto_exit=auto_exit)
    studio.page = page
    studio.script = name or ''
    try:
        srv = bind(studio, port or st_settings.get('port') or 50210)
    except OSError as e:
        system.message_box(NAME, 'Vocana could not open its studio: %s' % e)
        return 1
    studio.server = srv
    try:
        # The token is in here so Setup can ask a running copy to quit before
        # replacing its files. The file sits in the user's own folder: any
        # program that can read it can already act as the user.
        cfgmod.write_json(instance_file(lay), {'port': studio.port, 'pid': os.getpid(), 'version': VERSION,
                                               'token': studio.token})
    except OSError:
        pass
    url = 'http://127.0.0.1:%d/%s' % (studio.port, frag)
    log.info('studio on %s (data %s)', url, lay.data)
    if st_settings.get('engine_start', 'auto') != 'off' and not studio.vt.engine.alive(timeout=1):
        try:
            studio.start_engine()
        except Exception:
            log.error('could not start VOICEVOX\n%s', traceback.format_exc())
    threading.Thread(target=watchdog, args=(studio,), daemon=True).start()
    studio.updates.maybe_check()
    try:
        sys.stdout.write('%s %s - studio: %s\n(keep this window open; close it to quit)\n' % (NAME, VERSION, url))
        sys.stdout.flush()
    except Exception:
        pass
    if open_browser:
        threading.Timer(0.3, system.open_browser, args=(url, st_settings.get('app_window', True))).start()
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        studio.stop()
        try:
            os.remove(instance_file(lay))
        except OSError:
            pass
        srv.server_close()
    return 0
