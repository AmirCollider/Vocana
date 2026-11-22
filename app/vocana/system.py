"""
The operating system: finding and starting VOICEVOX, opening folders and
browser windows, and telling the user about a problem when there is no
console to print it in.

Starting VOICEVOX
  The VOICEVOX app carries its engine in a folder next to it
  (VOICEVOX/vv-engine/run.exe). Started on its own, the engine has no
  window at all - Vocana starts that, hidden, and stops it again on quit.
  When only the app can be found, the app is started instead (its editor
  window opens; closing it stops the engine). Either can be switched off.
"""

import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import webbrowser

WINDOWS = sys.platform == 'win32'
MAC = sys.platform == 'darwin'

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

# Official VOICEVOX engine UUIDs (product edition and OSS edition).
DEFAULT_ENGINE_UUIDS = (
    '074fc39e-678b-4c13-8916-ffca8d505d1d',
    'c7b58856-bd56-4aa1-afb7-b8415f824b06',
)


# ==================================================================
# VOICEVOX
# ==================================================================
def voicevox_candidates():
    """Places the VOICEVOX app or engine is installed by default."""
    out = []
    if WINDOWS:
        for base in (os.environ.get('LOCALAPPDATA'), os.environ.get('ProgramFiles'),
                     os.environ.get('ProgramW6432'), os.environ.get('ProgramFiles(x86)')):
            if base:
                out.append(os.path.join(base, 'Programs', 'VOICEVOX', 'VOICEVOX.exe'))
                out.append(os.path.join(base, 'VOICEVOX', 'VOICEVOX.exe'))
    elif MAC:
        out += ['/Applications/VOICEVOX.app', os.path.expanduser('~/Applications/VOICEVOX.app')]
    else:
        home = os.path.expanduser('~')
        out += sorted(glob.glob(os.path.join(home, '.voicevox', '*', 'VOICEVOX*.AppImage')))
        out += sorted(glob.glob(os.path.join(home, 'Applications', 'VOICEVOX*.AppImage')))
        out += sorted(glob.glob(os.path.join(home, '.voicevox', 'VOICEVOX.AppImage')))
    return out


def vvpp_engine_roots():
    """Places VOICEVOX 0.26+ installs its separated engine (vvpp-engines)."""
    out = []
    if WINDOWS:
        appdata = os.environ.get('APPDATA')
        if appdata:
            out.append(os.path.join(appdata, 'voicevox', 'vvpp-engines'))
    elif MAC:
        out.append(os.path.expanduser('~/Library/Application Support/voicevox/vvpp-engines'))
    else:
        xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        out.append(os.path.join(xdg, 'voicevox', 'vvpp-engines'))
    return out


def _ver_key(v):
    nums = [int(x) for x in re.findall(r'\d+', str(v or ''))[:3]]
    return tuple(nums) + (0,) * (3 - len(nums))


def _engine_in_dir(folder):
    """(exe_path, uuid, version_tuple) for one engine directory, or None."""
    if not folder or not os.path.isdir(folder):
        return None
    manifest_path = os.path.join(folder, 'engine_manifest.json')
    uuid, ver, cmd_exe = '', (), None
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding='utf-8-sig') as f:
                m = json.load(f)
            if isinstance(m, dict):
                uuid = str(m.get('uuid') or '')
                ver = _ver_key(m.get('version'))
                cmd = m.get('command')
                if isinstance(cmd, str) and cmd.strip():
                    try:
                        parts = shlex.split(cmd, posix=not WINDOWS)
                    except ValueError:
                        parts = cmd.split()
                    if parts:
                        c = os.path.join(folder, parts[0])
                        if os.path.isfile(c):
                            cmd_exe = c
                        elif WINDOWS and not c.lower().endswith('.exe') and os.path.isfile(c + '.exe'):
                            cmd_exe = c + '.exe'
        except (OSError, ValueError):
            pass
    if cmd_exe:
        return cmd_exe, uuid, ver
    for name in ('run.exe', 'run'):
        c = os.path.join(folder, name)
        if os.path.isfile(c):
            return c, uuid, ver
    return None


def find_vvpp_engine(roots=None):
    """Best VOICEVOX engine installed in vvpp-engines/ (VOICEVOX 0.26+), or None.
    Prefers official VOICEVOX engines over third-party VVPP engines, and newer
    versions over older ones."""
    best = None
    for root in (vvpp_engine_roots() if roots is None else roots):
        if not root or not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        for name in entries:
            if name.startswith('.'):
                continue
            hit = _engine_in_dir(os.path.join(root, name))
            if not hit:
                continue
            exe, uuid, ver = hit
            # Official default engine gets priority 2, OSS engine 1, other VVPP 0.
            if uuid == DEFAULT_ENGINE_UUIDS[0] or name.endswith('+' + DEFAULT_ENGINE_UUIDS[0]):
                rank = 2
            elif uuid == DEFAULT_ENGINE_UUIDS[1] or name.endswith('+' + DEFAULT_ENGINE_UUIDS[1]):
                rank = 1
            else:
                rank = 0
            key = (rank, ver)
            if best is None or key > best[0]:
                best = (key, exe, ver)
    return (best[1], best[2]) if best else (None, ())


def engine_next_to(app_path):
    """VOICEVOX/vv-engine/run(.exe) beside the app, if it is there."""
    if not app_path:
        return None
    if os.path.isdir(app_path) and app_path.endswith('.app'):
        cand = os.path.join(app_path, 'Contents', 'Resources', 'vv-engine', 'run')
        return cand if os.path.isfile(cand) else None
    folder = os.path.dirname(app_path) if os.path.isfile(app_path) else app_path
    for sub in ('vv-engine', 'engine', '.'):
        hit = _engine_in_dir(os.path.join(folder, sub))
        if hit:
            return hit[0]
    return None


def find_voicevox(user_path='', vvpp_roots=None):
    """{'app': path or None, 'engine': path or None}. A user-given path may
    be the app, the engine's run.exe, or the folder holding either."""
    found = {'app': None, 'engine': None}
    user_engine = False
    paths = []
    if user_path:
        p = os.path.expandvars(os.path.expanduser(user_path.strip().strip('"')))
        paths.append((p, True))
    paths += [(p, False) for p in voicevox_candidates()]
    for p, from_user in paths:
        if not p or not os.path.exists(p):
            continue
        base = os.path.basename(p).lower()
        if base in ('run.exe', 'run') and os.path.isfile(p):
            if not found['engine']:
                found['engine'] = p
                user_engine = from_user
            continue
        if os.path.isdir(p) and not p.endswith('.app'):
            for name in ('VOICEVOX.exe', 'voicevox.exe'):
                if os.path.isfile(os.path.join(p, name)):
                    found['app'] = found['app'] or os.path.join(p, name)
            eng = engine_next_to(p)
            if eng and not found['engine']:
                found['engine'] = eng
                user_engine = from_user
            continue
        found['app'] = found['app'] or p
        eng = engine_next_to(p)
        if eng and not found['engine']:
            found['engine'] = eng
            user_engine = from_user
        if found['app'] and found['engine']:
            break
    # VOICEVOX 0.26+ separates its engine into userData/vvpp-engines/. Use it
    # when no bundled vv-engine was found, or when the separated engine is newer
    # (unless the user explicitly chose an engine path in Settings).
    if not user_engine:
        vvpp_exe, vvpp_ver = find_vvpp_engine(vvpp_roots)
        if vvpp_exe:
            if not found['engine']:
                found['engine'] = vvpp_exe
            else:
                cur_hit = _engine_in_dir(os.path.dirname(found['engine']))
                cur_ver = cur_hit[2] if cur_hit else ()
                if vvpp_ver and (not cur_ver or vvpp_ver >= cur_ver):
                    found['engine'] = vvpp_exe
    return found


def start_voicevox(mode='auto', user_path='', port=50021):
    """Start the engine hidden (mode 'engine'), or the app ('app'); 'auto'
    prefers the engine. Returns (kind, Popen or None) or (None, reason)."""
    found = find_voicevox(user_path)
    order = {'engine': ['engine'], 'app': ['app'], 'auto': ['engine', 'app']}.get(mode, [])
    for kind in order:
        path = found.get(kind)
        if not path:
            continue
        try:
            if kind == 'engine':
                args = [path, '--host', '127.0.0.1', '--port', str(port)]
                kw = {'cwd': os.path.dirname(path), 'stdin': subprocess.DEVNULL,
                      'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
                if WINDOWS:
                    kw['creationflags'] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
                else:
                    kw['start_new_session'] = True
                return kind, subprocess.Popen(args, **kw)
            if MAC and path.endswith('.app'):
                subprocess.Popen(['open', '-a', path])
                return kind, None
            kw = {'cwd': os.path.dirname(path)}
            if WINDOWS:
                kw['creationflags'] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            else:
                kw['start_new_session'] = True
            subprocess.Popen([path], **kw)
            return kind, None
        except OSError:
            continue
    return None, ('not_found' if not any(found.values()) else 'failed')


def stop_process(proc):
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception:
        pass


# ==================================================================
# Folders, files and windows
# ==================================================================
def open_path(path):
    """Show a folder (or a file's folder) in Explorer / Finder / the file manager."""
    if WINDOWS:
        if os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
        else:
            os.startfile(os.path.normpath(path))      # noqa: S606 - a local folder the user owns
        return True
    opener = 'open' if MAC else shutil.which('xdg-open')
    if not opener:
        return False
    subprocess.Popen([opener, path if os.path.isdir(path) else os.path.dirname(path)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def app_browser():
    """Edge or Chrome, for an --app window (no tabs, no address bar)."""
    names = []
    if WINDOWS:
        for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'),
                     os.environ.get('ProgramW6432'), os.environ.get('LOCALAPPDATA')):
            if base:
                names.append(os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe'))
                names.append(os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'))
    elif MAC:
        names += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
    else:
        for n in ('microsoft-edge', 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
            p = shutil.which(n)
            if p:
                names.append(p)
    for p in names:
        if p and os.path.isfile(p):
            return p
    return None


def open_browser(url, app_window=True):
    if app_window:
        exe = app_browser()
        if exe:
            try:
                kw = {'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'stdin': subprocess.DEVNULL}
                if WINDOWS:
                    kw['creationflags'] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                else:
                    kw['start_new_session'] = True
                subprocess.Popen([exe, '--app=' + url, '--window-size=1360,880'], **kw)
                return 'app'
            except OSError:
                pass
    try:
        if webbrowser.open(url):
            return 'browser'
    except Exception:
        pass
    return None


def message_box(title, text, rtl=False, kind='error', ask=False):
    """A native message box on Windows (there is no console under pythonw);
    stderr elsewhere. With ask=True, returns True for Yes."""
    if WINDOWS:
        try:
            import ctypes
            flags = {'error': 0x10, 'warn': 0x30, 'info': 0x40}.get(kind, 0x40)
            flags |= 0x4 if ask else 0x0                      # MB_YESNO
            if rtl:
                flags |= 0x00100000 | 0x00080000              # MB_RTLREADING | MB_RIGHT
            flags |= 0x00010000                               # MB_SETFOREGROUND
            r = ctypes.windll.user32.MessageBoxW(None, text, title, flags)
            return r == 6 if ask else True
        except Exception:
            pass
    try:
        sys.stderr.write('%s: %s\n' % (title, text))
    except Exception:
        pass
    return False
