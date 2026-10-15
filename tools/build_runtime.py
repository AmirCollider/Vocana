"""
Builds app/runtime: the Windows Python that ships inside the release zip.

    python tools/build_runtime.py [--cache DIR]

Works on any OS (the release is usually made on Linux). Steps:
  1. download the three files in app/setup/runtime.lock.json, or take
     them from --cache, and check every SHA-256;
  2. unpack the embeddable CPython into app/runtime;
  3. unpack the numpy and e2k wheels into app/runtime/Lib/site-packages
     (a wheel is a zip laid out for exactly that);
  4. write python313._pth: the runtime's own stdlib, its site-packages,
     and app/ itself - and NOT "import site", so nothing from the user's
     profile (a user site-packages, a stray .pth) can change what runs;
  5. remove numpy's test suites (8 MB nobody runs) and byte-compile
     everything with unchecked-hash .pyc files, which stay valid when a
     zip tool changes the files' timestamps.

The same files are what app/setup/get-runtime.ps1 fetches on a Windows PC
that got Vocana without its runtime.
"""

import argparse
import compileall
import hashlib
import json
import os
import shutil
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOCK = os.path.join(ROOT, 'app', 'setup', 'runtime.lock.json')
RUNTIME = os.path.join(ROOT, 'app', 'runtime')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(entry, cache):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, entry['name'])
    if not os.path.isfile(path) or sha256(path) != entry['sha256']:
        print('downloading', entry['url'])
        tmp = path + '.part'
        with urllib.request.urlopen(entry['url'], timeout=120) as r, open(tmp, 'wb') as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, path)
    got = sha256(path)
    if got != entry['sha256']:
        raise SystemExit('%s: SHA-256 is %s, expected %s' % (entry['name'], got, entry['sha256']))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=os.path.join(ROOT, '.cache', 'runtime'))
    a = ap.parse_args()
    with open(LOCK, encoding='utf-8') as f:
        lock = json.load(f)
    paths = {e['name']: fetch(e, a.cache) for e in lock['files']}
    if os.path.isdir(RUNTIME):
        shutil.rmtree(RUNTIME)
    os.makedirs(RUNTIME)
    site = os.path.join(RUNTIME, 'Lib', 'site-packages')
    os.makedirs(site)
    for e in lock['files']:
        with zipfile.ZipFile(paths[e['name']]) as z:
            target = RUNTIME if e['kind'] == 'python' else site
            for info in z.infolist():
                name = info.filename
                if name.startswith('/') or '..' in name.split('/'):
                    raise SystemExit('unsafe path in %s: %s' % (e['name'], name))
                if e['kind'] == 'wheel' and '.data/' in name:
                    continue                      # scripts and headers: not needed
                z.extract(info, target)
    ver = lock['python'].split('.')
    pth = os.path.join(RUNTIME, 'python%s%s._pth' % (ver[0], ver[1]))
    with open(pth, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('# Written by tools/build_runtime.py. No "import site": nothing outside\n')
        f.write('# this folder can change which modules Vocana loads.\n')
        f.write('\n'.join(lock['pth']) + '\n')
    removed = 0
    for rootdir, dirs, _files in os.walk(os.path.join(site, 'numpy')):
        for d in list(dirs):
            if d == 'tests':
                shutil.rmtree(os.path.join(rootdir, d))
                dirs.remove(d)
                removed += 1
    if sys.version_info[:2] == tuple(int(x) for x in ver[:2]):
        compileall.compile_dir(site, quiet=1, workers=0,
                               invalidation_mode=compileall.py_compile.PycInvalidationMode.UNCHECKED_HASH)
    else:
        print('note: this Python is %d.%d, the runtime %s.%s - .pyc files not made' % (sys.version_info[0], sys.version_info[1], ver[0], ver[1]))
    total = sum(os.path.getsize(os.path.join(r, f)) for r, _d, fs in os.walk(RUNTIME) for f in fs)
    print('runtime ready: %s (%.1f MB, %d test folders removed)' % (RUNTIME, total / 2**20, removed))


if __name__ == '__main__':
    main()
