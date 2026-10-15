"""
Makes the two zips Vocana is published as:

  dist/Vocana-<version>.zip         what users download: everything, with the
                                    Windows Python runtime inside (runs on a
                                    bare Windows PC; start.sh on macOS/Linux)
  dist/Vocana-<version>-source.zip  the same without the runtime, plus tests/
                                    and tools/ - what goes in the repository

    python tools/make_release.py [--skip-tests] [--cache DIR]

It rebuilds Guide.html and app/runtime first, runs the tests (the
regression test needs VOICEVOX 0.25.2 on 127.0.0.1:50021, else it is
skipped), and writes SHA256SUMS.txt next to the zips.
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app'))
from vocana import VERSION  # noqa: E402

TOP_FILES = ['Vocana.bat', 'Setup.bat', 'render_script.bat', 'say.bat', 'start.sh', 'Vocana.command', 'vocana.py',
             'Guide.html', 'README.md', 'LICENSE.txt', 'THIRD-PARTY-NOTICES.txt', 'CHANGELOG.md', 'requirements.txt']
SKIP_NAMES = {'__pycache__', 'installed.json', '.unblocked', '.DS_Store'}
EXEC = {'start.sh', 'Vocana.command'}


def run(cmd):
    print('$', ' '.join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def add_tree(z, src, arc, skip_dirs=()):
    runtime = os.path.join(ROOT, 'app', 'runtime')
    for rootdir, dirs, files in os.walk(src):
        # The runtime's __pycache__ folders are kept: build_runtime.py made
        # them with unchecked hashes, so a first start does not compile numpy
        # into a folder that may not be writable. Everywhere else a .pyc is
        # this machine's leftover.
        in_runtime = os.path.commonpath([rootdir, runtime]) == runtime
        dirs[:] = sorted(d for d in dirs
                         if (d not in SKIP_NAMES or (in_runtime and d == '__pycache__'))
                         and os.path.join(rootdir, d) not in skip_dirs)
        for f in sorted(files):
            if f in SKIP_NAMES or f.endswith('.part') or (f.endswith('.pyc') and not in_runtime):
                continue
            full = os.path.join(rootdir, f)
            add_file(z, full, os.path.join(arc, os.path.relpath(full, src)).replace(os.sep, '/'))


def add_file(z, full, arcname):
    info = zipfile.ZipInfo(arcname, time.localtime(os.path.getmtime(full))[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if os.path.basename(full) in EXEC else 0o644
    info.external_attr = (0o100000 | mode) << 16
    with open(full, 'rb') as f:
        z.writestr(info, f.read())


def build(path, with_runtime, with_dev):
    top = 'Vocana'
    app = os.path.join(ROOT, 'app')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in TOP_FILES:
            add_file(z, os.path.join(ROOT, f), '%s/%s' % (top, f))
        skip = [os.path.join(app, 'lib')]
        if not with_runtime:
            skip.append(os.path.join(app, 'runtime'))
        add_tree(z, app, top + '/app', skip_dirs=skip)
        if not with_dev:
            # The user's files, as a fresh copy of the folder has them. The
            # source zip is the repository and leaves them out: the first
            # start copies them from app/vocana/defaults, and .gitignore
            # keeps a developer's own edits out of commits.
            d = os.path.join(app, 'vocana', 'defaults')
            add_file(z, os.path.join(d, 'words.json'), top + '/words.json')
            add_file(z, os.path.join(d, 'moods.json'), top + '/moods.json')
            add_tree(z, os.path.join(d, 'scripts'), top + '/scripts')
        add_tree(z, os.path.join(ROOT, 'renders', 'Sample'), top + '/renders/Sample')
        if with_dev:
            add_tree(z, os.path.join(ROOT, 'tests'), top + '/tests')
            add_tree(z, os.path.join(ROOT, 'tools'), top + '/tools')
            add_file(z, os.path.join(ROOT, '.gitignore'), top + '/.gitignore')
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-tests', action='store_true')
    ap.add_argument('--cache', help='where build_runtime.py keeps its downloads')
    a = ap.parse_args()
    run([sys.executable, 'tools/build_guide.py'])
    run([sys.executable, 'tools/build_runtime.py'] + (['--cache', a.cache] if a.cache else []))
    if not a.skip_tests:
        run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'])
    dist = os.path.join(ROOT, 'dist')
    if os.path.isdir(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)
    out = [build(os.path.join(dist, 'Vocana-%s.zip' % VERSION), True, False),
           build(os.path.join(dist, 'Vocana-%s-source.zip' % VERSION), False, True)]
    with open(os.path.join(dist, 'SHA256SUMS.txt'), 'w', encoding='ascii', newline='\n') as f:
        for p in out:
            f.write('%s  %s\n' % (sha256(p), os.path.basename(p)))
            print('%s  %.1f MB' % (os.path.basename(p), os.path.getsize(p) / 2**20))


if __name__ == '__main__':
    main()
