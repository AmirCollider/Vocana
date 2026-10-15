"""
Where the program is, and where the user's files are.

Two layouts, one program:

  portable  The folder as it was unzipped. Everything - words.json,
            moods.json, scripts/, renders/ - lives in that folder, so it
            can sit on a USB stick or be zipped and moved.

  installed Setup copied the program to %LOCALAPPDATA%\\Programs\\Vocana
            and wrote app/installed.json. The user's files live in
            Documents\\Vocana, where people look for their own work, and
            an update or an uninstall never touches them.

A portable folder that cannot be written to (unzipped under Program Files,
a read-only drive) also uses Documents\\Vocana, and the studio says so.
"""

import json
import os
import shutil
import sys

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(PKG_DIR)                 # .../app
ROOT_DIR = os.path.dirname(APP_DIR)                # the product folder
DEFAULTS_DIR = os.path.join(PKG_DIR, 'defaults')
STUDIO_DIR = os.path.join(APP_DIR, 'studio')
BRAND_DIR = os.path.join(APP_DIR, 'brand')
FONTS_DIR = os.path.join(APP_DIR, 'fonts')
RUNTIME_DIR = os.path.join(APP_DIR, 'runtime')
INSTALL_MARKER = os.path.join(APP_DIR, 'installed.json')
GUIDE = os.path.join(ROOT_DIR, 'Guide.html')

WINDOWS = sys.platform == 'win32'
MAC = sys.platform == 'darwin'


def installed_info():
    try:
        with open(INSTALL_MARKER, encoding='utf-8-sig') as f:
            info = json.load(f)
        return info if isinstance(info, dict) else {}
    except (OSError, ValueError):
        return None


# Known folders: Windows moves Documents and Desktop (to OneDrive, to another
# drive), and ~/Documents is then the wrong place.
FOLDERID = {
    'Documents': (0xFDD39AD0, 0x238F, 0x46AF, (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7)),
    'Desktop': (0xB4BFCC3A, 0xDB2C, 0x424C, (0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41)),
    'Programs': (0xA77F5D77, 0x2E2B, 0x44C3, (0xA6, 0xA2, 0xAB, 0xA6, 0x01, 0x05, 0x4A, 0x51)),
}


def known_folder(name):
    """The real path of a Windows known folder, or None."""
    if not WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                        ('Data3', wintypes.WORD), ('Data4', wintypes.BYTE * 8)]

        d1, d2, d3, d4 = FOLDERID[name]
        fid = GUID(d1, d2, d3, (wintypes.BYTE * 8)(*[b if b < 128 else b - 256 for b in d4]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
            path = out.value
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path or None
    except Exception:
        return None
    return None


def documents_dir():
    path = known_folder('Documents')
    if path and os.path.isdir(path):
        return path
    home = os.path.expanduser('~')
    docs = os.path.join(home, 'Documents')
    return docs if os.path.isdir(docs) else home


def writable(folder):
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, '.vocana-write-test')
        with open(probe, 'w') as f:
            f.write('ok')
        os.remove(probe)
        return True
    except OSError:
        return False


class Layout:
    """Resolved once per process: which mode, and where the data is."""

    def __init__(self, data_dir=None):
        self.installed = installed_info() is not None
        self.fallback = False
        if data_dir:
            self.data = os.path.abspath(data_dir)
        elif os.environ.get('VOCANA_DATA'):
            self.data = os.path.abspath(os.environ['VOCANA_DATA'])
        elif self.installed:
            info = installed_info() or {}
            self.data = info.get('data_dir') or os.path.join(documents_dir(), 'Vocana')
        elif writable(ROOT_DIR):
            self.data = ROOT_DIR
        else:
            self.data = os.path.join(documents_dir(), 'Vocana')
            self.fallback = True
        self.words = os.path.join(self.data, 'words.json')
        self.moods = os.path.join(self.data, 'moods.json')
        self.settings = os.path.join(self.data, 'settings.json')
        self.scripts = os.path.join(self.data, 'scripts')
        self.renders = os.path.join(self.data, 'renders')
        self.logs = os.path.join(self.data, 'logs')

    def ensure(self):
        """Create whatever is missing from the shipped defaults. Never
        overwrites a file that exists."""
        os.makedirs(self.data, exist_ok=True)
        for name in ('words.json', 'moods.json'):
            target = os.path.join(self.data, name)
            if not os.path.exists(target):
                shutil.copyfile(os.path.join(DEFAULTS_DIR, name), target)
        os.makedirs(self.renders, exist_ok=True)
        if not os.path.isdir(self.scripts):
            os.makedirs(self.scripts, exist_ok=True)
            src = os.path.join(DEFAULTS_DIR, 'scripts')
            for name in os.listdir(src):
                shutil.copyfile(os.path.join(src, name), os.path.join(self.scripts, name))
        return self

    def as_dict(self):
        return {'data': self.data, 'installed': self.installed, 'fallback': self.fallback,
                'scripts': self.scripts, 'renders': self.renders, 'root': ROOT_DIR}


_layout = None


def layout(data_dir=None):
    global _layout
    if _layout is None or data_dir:
        _layout = Layout(data_dir)
    return _layout
