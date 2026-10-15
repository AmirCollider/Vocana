"""
"Is there a newer Vocana?" - once a day, if the user leaves it switched on.

One GET to amircollider.com/vocana/version.json, nothing in it but the
request itself (no id, no usage data, no script text). The answer is cached
in settings.json, so the studio opening ten times a day asks once. Any
failure - offline, blocked, slow - is silent: an update check must never be
the reason the studio did not open.

Unlike the engine requests, this one DOES use the system proxy: it is the
one request that goes to the internet, and a user behind a proxy reaches
the internet only through it.
"""

import json
import re
import threading
import time
import urllib.request

from . import VERSION, UPDATE_URL

DAY = 24 * 3600


def parse_version(v):
    parts = re.findall(r'\d+', str(v))[:3]
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def newer(remote, local=VERSION):
    try:
        return parse_version(remote) > parse_version(local)
    except Exception:
        return False


def fetch(timeout=5):
    req = urllib.request.Request(UPDATE_URL, headers={'User-Agent': 'Vocana/%s' % VERSION,
                                                      'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read(65536).decode('utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('version'), str):
        raise ValueError('not a version document')
    return data


class Checker:
    def __init__(self, settings_get, settings_put):
        self.get = settings_get
        self.put = settings_put
        self.result = None
        self._lock = threading.Lock()

    def cached(self):
        s = self.get()
        c = s.get('_update') or {}
        return c if isinstance(c, dict) else {}

    def info(self):
        c = self.cached()
        if not c.get('version'):
            return {'available': False, 'checked': c.get('checked')}
        return {'available': newer(c['version']), 'version': c['version'], 'url': c.get('url'),
                'download': c.get('download'), 'notes': c.get('notes'), 'date': c.get('date'),
                'checked': c.get('checked')}

    def maybe_check(self, force=False):
        s = self.get()
        if not force and not s.get('check_updates', True):
            return
        c = self.cached()
        if not force and c.get('checked') and time.time() - float(c['checked']) < DAY:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        if not self._lock.acquire(False):
            return
        try:
            d = fetch()
            keep = {k: d.get(k) for k in ('version', 'url', 'download', 'notes', 'date')}
            # The studio opens 'url' in a window of its own origin, so an
            # address that is not plain https (javascript:, data:, file:) is
            # dropped here rather than trusted because it came from our site.
            for k in ('url', 'download'):
                if not (isinstance(keep[k], str) and keep[k].startswith('https://') and len(keep[k]) < 500):
                    keep[k] = None
            keep['checked'] = time.time()
            self.put({'_update': keep})
        except Exception:
            c = self.cached()
            c['checked'] = time.time()
            try:
                self.put({'_update': c})
            except Exception:
                pass
        finally:
            self._lock.release()
