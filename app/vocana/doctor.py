"""
`vocana doctor` and the studio's "Check this computer": everything Vocana
depends on, one row each, with what to do about anything that is wrong.
Rows carry a code so the studio can show them in the reader's language;
`detail` is the English for the command line.
"""

import os
import platform
import shutil
import sys

from . import NAME, VERSION
from .paths import layout, writable, RUNTIME_DIR, installed_info


def report(data_dir=None, engine_url=None):
    rows = []

    def row(code, label, status, detail, **extra):
        rows.append(dict(extra, code=code, label=label, status=status, detail=detail))

    row('version', NAME, 'ok', '%s on %s %s' % (VERSION, platform.system(), platform.release()))
    v = sys.version_info
    row('python', 'Python', 'ok' if v >= (3, 10) else 'fail',
        '%d.%d.%d (%s)%s' % (v[0], v[1], v[2], 'bundled' if os.path.abspath(sys.executable).startswith(os.path.abspath(RUNTIME_DIR)) else sys.executable,
                             '' if v >= (3, 10) else ' - Vocana needs Python 3.10 or newer'))
    try:
        import numpy
        row('numpy', 'numpy', 'ok', numpy.__version__)
    except Exception as e:
        row('numpy', 'numpy', 'fail', 'missing (%s) - run Vocana.bat again, or: python vocana.py ensure-deps' % e)
    try:
        import e2k  # noqa: F401  (installed? the model check below says if it loads)
        from .kana import Kana
        ok = Kana.model() is not None
        row('e2k', 'e2k (English -> katakana)', 'ok' if ok else 'fail',
            'loaded' if ok else 'installed but the model did not load')
    except Exception as e:
        row('e2k', 'e2k (English -> katakana)', 'warn',
            'missing (%s): words not in words.json will be spelled letter by letter' % e)
    lay = layout(data_dir)
    row('mode', 'Mode', 'ok', ('installed' if lay.installed else 'portable') + (' (folder is read-only: files kept in Documents)' if lay.fallback else ''))
    row('data', 'Your files', 'ok' if writable(lay.data) else 'fail',
        lay.data if writable(lay.data) else lay.data + ' cannot be written to')
    try:
        free = shutil.disk_usage(lay.data).free
        row('disk', 'Free space', 'ok' if free > 200 * 2**20 else 'warn', '%.1f GB' % (free / 2**30))
    except OSError:
        pass
    try:
        from .config import load_moods, load_words
        cfg, w1 = load_moods(lay.moods)
        words, w2 = load_words(lay.words)
        bad = [w for w in w1 + w2 if w['code'] in ('moods_invalid', 'words_invalid')]
        row('config', 'words.json / moods.json', 'fail' if bad else ('warn' if w1 + w2 else 'ok'),
            bad[0]['message'] if bad else ('%d words, %d moods' % (len(words), len(cfg['moods']))
                                           + ('; %d notes' % len(w1 + w2) if w1 + w2 else '')))
        url = engine_url or cfg.get('engine')
    except Exception as e:
        row('config', 'words.json / moods.json', 'fail', str(e))
        url = engine_url
    from .engine import Engine
    eng = Engine(url or 'http://127.0.0.1:50021')
    ver = eng.alive(timeout=2)
    if ver:
        try:
            n = len(eng.speakers())
        except Exception:
            n = 0
        row('engine', 'VOICEVOX', 'ok', '%s at %s, %d characters' % (ver, eng.url, n), version=ver, characters=n)
    else:
        from .system import find_voicevox
        found = find_voicevox()
        where = found['engine'] or found['app']
        row('engine', 'VOICEVOX', 'warn',
            'not running at %s%s' % (eng.url, (' - installed at ' + where + '; the studio can start it') if where
                                     else ' - install it from voicevox.hiroshiba.jp, then open it'),
            installed=bool(where))
    info = installed_info()
    if info is not None:
        row('install', 'Installed copy', 'ok', info.get('dir') or '')
    return rows
