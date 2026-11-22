"""
The VOICEVOX engine, over HTTP, with the standard library only.

Two things here exist because they broke real setups:

  * Requests to the engine never go through a proxy. urllib reads the
    system proxy on Windows (and HTTP_PROXY everywhere), and a VPN or proxy
    tool that sets one sent "127.0.0.1:50021" to the proxy, which cannot
    reach the user's own computer. The result was "VOICEVOX is not
    answering" with VOICEVOX open on the screen.

  * "localhost" is rewritten to 127.0.0.1. VOICEVOX listens on IPv4 only,
    and on Windows "localhost" resolves to ::1 first, so every request
    waited for an IPv6 refusal before trying the address that works.
"""

import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import http.client

DEFAULT_URL = 'http://127.0.0.1:50021'

_NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class EngineError(RuntimeError):
    """The engine answered with an error, or did not answer at all."""

    def __init__(self, message, code=None, path=None, detail=None, kind='error'):
        RuntimeError.__init__(self, message)
        self.code = code
        self.path = path
        self.detail = detail
        self.kind = kind            # 'down' | 'error' | 'voice'


def normalize_url(url):
    """'127.0.0.1:50021', 'localhost:50021/', ' http://x ' -> a usable base URL."""
    url = (url or '').strip() or DEFAULT_URL
    if '://' not in url:
        url = 'http://' + url
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or '127.0.0.1'
    if host in ('localhost', '0.0.0.0'):
        host = '127.0.0.1'
    port = parts.port
    netloc = host if port is None else '%s:%d' % (host, port)
    if ':' in host and not host.startswith('['):
        netloc = '[%s]' % host if port is None else '[%s]:%d' % (host, port)
    return urllib.parse.urlunsplit((parts.scheme or 'http', netloc, parts.path.rstrip('/'), '', ''))


# The style types that read text. Everything else (frame_decode, sing,
# singing_teacher...) only sings. VOICEVOX 0.26 renamed talking styles to
# 'streaming_talk'; filtering out singing styles rather than hard-coding one
# name keeps future talking types working too.
TALK_TYPES = ('talk', 'streaming_talk')
SING_TYPES = ('frame_decode', 'sing', 'singing_teacher')


def is_talk_style(style):
    t = (style or {}).get('type') or 'talk'
    if t in TALK_TYPES:
        return True
    return t not in SING_TYPES and 'sing' not in str(t).lower()


class Engine:
    def __init__(self, url=DEFAULT_URL, timeout=120):
        self.url = normalize_url(url)
        self.timeout = timeout
        self._template = {}
        self._speakers = None
        self._speakers_at = 0.0
        self._info = {}
        self._manifest = None
        self._lock = threading.Lock()

    def clear_cache(self):
        """Drop cached speakers, portraits, manifest and audio_query templates
        (called when VOICEVOX restarts or switches version)."""
        with self._lock:
            self._template.clear()
            self._speakers = None
            self._speakers_at = 0.0
            self._info.clear()
            self._manifest = None

    # --------------------------------------------------------------
    def _req(self, method, path, params=None, body=None, raw=False, timeout=None):
        q = ('?' + urllib.parse.urlencode(params)) if params else ''
        data = None
        headers = {'User-Agent': 'Vocana'}
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        last = None
        for attempt in range(2):
            req = urllib.request.Request(self.url + path + q, data=data, method=method, headers=headers)
            try:
                with _NO_PROXY.open(req, timeout=timeout or self.timeout) as r:
                    content = r.read()
                break
            except urllib.error.HTTPError as e:
                detail = _error_detail(e)
                raise EngineError('VOICEVOX said %s for %s: %s' % (e.code, path, detail),
                                  code=e.code, path=path, detail=detail)
            except (ConnectionResetError, ConnectionAbortedError, http.client.RemoteDisconnected,
                    http.client.IncompleteRead) as e:
                # The engine dropped the connection mid-answer: it happens
                # while it loads a voice. Once more, then give up.
                last = e
                time.sleep(0.4)
                continue
            except (urllib.error.URLError, socket.timeout, OSError) as e:
                reason = getattr(e, 'reason', e)
                if isinstance(reason, socket.timeout) or isinstance(e, socket.timeout):
                    raise EngineError('VOICEVOX did not answer in time (%s).' % path, path=path, kind='down')
                raise EngineError('VOICEVOX is not answering at %s. Open the VOICEVOX app first '
                                  '(it starts the engine), then try again.' % self.url, path=path, kind='down')
        else:
            raise EngineError('VOICEVOX closed the connection (%s): %s' % (path, last), path=path, kind='down')
        if raw:
            return content
        try:
            return json.loads(content.decode('utf-8'))
        except ValueError:
            raise EngineError('VOICEVOX sent something that is not JSON for %s.' % path, path=path)

    # --------------------------------------------------------------
    def version(self, timeout=3):
        v = self._req('GET', '/version', timeout=timeout)
        return v if isinstance(v, str) else str(v)

    def alive(self, timeout=2):
        try:
            return self.version(timeout=timeout)
        except EngineError:
            return None

    def manifest(self):
        with self._lock:
            if self._manifest is not None:
                return self._manifest
        try:
            m = self._req('GET', '/engine_manifest', timeout=10)
        except EngineError:
            m = {}
        with self._lock:
            self._manifest = m
            return self._manifest

    def speakers(self, refresh=False):
        with self._lock:
            if not refresh and self._speakers and time.time() - self._speakers_at <= 300:
                return self._speakers
        sp = self._req('GET', '/speakers', timeout=30)
        # Singing-only styles (type 'frame_decode' / 'sing') cannot
        # read text. Older engines have no type: they are all talk.
        # VOICEVOX 0.26 calls its talking styles 'streaming_talk':
        # keeping only 'talk' dropped every voice ("no characters").
        filtered = []
        for s in sp:
            styles = [st for st in s.get('styles', []) if is_talk_style(st)]
            if styles:
                entry = dict(s)
                entry['styles'] = styles
                filtered.append(entry)
        with self._lock:
            self._speakers = filtered
            self._speakers_at = time.time() if filtered else 0.0
            return self._speakers

    def speaker_info(self, uuid):
        with self._lock:
            if uuid in self._info:
                return self._info[uuid]
        feats = self.manifest().get('supported_features') or {}
        params = {'speaker_uuid': uuid}
        if feats.get('return_resource_url'):
            params['resource_format'] = 'url'
        info = self._req('GET', '/speaker_info', params, timeout=30)
        with self._lock:
            self._info[uuid] = info
            return info

    def resource(self, path):
        """(bytes, content type) of an engine resource: an icon, a portrait,
        a voice sample. Only paths under /_resources/ - the studio passes
        these through from the browser."""
        if not path.startswith('/_resources/') or '..' in path or '?' in path or '#' in path:
            raise EngineError('not a resource path', path=path)
        req = urllib.request.Request(self.url + path, headers={'User-Agent': 'Vocana'})
        try:
            with _NO_PROXY.open(req, timeout=30) as r:
                return r.read(), r.headers.get('Content-Type', 'application/octet-stream')
        except urllib.error.HTTPError as e:
            raise EngineError('VOICEVOX said %s for %s' % (e.code, path), code=e.code, path=path)
        except (urllib.error.URLError, socket.timeout, OSError):
            raise EngineError('VOICEVOX is not answering at %s.' % self.url, path=path, kind='down')

    def initialize(self, sid):
        """Load a voice before it is needed, so the first line does not take
        the loading time. Engines without the endpoint are fine."""
        try:
            self._req('POST', '/initialize_speaker', {'speaker': sid, 'skip_reinit': 'true'}, timeout=300)
        except EngineError as e:
            if e.kind == 'down':
                raise

    def accent_phrases(self, text, sid, is_kana=True):
        return self._req('POST', '/accent_phrases',
                         {'text': text, 'speaker': sid, 'is_kana': 'true' if is_kana else 'false'})

    def template(self, sid):
        with self._lock:
            tpl = self._template.get(sid)
        if tpl is None:
            tpl = self._req('POST', '/audio_query', {'text': 'あ', 'speaker': sid})
            with self._lock:
                self._template[sid] = tpl
        return json.loads(json.dumps(tpl))

    def synthesis(self, query, sid):
        return self._req('POST', '/synthesis', {'speaker': sid, 'enable_interrogative_upspeak': 'true'},
                         body=query, raw=True)


def _error_detail(e):
    try:
        body = e.read()[:2000].decode('utf-8', 'ignore')
    except Exception:
        return ''
    try:
        obj = json.loads(body)
        d = obj.get('detail') if isinstance(obj, dict) else None
        if not d and isinstance(obj, dict):
            d = obj.get('message')
        if isinstance(d, list):
            return '; '.join(str(x.get('msg', x)) if isinstance(x, dict) else str(x) for x in d)[:300]
        if d:
            return str(d)[:300]
    except Exception:
        pass
    return body[:300]
