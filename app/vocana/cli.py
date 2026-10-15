"""
The command line. Every command VoxTalk had still works the same way:

  vocana script scripts/intro.txt         -> renders/intro/
  vocana say "Hello! I'm AmirCollider!" --mood excited
  vocana kana "Hello! I'm AmirCollider!"  (the katakana; no engine needed)
  vocana voices                           (every character and style)

and there are new ones:

  vocana studio                           the studio in your browser
  vocana check scripts/intro.txt          read a script, report problems, render nothing
  vocana say --interactive                type lines, hear them, until an empty line
  vocana doctor                           what is installed and what is not
  vocana install / uninstall              (Windows) Start menu, Apps & features

`vocana` is `python vocana.py` in the product folder, or Vocana.bat's
Python on Windows (render_script.bat and say.bat call these for you).
"""

import argparse
import os
import sys

from . import NAME, VERSION


def _out(text=''):
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or 'ascii'
        print(text.encode(enc, 'replace').decode(enc, 'replace'), flush=True)


WARN_TEXT = {
    'unknown_mood': 'mood "{mood}" is not in moods.json - the line uses "normal" for it',
    'speaker_not_cast': '"{who}" has no @cast line - read by the default voice ({name})',
    'cast_unknown_character': '"{name}" is not a character in this VOICEVOX - {who} uses the default voice',
    'default_missing': 'the default voice "{name}" is not in this VOICEVOX',
    'bad_cast': 'this @cast line has no character after "="',
    'bad_cast_option': '"{text}" is not an option @cast understands (pitch, speed, volume, intonation)',
    'unknown_directive': 'unknown "@" line, ignored: {text}',
    'bad_number': 'not a number: {text}',
    'unreadable_text': 'VOICEVOX cannot read this script, left out: {text}',
    'nothing_to_say': 'nothing on this line can be said',
    'no_model': 'e2k is not installed: words not in words.json are spelled letter by letter',
    'kana_simplified': 'VOICEVOX refused the accents of "{kana}"; read with simpler accents',
    'kana_plain': 'VOICEVOX refused "{kana}"; read as plain katakana',
}


def warning_text(w):
    try:
        msg = WARN_TEXT.get(w.get('code'), w.get('message') or w.get('code', '')).format(**w)
    except (KeyError, IndexError):
        msg = w.get('message') or w.get('code', '')
    return ('line %s: ' % w['n'] if w.get('n') else '') + msg


def main(argv=None):
    ap = argparse.ArgumentParser(prog='vocana', description='%s %s - plain English, any VOICEVOX voice.' % (NAME, VERSION))
    ap.add_argument('--version', action='version', version='%s %s' % (NAME, VERSION))
    ap.add_argument('--data', help='folder with words.json, moods.json, scripts/ and renders/')
    sub = ap.add_subparsers(dest='cmd')
    s = sub.add_parser('script', help='render a script file')
    s.add_argument('file')
    s.add_argument('--out', help='output folder (default: renders/<script name>)')
    s = sub.add_parser('say', help='say one line')
    s.add_argument('text', nargs='?')
    s.add_argument('--mood', action='append', default=[])
    s.add_argument('--character', help='a VOICEVOX character (name, romaji or style id)')
    s.add_argument('--out')
    s.add_argument('--interactive', action='store_true', help='keep asking for lines')
    s = sub.add_parser('kana', help='show the katakana VOICEVOX will get (no engine needed)')
    s.add_argument('text')
    s.add_argument('--mood', action='append', default=[])
    sub.add_parser('voices', help='list the characters and styles of the running VOICEVOX')
    s = sub.add_parser('check', help='read a script and report problems without rendering')
    s.add_argument('file')
    s = sub.add_parser('studio', help='open the studio')
    s.add_argument('--port', type=int)
    s.add_argument('--no-browser', action='store_true')
    s.add_argument('--auto-exit', action='store_true', help='quit when no studio window has been open for a while')
    s.add_argument('--page', default='')
    s.add_argument('file', nargs='?', help='a script to open')
    sub.add_parser('doctor', help='check the installation')
    s = sub.add_parser('install', help='(Windows) install for this user: Start menu, Apps & features')
    s.add_argument('--silent', action='store_true')
    s.add_argument('--no-desktop', action='store_true')
    s = sub.add_parser('uninstall', help='(Windows) remove the installed copy (your files stay)')
    s.add_argument('--silent', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd is None:
        ap.print_help()
        return 0

    if a.cmd == 'studio':
        from .server import run_studio
        return run_studio(port=a.port, open_browser=not a.no_browser, auto_exit=a.auto_exit,
                          page=a.page, script=a.file, data_dir=a.data)
    if a.cmd == 'doctor':
        from .doctor import report
        ok = True
        for row in report(a.data):
            mark = {'ok': 'OK  ', 'warn': 'WARN', 'fail': 'FAIL'}[row['status']]
            ok = ok and row['status'] != 'fail'
            _out('[%s] %-22s %s' % (mark, row['label'], row['detail']))
        return 0 if ok else 1
    if a.cmd == 'install':
        from .installer import install_cli
        return install_cli(silent=a.silent, desktop=not a.no_desktop)
    if a.cmd == 'uninstall':
        from .installer import uninstall_cli
        return uninstall_cli(silent=a.silent)

    from .engine import EngineError
    from .render import Vocana, RenderError, Cancelled, safe_name
    from .paths import layout

    lay = layout(a.data).ensure()
    vt = Vocana(data_dir=a.data)
    started = None
    if a.cmd in ('script', 'say', 'voices'):
        started = _ensure_engine(vt, lay)
    try:
        if a.cmd == 'kana':
            for p in vt.plan(a.text, a.mood):
                _out('%-12s %s' % ('/'.join(p['seg']['moods']), p['kana']))
            if vt.kana.c2k is None:
                _out('(e2k is not installed: unknown words are spelled letter by letter.)')
        elif a.cmd == 'voices':
            voices = vt.voices()
            for sp in voices.speakers:
                _out(sp['name'] + ':  ' + ', '.join('%s=%d' % (st['name'], st['id']) for st in sp['styles']))
            _out('\n%d characters. Credit each one you use: "VOICEVOX:<name>" (the studio shows each character\'s own terms).'
                 % len(voices.speakers))
        elif a.cmd == 'check':
            from .config import read_text
            text, enc = read_text(a.file)
            plan = vt.plan_script(text)
            n_lines = sum(1 for ln in plan['lines'] if ln['kind'] == 'line')
            _out('%d lines, %d characters%s' % (n_lines, len(plan['cast']),
                                               '' if plan['engine'] else ' (VOICEVOX closed: characters not checked)'))
            for c in plan['cast']:
                _out('  %-10s -> %s%s' % (c['who'], c['character'], '' if c['found'] or not plan['engine'] else '  (not found)'))
            if enc != 'utf-8':
                _out('note: the file is not UTF-8 (read as %s). Save it as UTF-8 to be safe.' % enc)
            for w in plan['warnings']:
                _out('warning: ' + warning_text(w))
            if plan['review']:
                _out('\nWords guessed by the model (pin any that sound wrong in words.json):')
                for r in plan['review']:
                    _out('  %-18s %s' % (r['word'], r['kana']))
            return 0
        elif a.cmd == 'say':
            if a.interactive or not a.text:
                return _say_loop(vt, a, lay)
            _say_once(vt, a.text, a, a.out or os.path.join(lay.renders, 'say.wav'))
        elif a.cmd == 'script':
            from .config import read_text
            name = safe_name(os.path.splitext(os.path.basename(a.file))[0])
            out = a.out or os.path.join(lay.renders, name)
            text, enc = read_text(a.file)
            if enc != 'utf-8':
                _out('note: %s is not UTF-8 (read as %s).' % (os.path.basename(a.file), enc))

            def progress(ev):
                if ev['stage'] == 'voice':
                    _out('loading voice %d/%d: %s' % (ev['i'], ev['total'], ev['text']))
                elif ev['stage'] == 'line':
                    _out('[%d/%d] %s: %s' % (ev['i'], ev['total'], ev.get('character') or ev['who'], ev['text']))
            res = vt.render_script(text, out, progress=progress, script_name=name)
            for w in res['warnings']:
                _out('warning: ' + warning_text(w))
            _out('\n%d lines, %.1f s -> %s' % (res['lines'], res['length'], out))
            if res['credits']:
                _out('Put this in the video\'s description: ' + ', '.join(c['credit'] for c in res['credits']))
    except (EngineError, RenderError) as e:
        _out('\n' + str(e))
        return 1
    except Cancelled:
        _out('\ncancelled')
        return 1
    except KeyboardInterrupt:
        _out('\nstopped')
        return 1
    finally:
        if started is not None:
            from .system import stop_process
            stop_process(started)
    return 0


def _ensure_engine(vt, lay):
    """render_script.bat should not need VOICEVOX opened first: start its
    engine (hidden) when it is closed, and stop it again afterwards. Returns
    the process to stop, or None."""
    if vt.engine.alive(timeout=1.5):
        return None
    from .config import load_settings
    from .system import start_voicevox
    import time
    st = load_settings(lay.settings)
    if st.get('engine_start') == 'off':
        return None
    import urllib.parse
    port = urllib.parse.urlsplit(vt.engine.url).port or 50021
    kind, proc = start_voicevox(st.get('engine_start', 'auto'), st.get('voicevox_path', ''), port)
    if kind is None:
        return None
    _out('Starting VOICEVOX (%s)...' % ('engine' if kind == 'engine' else 'app'))
    for _ in range(240):
        if vt.engine.alive(timeout=1):
            return proc if kind == 'engine' else None
        if proc is not None and proc.poll() is not None:
            break
        time.sleep(0.5)
    _out('VOICEVOX did not start in time.')
    return proc if kind == 'engine' else None


def _say_once(vt, text, a, out):
    from .render import normalize, write_wav
    voices = vt.voices()
    cast = {}
    if a.character:
        cast['ME'] = {'speaker': a.character}
    char = vt.character('ME', cast, voices)
    if char.get('warning'):
        _out('warning: ' + warning_text(char['warning']))
    for p in vt.plan(text, a.mood, None, 'ME', char, None):
        _out(p['kana'])
    x, sr, _s = vt.speak_timed(text, a.mood, None, 'ME', char, voices)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    write_wav(out, normalize(x), sr)
    _out('wrote %s  (%s)' % (out, char.get('name')))


def _say_loop(vt, a, lay):
    _out('Type a line and press Enter (an empty line quits). [mood] at the start picks a mood: [excited] Hello!')
    k = 0
    while True:
        try:
            text = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        k += 1
        out = os.path.join(lay.renders, 'say.wav' if k == 1 else 'say_%d.wav' % k)
        try:
            _say_once(vt, text, a, out)
        except Exception as e:                         # keep the loop alive
            _out(str(e))
    return 0


if __name__ == '__main__':
    sys.exit(main())
