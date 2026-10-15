"""
Installing for one Windows user, and uninstalling again. No administrator
rights are needed and nothing outside the user's own profile is touched:

  program      %LOCALAPPDATA%\\Programs\\Vocana         (replaced on update)
  your files   Documents\\Vocana                         (never deleted)
  Start menu   ...\\Start Menu\\Programs\\Vocana.lnk
  Desktop      Vocana.lnk                               (optional)
  Apps list    HKCU\\...\\Uninstall\\Vocana              (so Windows can remove it)

The portable folder keeps working after an install; the two simply have
separate files. An install never overwrites a file in Documents\\Vocana:
words, moods, scripts and renders from the portable folder are copied
there only when the installed copy has none of its own yet.

The shortcut and the folder removal go through Windows PowerShell, with
every path passed in an environment variable rather than spliced into a
command line: a user name with a space, an apostrophe or Persian letters
in it is just a value then, never something to quote.
"""

import base64
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

from . import NAME, VERSION, PUBLISHER, HOMEPAGE
from .paths import (ROOT_DIR, APP_DIR, RUNTIME_DIR, WINDOWS, documents_dir, known_folder,
                    installed_info, layout as get_layout)

UNINSTALL_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\Vocana'
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

# Not copied into the installed program folder: the user's files go to
# Documents\Vocana instead, and the rest is per-copy state.
SKIP_TOP = {'renders', 'scripts', 'words.json', 'moods.json', 'settings.json', 'logs', 'tests', 'tools',
            '.cache', '.vocana-instance.json', '.git', '.github'}

MESSAGES = {
    'en': {
        'confirm': 'Remove Vocana from this computer?\n\nYour scripts, words and renders in\n{data}\nare kept.',
        'done': 'Vocana has been removed. Your files are still in:\n{data}',
        'manual': 'Vocana was removed from the Start menu and the Apps list, but its folder could not be deleted:\n{dir}\nYou can delete it yourself.',
        'not_installed': 'This copy of Vocana is not an installed one - there is nothing to uninstall. To remove a portable folder, just delete it.',
        'windows_only': 'Installing is for Windows. On this system, run Vocana from its folder (start.sh).',
    },
    'fa': {
        'confirm': 'Vocana از این کامپیوتر حذف شود؟\n\nاسکریپت‌ها، واژه‌نامه و خروجی‌های شما در این پوشه می‌مانند:\n{data}',
        'done': 'Vocana حذف شد. فایل‌های شما هنوز این‌جا هستند:\n{data}',
        'manual': 'Vocana از منوی استارت و فهرست برنامه‌ها حذف شد، ولی پوشه‌اش پاک نشد:\n{dir}\nمی‌توانید خودتان پاکش کنید.',
        'not_installed': 'این نسخه‌ی Vocana نصب‌شده نیست و چیزی برای حذف ندارد. نسخه‌ی پرتابل را کافی است پوشه‌اش را پاک کنید.',
        'windows_only': 'نصب فقط برای ویندوز است. روی این سیستم Vocana را از پوشه‌اش اجرا کنید (start.sh).',
    },
    'ja': {
        'confirm': 'このコンピューターから Vocana を削除しますか？\n\nスクリプト・辞書・書き出したファイルは次のフォルダーに残ります:\n{data}',
        'done': 'Vocana を削除しました。あなたのファイルは次の場所に残っています:\n{data}',
        'manual': 'スタートメニューとアプリ一覧からは削除しましたが、フォルダーを削除できませんでした:\n{dir}\n手動で削除してください。',
        'not_installed': 'この Vocana はインストール版ではないため、アンインストールするものはありません。ポータブル版はフォルダーごと削除してください。',
        'windows_only': 'インストールは Windows 用です。このシステムではフォルダーから起動してください (start.sh)。',
    },
}


def ui_lang(data_dir=None):
    try:
        from .config import load_settings
        lay = get_layout(data_dir)
        lang = load_settings(lay.settings).get('lang', 'auto')
        if lang in MESSAGES:
            return lang
    except Exception:
        pass
    if WINDOWS:
        try:
            import ctypes
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return {0x29: 'fa', 0x11: 'ja'}.get(primary, 'en')
        except Exception:
            pass
    return 'en'


def msg(key, lang, **kw):
    return MESSAGES.get(lang, MESSAGES['en'])[key].format(**kw)


def default_target():
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    return os.path.join(base, 'Programs', NAME)


def data_target():
    return os.path.join(documents_dir(), NAME)


def bundled_python(folder, windowless=True):
    """The interpreter an installed copy runs on: its own runtime when it has
    one, otherwise the Python running right now."""
    exe = 'pythonw.exe' if windowless else 'python.exe'
    cand = os.path.join(folder, 'app', 'runtime', exe)
    if os.path.isfile(cand):
        return cand
    here = os.path.dirname(sys.executable)
    cand = os.path.join(here, exe)
    return cand if os.path.isfile(cand) else sys.executable


def info():
    me = installed_info()
    return {'windows': WINDOWS, 'installed': me is not None, 'can_install': WINDOWS and me is None,
            'target': default_target() if WINDOWS else None, 'data': data_target(),
            'runtime': os.path.isdir(RUNTIME_DIR), 'existing': os.path.isfile(os.path.join(default_target(), 'app', 'installed.json')) if WINDOWS else False,
            'this': me}


def powershell(script, env):
    """Run a PowerShell snippet; values arrive in $env:VC_* variables."""
    enc = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    full = dict(os.environ)
    full.update({k: str(v) for k, v in env.items()})
    exe = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    if not os.path.isfile(exe):
        exe = 'powershell.exe'
    r = subprocess.run([exe, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', enc],
                       env=full, capture_output=True, timeout=120, creationflags=CREATE_NO_WINDOW)
    return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')


# Paths come from Python (which knows the user's real Start menu and
# Desktop, wherever they were moved); PowerShell only makes the files.
SHORTCUT_PS = r'''
$ErrorActionPreference = 'Stop'
$ws = New-Object -ComObject WScript.Shell
foreach ($p in @($env:VC_LNK1, $env:VC_LNK2)) {
  if (-not $p) { continue }
  $s = $ws.CreateShortcut($p)
  $s.TargetPath = $env:VC_TARGET
  $s.Arguments = $env:VC_ARGS
  $s.WorkingDirectory = $env:VC_WD
  $s.IconLocation = $env:VC_ICON + ',0'
  $s.Description = 'Vocana - plain English, any VOICEVOX voice'
  $s.Save()
}
'''

REMOVE_PS = r'''
Start-Sleep -Seconds 3
for ($i = 0; $i -lt 10; $i++) {
  try { Remove-Item -LiteralPath $env:VC_DEL -Recurse -Force -ErrorAction Stop; break } catch { Start-Sleep -Seconds 2 }
}
'''


def stop_running(data_dir):
    """Ask a studio that runs on this data folder to quit (an update over a
    running installed copy would fail on its locked files)."""
    import urllib.request
    try:
        with open(os.path.join(data_dir, '.vocana-instance.json'), encoding='utf-8') as f:
            inst = json.load(f)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request('http://127.0.0.1:%d/api/quit' % int(inst['port']), data=b'{}', method='POST',
                                     headers={'Content-Type': 'application/json', 'X-Vocana-Token': inst.get('token', '')})
        opener.open(req, timeout=2).read()
        time.sleep(2.5)
        return True
    except Exception:
        return False


def copy_user_files(src_root, data):
    """The portable folder's own files -> Documents\\Vocana, never overwriting."""
    os.makedirs(data, exist_ok=True)
    for name in ('words.json', 'moods.json'):
        s, d = os.path.join(src_root, name), os.path.join(data, name)
        if os.path.isfile(s) and not os.path.exists(d):
            shutil.copy2(s, d)
    for sub in ('scripts', 'renders'):
        s, d = os.path.join(src_root, sub), os.path.join(data, sub)
        if not os.path.isdir(s):
            continue
        for rootdir, dirs, files in os.walk(s):
            rel = os.path.relpath(rootdir, s)
            target = os.path.join(d, rel) if rel != '.' else d
            os.makedirs(target, exist_ok=True)
            for f in files:
                if f.endswith('.part'):
                    continue
                tf = os.path.join(target, f)
                if not os.path.exists(tf):
                    shutil.copy2(os.path.join(rootdir, f), tf)


def install(job=None, desktop=True, start_menu=True, lang='en', target=None):
    def step(name, i, total=6):
        if job is not None:
            job.progress = {'stage': name, 'i': i, 'total': total}
    if not WINDOWS:
        raise RuntimeError(msg('windows_only', lang))
    if installed_info() is not None:
        raise RuntimeError('This copy is already the installed one.')
    target = os.path.abspath(target or default_target())
    if os.path.basename(target.rstrip('\\/')).lower() != NAME.lower():
        target = os.path.join(target, NAME)
    data = data_target()
    if os.path.normcase(os.path.realpath(target)) == os.path.normcase(os.path.realpath(ROOT_DIR)):
        raise RuntimeError('This folder is the install location itself.')

    step('stop', 1)
    stop_running(data)

    step('copy', 2)
    old_marker = os.path.join(target, 'app', 'installed.json')
    if os.path.isfile(old_marker):
        # An earlier install: ours to replace. Only app/ and the top-level
        # program files - nothing else that may have been put in there.
        for attempt in range(3):
            try:
                shutil.rmtree(os.path.join(target, 'app'))
                break
            except OSError:
                if attempt == 2:
                    raise RuntimeError('The installed Vocana is still running. Quit it (or restart Windows) and try again.')
                time.sleep(2)
    os.makedirs(target, exist_ok=True)

    def ignore(folder, names):
        skip = {'__pycache__'}
        if os.path.realpath(folder) == os.path.realpath(ROOT_DIR):
            skip |= SKIP_TOP
        if os.path.realpath(folder) == os.path.realpath(APP_DIR):
            skip |= {'installed.json'}
        return [n for n in names if n in skip or n.endswith('.part') or n.endswith('.pyc')]
    for name in os.listdir(ROOT_DIR):
        if name in SKIP_TOP:
            continue
        s, d = os.path.join(ROOT_DIR, name), os.path.join(target, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, ignore=ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
    os.makedirs(os.path.join(target, 'renders'), exist_ok=True)
    if os.path.isdir(os.path.join(ROOT_DIR, 'renders', 'Sample')):
        shutil.copytree(os.path.join(ROOT_DIR, 'renders', 'Sample'), os.path.join(target, 'renders', 'Sample'),
                        dirs_exist_ok=True)

    step('files', 3)
    copy_user_files(ROOT_DIR, data)

    step('shortcuts', 4)
    pyw = bundled_python(target, True)
    launch = os.path.join(target, 'app', 'launch.py')
    args = '-X utf8 "%s" studio --auto-exit' % launch
    icon = os.path.join(target, 'app', 'brand', 'vocana.ico')
    shortcuts, problem = [], None
    wanted = []
    if start_menu:
        folder = known_folder('Programs') or os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows',
                                                         'Start Menu', 'Programs')
        wanted.append(os.path.join(folder, NAME + '.lnk'))
    if desktop:
        folder = known_folder('Desktop') or os.path.join(os.path.expanduser('~'), 'Desktop')
        wanted.append(os.path.join(folder, NAME + '.lnk'))
    if wanted:
        try:
            code, out, err = powershell(SHORTCUT_PS, {'VC_TARGET': pyw, 'VC_ARGS': args, 'VC_WD': target, 'VC_ICON': icon,
                                                      'VC_LNK1': wanted[0], 'VC_LNK2': wanted[1] if len(wanted) > 1 else ''})
            shortcuts = [p for p in wanted if os.path.isfile(p)]
            if len(shortcuts) < len(wanted):
                problem = (err or out).strip()[:300] or 'PowerShell did not create them (exit %d)' % code
        except Exception as e:
            problem = str(e)

    step('register', 5)
    marker = {'version': VERSION, 'installed_at': datetime.datetime.now().isoformat(timespec='seconds'),
              'dir': target, 'data_dir': data, 'shortcuts': shortcuts, 'python': pyw}
    with open(os.path.join(target, 'app', 'installed.json'), 'w', encoding='utf-8') as f:
        json.dump(marker, f, ensure_ascii=False, indent=1)
    register(target, pyw)

    step('done', 6)
    return {'dir': target, 'data': data, 'shortcuts': shortcuts, 'shortcut_problem': problem,
            'launch': [pyw, '-X', 'utf8', launch, 'studio', '--auto-exit']}


def folder_size_kb(folder):
    total = 0
    for rootdir, _d, files in os.walk(folder):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(rootdir, f))
            except OSError:
                pass
    return int(total / 1024)


def register(target, pyw):
    import winreg
    launch = os.path.join(target, 'app', 'launch.py')
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, winreg.KEY_WRITE) as k:
        def sz(name, value):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)

        def dw(name, value):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, int(value))
        sz('DisplayName', NAME)
        sz('DisplayVersion', VERSION)
        sz('Publisher', PUBLISHER)
        sz('DisplayIcon', os.path.join(target, 'app', 'brand', 'vocana.ico'))
        sz('InstallLocation', target)
        sz('UninstallString', '"%s" -X utf8 "%s" uninstall' % (pyw, launch))
        sz('QuietUninstallString', '"%s" -X utf8 "%s" uninstall --silent' % (pyw, launch))
        sz('URLInfoAbout', HOMEPAGE)
        sz('HelpLink', HOMEPAGE)
        sz('InstallDate', datetime.date.today().strftime('%Y%m%d'))
        dw('NoModify', 1)
        dw('NoRepair', 1)
        dw('EstimatedSize', folder_size_kb(target))


def unregister():
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except OSError:
        pass


def launch_detached(cmd):
    kw = {'cwd': os.path.dirname(cmd[0]) or None, 'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL,
          'stderr': subprocess.DEVNULL}
    if WINDOWS:
        kw['creationflags'] = DETACHED_PROCESS | 0x00000200
    else:
        kw['start_new_session'] = True
    subprocess.Popen(cmd, **kw)


def uninstall(keep_running=False):
    """Remove shortcuts, the Apps entry and (after this process exits) the
    program folder. The user's Documents\\Vocana is never touched."""
    me = installed_info()
    if me is None:
        raise RuntimeError('not installed')
    target = me.get('dir') or ROOT_DIR
    # Only ever delete the folder this copy runs from, and only when it is
    # really ours: our marker is in it and its name is Vocana.
    if (os.path.normcase(os.path.realpath(target)) != os.path.normcase(os.path.realpath(ROOT_DIR))
            or os.path.basename(target.rstrip('\\/')).lower() != NAME.lower()):
        target = None
    for p in me.get('shortcuts') or []:
        try:
            if p.lower().endswith('.lnk') and os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass
    unregister()
    scheduled = False
    if target and WINDOWS:
        try:
            enc = base64.b64encode(REMOVE_PS.encode('utf-16-le')).decode('ascii')
            env = dict(os.environ)
            env['VC_DEL'] = target
            exe = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0',
                               'powershell.exe')
            subprocess.Popen([exe if os.path.isfile(exe) else 'powershell.exe', '-NoProfile', '-NonInteractive',
                              '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-EncodedCommand', enc],
                             env=env, cwd=os.environ.get('TEMP') or os.path.expanduser('~'),
                             creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS | 0x00000200,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            scheduled = True
        except Exception:
            scheduled = False
    return {'removed': True, 'folder_scheduled': scheduled, 'dir': me.get('dir'), 'data': me.get('data_dir')}


# ==================================================================
# Command line entry points (Setup.bat and the Apps list call these)
# ==================================================================
def install_cli(silent=False, desktop=True):
    from .system import message_box
    lang = ui_lang()
    if not WINDOWS:
        print(msg('windows_only', lang))
        return 1
    try:
        res = install(desktop=desktop, lang=lang)
    except Exception as e:
        if silent:
            print('install failed: %s' % e)
        else:
            message_box(NAME, str(e), rtl=lang == 'fa')
        return 1
    print('Installed to %s' % res['dir'])
    if not silent:
        launch_detached(res['launch'])
    return 0


def uninstall_cli(silent=False):
    from .system import message_box
    lang = ui_lang()
    me = installed_info()
    if me is None:
        if not silent:
            message_box(NAME, msg('not_installed', lang), rtl=lang == 'fa', kind='info')
        return 1
    data = me.get('data_dir') or data_target()
    if not silent and not message_box(NAME, msg('confirm', lang, data=data), rtl=lang == 'fa', kind='warn', ask=True):
        return 1
    stop_running(data)
    res = uninstall()
    if not silent:
        if res['folder_scheduled']:
            message_box(NAME, msg('done', lang, data=data), rtl=lang == 'fa', kind='info')
        else:
            message_box(NAME, msg('manual', lang, dir=res.get('dir') or ''), rtl=lang == 'fa', kind='warn')
    return 0
