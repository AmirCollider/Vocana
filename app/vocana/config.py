"""
Reading and writing the user's files: words.json, moods.json, settings.json
and scripts.

Everything here is written for files that a person edits in Notepad:

  * A byte-order mark is accepted (Notepad adds one; json.load refuses it).
  * A script saved as "ANSI" or "Unicode" (UTF-16) still opens, and the
    studio is told which encoding was guessed.
  * A broken JSON file is reported with its name, line and column - not a
    traceback - and the shipped default is used until it is fixed.
  * Writes go to a temporary file first and replace the real one in one
    step, so a crash or a full disk never leaves half a file behind.
  * A value that would make the engine refuse a request (a speed of 0, a
    pitch of 40 semitones) is clamped, and the clamp is reported.
"""

import copy
import json
import locale
import os
import tempfile

from .paths import DEFAULTS_DIR


class ConfigError(Exception):
    def __init__(self, message, path=None, line=None, column=None):
        Exception.__init__(self, message)
        self.path = path
        self.line = line
        self.column = column


# ==================================================================
# Text files
# ==================================================================
def read_text(path):
    """(text, encoding). Tries UTF-8 (with or without BOM), UTF-16 by its
    BOM, the system's ANSI code page, then Latin-1, which never fails."""
    with open(path, 'rb') as f:
        data = f.read()
    if data.startswith(b'\xff\xfe') or data.startswith(b'\xfe\xff'):
        return data.decode('utf-16'), 'utf-16'
    try:
        return data.decode('utf-8-sig'), 'utf-8'
    except UnicodeDecodeError:
        pass
    enc = locale.getpreferredencoding(False) or 'cp1252'
    for e in (enc, 'cp1252'):
        try:
            return data.decode(e), e
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('latin-1'), 'latin-1'


def write_text(path, text):
    """Atomic UTF-8 write (no BOM, newlines as given)."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.vocana-', suffix='.tmp', dir=folder)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def read_json(path):
    try:
        text, _enc = read_text(path)
    except FileNotFoundError:
        raise
    except OSError as e:
        raise ConfigError('%s cannot be read: %s' % (os.path.basename(path), e), path)
    try:
        return json.loads(text)
    except ValueError as e:
        line = getattr(e, 'lineno', None)
        col = getattr(e, 'colno', None)
        raise ConfigError('%s is not valid JSON (line %s, column %s): %s'
                          % (os.path.basename(path), line, col, getattr(e, 'msg', e)), path, line, col)


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + '\n')


def default_json(name):
    with open(os.path.join(DEFAULTS_DIR, name), encoding='utf-8') as f:
        return json.load(f)


# ==================================================================
# words.json
# ==================================================================
def load_words(path):
    """({word: kana}, warnings). Keys are lowercased; '_about' and other
    underscore keys are notes, not words."""
    warnings = []
    try:
        raw = read_json(path)
    except FileNotFoundError:
        raw = default_json('words.json')
    except ConfigError as e:
        warnings.append({'code': 'words_invalid', 'message': str(e), 'line': e.line})
        raw = default_json('words.json')
    if not isinstance(raw, dict):
        warnings.append({'code': 'words_invalid', 'message': 'words.json must be an object of "word": "カタカナ" pairs.'})
        raw = default_json('words.json')
    words = {}
    for k, v in raw.items():
        if not isinstance(k, str) or k.startswith('_'):
            continue
        if not isinstance(v, str) or not v.strip():
            warnings.append({'code': 'word_empty', 'word': k})
            continue
        key = k.strip().lower().replace('’', "'")
        if not any('ぁ' <= c <= 'ヺ' for c in v):
            warnings.append({'code': 'word_no_kana', 'word': k, 'kana': v})
            continue
        words[key] = v.strip()
    return words, warnings


def save_words(path, entries, about=None):
    """entries: {word: kana}. Keeps the file's _about note at the top."""
    out = {}
    try:
        old = read_json(path)
        if isinstance(old, dict):
            for k, v in old.items():
                if isinstance(k, str) and k.startswith('_'):
                    out[k] = v
    except (FileNotFoundError, ConfigError):
        pass
    if about:
        out['_about'] = about
    if '_about' not in out:
        out['_about'] = default_json('words.json').get('_about', '')
    for k in sorted(entries, key=lambda s: s.lower()):
        v = entries[k]
        if isinstance(k, str) and k.strip() and not k.startswith('_') and isinstance(v, str) and v.strip():
            out[k.strip().lower()] = v.strip()
    write_json(path, out)


# ==================================================================
# moods.json
# ==================================================================
# (low, high) for every number a mood may set. Outside these the engine
# either refuses the request or produces noise.
RANGES = {
    'speed': (0.5, 2.0), 'intonation': (0.0, 2.0), 'volume': (0.0, 3.0), 'pitch': (-12.0, 12.0),
    'bounce': (0.0, 4.0), 'end_rise': (-12.0, 12.0), 'exclaim_rise': (-12.0, 12.0),
    'end_stretch': (0.3, 3.0), 'pauses': (0.0, 3.0),
}
CAST_RANGES = {'pitch': (-12.0, 12.0), 'speed': (0.5, 2.0), 'volume': (0.0, 3.0), 'intonation': (0.0, 2.0)}


def clean_mood(name, mood, warnings):
    out = {}
    if not isinstance(mood, dict):
        warnings.append({'code': 'mood_invalid', 'mood': name})
        return out
    for k, v in mood.items():
        if k in RANGES:
            try:
                f = float(v)
            except (TypeError, ValueError):
                warnings.append({'code': 'mood_value', 'mood': name, 'key': k, 'value': v})
                continue
            lo, hi = RANGES[k]
            if f != f or f < lo or f > hi:          # NaN, or out of range
                warnings.append({'code': 'mood_clamped', 'mood': name, 'key': k, 'value': v, 'low': lo, 'high': hi})
                f = lo if f != f else min(max(f, lo), hi)
            out[k] = f
        elif k == 'style':
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()
        elif k == 'tone':
            if isinstance(v, str) and v.strip():
                out[k] = [v.strip()]
            elif isinstance(v, list):
                out[k] = [str(x).strip() for x in v if str(x).strip()]
        else:
            out[k] = v
    return out


def load_moods(path):
    """(config, warnings). config always has engine, speaker, style, cast,
    moods - filled from the shipped file where the user's lacks them."""
    warnings = []
    default = default_json('moods.json')
    try:
        raw = read_json(path)
    except FileNotFoundError:
        raw = copy.deepcopy(default)
    except ConfigError as e:
        warnings.append({'code': 'moods_invalid', 'message': str(e), 'line': e.line})
        raw = copy.deepcopy(default)
    if not isinstance(raw, dict):
        warnings.append({'code': 'moods_invalid', 'message': 'moods.json must be a JSON object.'})
        raw = copy.deepcopy(default)
    cfg = {
        'engine': raw.get('engine') if isinstance(raw.get('engine'), str) else default['engine'],
        'speaker': raw.get('speaker') if isinstance(raw.get('speaker'), str) else default['speaker'],
        'style': raw.get('style') if isinstance(raw.get('style'), str) else default['style'],
        'cast': {},
        'moods': {},
    }
    moods = raw.get('moods')
    if not isinstance(moods, dict) or not moods:
        if moods is not None:
            warnings.append({'code': 'moods_invalid', 'message': '"moods" must be an object.'})
        moods = default['moods']
    for name, m in moods.items():
        if isinstance(name, str) and not name.startswith('_'):
            cfg['moods'][name.strip().lower()] = clean_mood(name, m, warnings)
    if 'normal' not in cfg['moods']:
        cfg['moods']['normal'] = clean_mood('normal', default['moods']['normal'], warnings)
    cast = raw.get('cast')
    if isinstance(cast, dict):
        for tag, spec in cast.items():
            if isinstance(tag, str) and not tag.startswith('_'):
                entry = clean_cast(tag, spec, warnings)
                if entry:
                    cfg['cast'][tag.strip().upper()] = entry
    return cfg, warnings


def clean_cast(tag, spec, warnings):
    """A cast entry: {speaker, style?, pitch?, speed?, volume?, intonation?}.
    A bare string is the character's name."""
    if isinstance(spec, str):
        spec = {'speaker': spec}
    if not isinstance(spec, dict) or not str(spec.get('speaker', '')).strip():
        warnings.append({'code': 'cast_invalid', 'who': tag})
        return None
    out = {'speaker': str(spec['speaker']).strip()}
    if spec.get('style') not in (None, ''):
        out['style'] = str(spec['style']).strip()
    for k, (lo, hi) in CAST_RANGES.items():
        if k in spec:
            try:
                f = float(spec[k])
            except (TypeError, ValueError):
                warnings.append({'code': 'cast_value', 'who': tag, 'key': k, 'value': spec[k]})
                continue
            if f != f or f < lo or f > hi:
                warnings.append({'code': 'cast_clamped', 'who': tag, 'key': k, 'value': spec[k], 'low': lo, 'high': hi})
                f = lo if f != f else min(max(f, lo), hi)
            out[k] = f
    return out


def save_moods(path, cfg):
    """Writes the whole moods.json, keeping the file's notes."""
    out = {}
    try:
        old = read_json(path)
        if isinstance(old, dict):
            out.update({k: v for k, v in old.items() if isinstance(k, str) and k.startswith('_')})
    except (FileNotFoundError, ConfigError):
        pass
    if '_about' not in out:
        out['_about'] = default_json('moods.json').get('_about', '')
    out['engine'] = cfg.get('engine') or default_json('moods.json')['engine']
    out['speaker'] = cfg.get('speaker') or 'ずんだもん'
    out['style'] = cfg.get('style') or 'ノーマル'
    out['cast'] = cfg.get('cast') or {}
    moods = {}
    for name, m in (cfg.get('moods') or {}).items():
        m = dict(m)
        if isinstance(m.get('tone'), list) and len(m['tone']) == 1:
            m['tone'] = m['tone'][0]
        moods[name] = m
    out['moods'] = moods
    write_json(path, out)


# ==================================================================
# settings.json - the studio's own preferences
# ==================================================================
SETTINGS_DEFAULTS = {
    'lang': 'auto',              # auto | fa | en | ja
    'theme': 'auto',             # auto | light | dark
    'engine_start': 'auto',      # auto | engine | app | off
    'voicevox_path': '',
    'app_window': True,          # open the studio in an app window (Edge/Chrome --app)
    'check_updates': True,
    'port': 50210,
    'last_script': '',
    'editor_size': 15,
    'show_kana': True,
}


def load_settings(path):
    s = dict(SETTINGS_DEFAULTS)
    try:
        raw = read_json(path)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in SETTINGS_DEFAULTS and type(v) is type(SETTINGS_DEFAULTS[k]):
                    s[k] = v
                elif k.startswith('_'):
                    s[k] = v
    except (FileNotFoundError, ConfigError):
        pass
    if s['lang'] not in ('auto', 'fa', 'en', 'ja'):
        s['lang'] = 'auto'
    if s['theme'] not in ('auto', 'light', 'dark'):
        s['theme'] = 'auto'
    if s['engine_start'] not in ('auto', 'engine', 'app', 'off'):
        s['engine_start'] = 'auto'
    if not (1024 <= int(s['port']) <= 65535):
        s['port'] = SETTINGS_DEFAULTS['port']
    return s


def save_settings(path, settings):
    s = load_settings(path)
    for k, v in settings.items():
        if k in SETTINGS_DEFAULTS and type(v) is type(SETTINGS_DEFAULTS[k]):
            s[k] = v
        elif k.startswith('_'):
            s[k] = v
    write_json(path, s)
    return load_settings(path)
