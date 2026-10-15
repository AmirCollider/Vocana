"""
The one entry point. Vocana.bat, Setup.bat, the Start-menu shortcut,
render_script.bat, say.bat, start.sh and vocana.py all run this file:

    python app/launch.py studio | setup | preflight | ensure-deps | <any vocana command>

It works on three kinds of Python:

  the bundled runtime   app/runtime/ in the release zip - an embeddable
                        CPython with numpy and e2k already inside. Nothing
                        to install; nothing on the PC is touched.
  any Python 3.10+      numpy and e2k are installed into app/lib/<python>
                        (ensure-deps), never into that Python itself, so
                        other programs on the PC are not affected.
  pythonw.exe           no console: problems are shown in a message box
                        and written to logs/vocana.log.
"""

import os
import platform
import subprocess
import sys

APP = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(APP)


def lib_dir():
    tag = '%s-%s-py%d%d' % (sys.platform, (platform.machine() or 'x').lower(), sys.version_info[0], sys.version_info[1])
    return os.path.join(APP, 'lib', tag)


def setup_path():
    if APP not in sys.path:
        sys.path.insert(0, APP)
    lib = lib_dir()
    if os.path.isdir(lib) and lib not in sys.path:
        sys.path.insert(1, lib)
    # pythonw.exe has no console: print() must still work.
    if sys.stdout is None or sys.stderr is None:
        devnull = open(os.devnull, 'w', encoding='utf-8')
        sys.stdout = sys.stdout or devnull
        sys.stderr = sys.stderr or devnull


def missing():
    out = []
    if sys.version_info < (3, 10):
        return ['python>=3.10']
    for mod in ('numpy', 'e2k'):
        try:
            __import__(mod)
        except Exception:
            out.append(mod)
    return out


TEXT = {
    'en': ('Vocana needs {m}.', 'Run Vocana.bat (Windows) or start.sh (macOS / Linux) once while online: '
           'it installs them into Vocana\'s own folder. Or download the release with everything inside from '
           'amircollider.com/vocana.'),
    'fa': ('Vocana به {m} نیاز دارد.', 'یک بار با اینترنت Vocana.bat (ویندوز) یا start.sh (مک/لینوکس) را اجرا کنید تا '
           'این‌ها در پوشه‌ی خود Vocana نصب شوند. یا نسخه‌ی کامل را از amircollider.com/vocana بگیرید.'),
    'ja': ('Vocana には {m} が必要です。', 'インターネットに接続した状態で Vocana.bat (Windows) または start.sh (macOS / Linux) '
           'を一度実行すると、Vocana のフォルダー内にインストールされます。または amircollider.com/vocana から'
           'すべて同梱の版をダウンロードしてください。'),
}


def lang():
    try:
        from vocana.installer import ui_lang
        return ui_lang()
    except Exception:
        return 'en'


def complain(m):
    lg = lang()
    head, body = TEXT.get(lg, TEXT['en'])
    text = head.format(m=', '.join(m)) + '\n\n' + body
    if sys.stdout is not None and getattr(sys.stdout, 'isatty', lambda: False)():
        print(text)
    try:
        from vocana.system import message_box
        message_box('Vocana', text, rtl=lg == 'fa')
    except Exception:
        print(text)


def ensure_deps(ask=False):
    """pip install the requirements into app/lib/<python> - not into the
    Python itself, so nothing else on the computer changes."""
    m = missing()
    if not m:
        print('numpy and e2k are ready.')
        return 0
    if 'python>=3.10' in m:
        print('Vocana needs Python 3.10 or newer (this is %d.%d).' % sys.version_info[:2])
        return 1
    if ask and sys.stdin is not None and sys.stdin.isatty():
        try:
            yes = input('Vocana needs %s. Install into %s now? [Y/n] ' % (', '.join(m), lib_dir())).strip().lower()
        except EOFError:
            yes = 'n'
        if yes not in ('', 'y', 'yes'):
            return 1
    lib = lib_dir()
    os.makedirs(lib, exist_ok=True)
    req = os.path.join(ROOT, 'requirements.txt')
    print('Installing %s into %s (about 25 MB, once)...' % (', '.join(m), lib))
    cmd = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-warn-script-location',
           '--upgrade', '--target', lib, '-r', req]
    try:
        r = subprocess.call(cmd)
    except OSError as e:
        print('Could not run pip: %s' % e)
        return 1
    if r != 0:
        print('\npip failed. Check the internet connection (a proxy or VPN may need to be on), then run this again.')
        return 1
    if lib not in sys.path:
        sys.path.insert(1, lib)
    import importlib
    importlib.invalidate_caches()
    m = missing()
    if m:
        print('Still missing: %s' % ', '.join(m))
        return 1
    print('Done.')
    return 0


def unblock():
    """Windows marks every file extracted from a downloaded zip as "from the
    internet" (a Zone.Identifier stream), and then asks "do you want to run
    this?" every time a .bat in it is opened. The folder is Vocana's own,
    so the mark is removed once, the way Properties -> Unblock would."""
    if sys.platform != 'win32':
        return
    marker = os.path.join(APP, '.unblocked')
    if os.path.exists(marker):
        return
    for rootdir, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ('renders', 'scripts', '.git', '__pycache__')]
        for f in files:
            try:
                os.remove(os.path.join(rootdir, f) + ':Zone.Identifier')
            except OSError:
                pass
    try:
        with open(marker, 'w') as f:
            f.write('Zone.Identifier marks removed once by launch.py\n')
    except OSError:
        pass


def start(argv, data):
    """Vocana.bat and Setup.bat: check (and if needed install) what is
    missing while there is a console to say so, then start the studio
    without a console window and return - the black window closes."""
    unblock()
    m = missing()
    if m:
        if 'python>=3.10' in m:
            print('Vocana needs Python 3.10 or newer (this is %d.%d).' % sys.version_info[:2])
            return 1
        if ensure_deps(ask=True) != 0:
            return 1
    exe = sys.executable
    if sys.platform == 'win32':
        w = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
        if os.path.isfile(w):
            exe = w
    cmd = [exe, '-X', 'utf8', os.path.abspath(__file__)] + data + ['studio', '--auto-exit'] + argv
    kw = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'cwd': ROOT}
    if sys.platform == 'win32':
        kw['creationflags'] = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kw['start_new_session'] = True
    try:
        proc = subprocess.Popen(cmd, **kw)
    except OSError as e:
        print('Could not start the studio: %s' % e)
        return 1
    import time
    for _ in range(25):                                        # a crash shows up within a second or two
        time.sleep(0.1)
        if proc.poll() is not None:
            break
    if proc.poll() not in (None, 0):
        print('The studio stopped while starting (exit %s).' % proc.returncode)
        try:
            from vocana.paths import layout
            lay = layout(data[1] if data else None)
            with open(os.path.join(lay.logs, 'crash.log'), encoding='utf-8') as f:
                print(f.read()[-3000:])
        except Exception:
            pass
        return 1
    print('Vocana is opening in your browser...')
    return 0


def split_data(argv):
    """(--data DIR as a list, the rest). --data may come before the command."""
    if len(argv) >= 2 and argv[0] == '--data':
        return argv[:2], argv[2:]
    return [], argv


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    setup_path()
    data, rest = split_data(argv)
    cmd = rest[0] if rest else 'studio'
    if cmd == 'start':
        return start(rest[1:], data)
    if cmd == 'ensure-deps':
        return ensure_deps(ask='--ask' in argv)
    if cmd == 'preflight':
        m = missing()
        if m:
            print('missing: ' + ', '.join(m))
            return 2
        return 0
    m = missing()
    if m and cmd not in ('doctor', 'install', 'uninstall', '--version', '-h', '--help'):
        complain(m)
        return 2
    if cmd == 'setup':
        argv = data + ['studio', '--page', 'install'] + rest[1:]
    elif not rest:
        argv = data + ['studio']
    from vocana.cli import main as cli_main
    try:
        return cli_main(argv)
    except Exception:
        import traceback
        tb = traceback.format_exc()
        try:
            from vocana.paths import layout
            lay = layout()
            os.makedirs(lay.logs, exist_ok=True)
            with open(os.path.join(lay.logs, 'crash.log'), 'a', encoding='utf-8') as f:
                f.write(tb + '\n')
        except Exception:
            pass
        try:
            from vocana.system import message_box
            message_box('Vocana', 'Vocana stopped because of an error:\n\n' + tb.strip().splitlines()[-1] +
                        '\n\nDetails are in logs/crash.log.')
        except Exception:
            pass
        print(tb)
        return 1


if __name__ == '__main__':
    sys.exit(main())
