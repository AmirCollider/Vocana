"""
From a script to audio, captions and timing.

    vc = Vocana()
    plan = vc.plan_script(text)            # what will be said - no engine needed
    result = vc.render_script(text, 'renders/intro')

The sound of a single-character script is what VoxTalk made, sample for
sample (tests/test_regression.py renders the sample script both ways and
compares the files). What changed around it:

  * every line can be a different character (the cast), and a mood picks
    the closest style that character has;
  * a word the engine refuses no longer stops the render - the sentence is
    read a simpler way and the render reports which word it was;
  * Japanese sentences go to the engine's own Japanese reader;
  * a render writes credits.txt (the exact credit line each character's
    terms ask for), WebVTT captions and a copy of the script beside the
    audio, and removes line files left over from a longer earlier render;
  * the studio can follow progress and cancel.
"""

import io
import json
import os
import re
import threading
import wave
import zlib

import numpy as np

from . import config as cfgmod
from .engine import Engine, EngineError
from .kana import Kana, loanword_accent, SOURCE_MODEL, SOURCE_SPELLED
from .melody import shape, mora_times
from .paths import layout as get_layout
from .script import parse_script
from .text import split_line, sentence_words, build_kana, japanese_text, caption_text
from .voices import Voices, policy_summary

SR = 24000


class Cancelled(Exception):
    pass


class RenderError(RuntimeError):
    def __init__(self, message, n=None, code=None, kind='error'):
        RuntimeError.__init__(self, message)
        self.n = n
        self.code = code
        self.kind = kind


# ==================================================================
# Audio helpers
# ==================================================================
def wav_to_array(data):
    with wave.open(io.BytesIO(data)) as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        width = w.getsampwidth()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise EngineError('VOICEVOX sent %d-bit audio; Vocana reads 16-bit.' % (width * 8))
    x = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def resample(x, sr, target):
    if sr == target or not len(x):
        return x
    n = int(round(len(x) * target / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def trim_bounds(x, sr, thresh=0.01, keep=0.03):
    a = np.abs(x)
    on = np.where(a > thresh * max(a.max(), 1e-6))[0] if len(a) else np.array([], dtype=int)
    if len(on) == 0:
        return 0, len(x)
    k = int(keep * sr)
    return max(0, on[0] - k), min(len(x), on[-1] + k)


def wav_bytes(x, sr):
    x = np.clip(x, -1, 1)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def write_file(path, data):
    """Atomic binary write. A file another program holds open (a video
    editor with full.wav in its timeline) is reported by name."""
    tmp = path + '.part'
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except PermissionError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise RenderError('%s is open in another program (a video editor or a player?). '
                          'Close it there, or render under a new name.' % os.path.basename(path),
                          code='file_locked')


def write_wav(path, x, sr):
    write_file(path, wav_bytes(x, sr))


def normalize(x, peak=0.89):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return x * (peak / m) if m > 0 else x


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return '%02d:%02d:%02d,%03d' % (h, m, s, ms)


def vtt_time(t):
    return srt_time(t).replace(',', '.')


WIN_RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % i for i in range(1, 10)} | {'lpt%d' % i for i in range(1, 10)}


def safe_name(name, fallback='render'):
    """A file or folder name every OS accepts."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f†]+', '_', str(name)).strip().strip('.')
    name = re.sub(r'\s+', ' ', name)[:80].strip()
    if not name or name.lower() in WIN_RESERVED:
        name = fallback
    return name


# ==================================================================
# The program
# ==================================================================
class Vocana:
    def __init__(self, data_dir=None, moods_path=None, words_path=None, engine_url=None):
        self.layout = get_layout(data_dir)
        self.moods_path = moods_path or self.layout.moods
        self.words_path = words_path or self.layout.words
        self._engine_url = engine_url
        self._stamp = None
        self._voices = None
        self._voices_lock = threading.Lock()
        self._credits = {}
        self.load()

    # --------------------------------------------------------------
    def _mtimes(self):
        out = []
        for p in (self.moods_path, self.words_path):
            try:
                st = os.stat(p)
                out.append((st.st_mtime_ns, st.st_size))
            except OSError:
                out.append(None)
        return tuple(out)

    def load(self):
        self.cfg, self.cfg_warnings = cfgmod.load_moods(self.moods_path)
        self.cfg_warnings = list(self.cfg_warnings)
        words, wwarn = cfgmod.load_words(self.words_path)
        self.cfg_warnings += wwarn
        self.moods = self.cfg['moods']
        self.kana = Kana(words)
        url = self._engine_url or self.cfg.get('engine')
        if not hasattr(self, 'engine') or self.engine.url != Engine(url).url:
            self.engine = Engine(url)
            self._voices = None
        self._stamp = self._mtimes()

    def reload_if_changed(self):
        if self._mtimes() != self._stamp:
            self.load()
            return True
        return False

    # --------------------------------------------------------------
    def voices(self, refresh=False):
        with self._voices_lock:
            if self._voices is None or refresh:
                self._voices = Voices(self.engine.speakers(refresh=refresh))
            return self._voices

    def voices_or_none(self):
        try:
            return self.voices()
        except EngineError:
            return None

    def credit(self, sp):
        name = sp['name']
        if name not in self._credits:
            try:
                info = self.engine.speaker_info(sp['speaker_uuid'])
                self._credits[name] = policy_summary(name, info.get('policy', ''))
            except (EngineError, KeyError):
                return policy_summary(name, '')
        return self._credits[name]

    def mood(self, names):
        m = dict(self.moods.get('normal', {}))
        for n in names:
            if n in self.moods:
                m.update(self.moods[n])
        return m

    # --------------------------------------------------------------
    # Cast: which character says the lines of one speaker tag
    # --------------------------------------------------------------
    def find_speaker(self, name, voices):
        sp = voices.find(name)
        if sp is not None:
            return sp, None
        if '/' in str(name):
            n, _, st = str(name).rpartition('/')
            sp = voices.find(n.strip())
            if sp is not None:
                return sp, st.strip() or None
        return None, None

    def character(self, who, script_cast, voices):
        """{'who', 'speaker' (engine entry or None), 'style', 'adjust',
        'origin', 'warning'?} for one speaker tag."""
        spec = (script_cast or {}).get(who)
        origin = 'script'
        if spec is None:
            spec = self.cfg['cast'].get(who)
            origin = 'config'
        out = {'who': who, 'speaker': None, 'style': None, 'adjust': {}, 'origin': origin, 'name': None}
        if spec is not None:
            out['name'] = spec['speaker']
            out['style'] = spec.get('style')
            out['adjust'] = {k: spec[k] for k in ('pitch', 'speed', 'volume', 'intonation') if k in spec}
        if voices is None:                       # engine offline: plan without voices
            if spec is None:
                out['origin'] = 'default'
                out['name'] = self.cfg['speaker']
            return out
        if spec is not None:
            sp, st = self.find_speaker(spec['speaker'], voices)
            if sp is not None:
                out['speaker'] = sp
                out['name'] = sp['name']
                if st and not out['style']:
                    out['style'] = st
                return out
            out['warning'] = {'code': 'cast_unknown_character', 'who': who, 'name': spec['speaker']}
        else:
            sp = voices.find(who) if who != 'ME' else None
            if sp is not None:                   # "METAN: ..." - the tag is a character
                out.update(speaker=sp, name=sp['name'], origin='auto')
                return out
            if who != 'ME':
                out['warning'] = {'code': 'speaker_not_cast', 'who': who, 'name': self.cfg['speaker']}
        sp, st = self.find_speaker(self.cfg['speaker'], voices)
        if sp is None:
            sp = voices.speakers[0] if voices.speakers else None
            out['warning'] = {'code': 'default_missing', 'who': who, 'name': self.cfg['speaker']}
        out.update(speaker=sp, name=sp['name'] if sp else self.cfg['speaker'],
                   origin='default' if spec is None else out['origin'])
        if out['style'] is None and spec is None:
            out['style_default'] = st or self.cfg.get('style')
        return out

    def line_mood(self, names, char):
        mood = self.mood(names)
        if char.get('style_default') and 'style' not in mood:
            mood['style'] = char['style_default']
        adj = char.get('adjust') or {}
        if 'pitch' in adj:
            mood['pitch'] = float(mood.get('pitch', 0.0)) + adj['pitch']
        for k, neutral in (('speed', 1.0), ('volume', 1.0), ('intonation', 1.3)):
            if k in adj:
                mood[k] = float(mood.get(k, neutral)) * adj[k]
        return mood

    def style_for(self, char, mood, voices):
        sp = char.get('speaker')
        if sp is None or voices is None:
            return None, mood.get('style') or char.get('style'), 'offline'
        if char.get('style_default') and not char.get('style'):
            st, how = voices.resolve(sp, mood, None)
        else:
            st, how = voices.resolve(sp, mood, char.get('style'))
        return st, st['name'], how

    # --------------------------------------------------------------
    # Planning: what will be said
    # --------------------------------------------------------------
    def plan(self, text, moods=(), sentence_gap=None, who='ME', char=None, voices=None, notes=None):
        """Sentences of one line, each with kana, mood and words."""
        plan = []
        if char is None:
            char = self.character(who, None, voices)
        for seg in split_line(text, list(moods) or ['normal'], sentence_gap, notes):
            mood = self.line_mood(seg['moods'], char)
            st, style_name, how = self.style_for(char, mood, voices)
            if seg.get('japanese'):
                jt = japanese_text(seg['body'], self.kana, seg['question'])
                if not jt.strip('？ '):
                    continue
                plan.append({'seg': seg, 'words': [], 'kana': jt, 'japanese': True, 'spans': [], 'moras': 0,
                             'mood': mood, 'style': st, 'style_name': style_name, 'style_how': how})
                continue
            words = sentence_words(seg['body'], self.kana)
            if not any(isinstance(w, dict) for w in words):
                continue
            kana, spans, n = build_kana(words, seg['question'])
            plan.append({'seg': seg, 'words': words, 'kana': kana, 'japanese': False, 'spans': spans, 'moras': n,
                         'mood': mood, 'style': st, 'style_name': style_name, 'style_how': how})
        return plan

    def plan_script(self, text, offline=False):
        """Everything the studio shows before a render: per line the
        character, the styles, the kana and every word's source, plus the
        warnings - with line numbers. Works without the engine (offline=True
        or engine closed): characters are then named, not checked."""
        self.reload_if_changed()
        sc = parse_script(text) if isinstance(text, str) else text
        voices = None if offline else self.voices_or_none()
        warnings = [dict(w) for w in sc['warnings']]
        chars, lines, used = {}, [], {}
        unknown_moods, review = set(), {}
        est, said = 0.0, 0                     # an estimate of the render's length, in seconds
        for it in sc['items']:
            if it['kind'] == 'pause':
                lines.append({'kind': 'pause', 'n': it['n'], 'seconds': it['seconds']})
                est += it['seconds']
                continue
            who = it['who']
            if said:
                est += sc['gap']
            said += 1
            if who not in chars:
                chars[who] = self.character(who, sc['cast'], voices)
                if chars[who].get('warning'):
                    warnings.append(dict(chars[who]['warning'], n=it['n']))
            char = chars[who]
            for m in it['moods']:
                if m not in self.moods:
                    unknown_moods.add((it['n'], m))
            for m in re.findall(r'\[([^\]]*)\]', it['text']):
                for name in re.split(r'[\s,]+', m.lower()):
                    if name and name not in self.moods:
                        unknown_moods.add((it['n'], name))
            notes = []
            sents = []
            for p in self.plan(it['text'], it['moods'], sc['sentence_gap'], who, char, voices, notes):
                words = []
                for w in p['words']:
                    if not isinstance(w, dict) or w.get('stutter'):
                        continue
                    words.append({'word': w['word'], 'kana': ''.join(w['moras']), 'source': w.get('source')})
                    if w.get('source') in (SOURCE_MODEL, SOURCE_SPELLED):
                        key = (w.get('lookup') or w['word']).lower()
                        review.setdefault(key, {'word': key, 'kana': ''.join(w['moras']), 'source': w['source'], 'lines': []})
                        if it['n'] not in review[key]['lines']:
                            review[key]['lines'].append(it['n'])
                sents.append({'text': caption_text(p['seg']['body'] + p['seg']['sep']), 'kana': p['kana'],
                              'japanese': p['japanese'], 'moods': p['seg']['moods'], 'style': p['style_name'],
                              'style_id': p['style']['id'] if p['style'] else None, 'how': p['style_how'],
                              'pause': p['seg']['pause'], 'words': words})
                if p['style'] is not None and char.get('speaker'):
                    used.setdefault(char['speaker']['name'], set()).add(p['style']['name'])
                # About 0.155 s a mora at speed 1.0, measured on the shipped samples.
                speed = float(p['mood'].get('speed', 1.0)) or 1.0
                est += (len(p['kana']) if p['japanese'] else p['moras']) * 0.155 / speed + p['seg']['pause']
            for nt in notes:
                warnings.append({'n': it['n'], 'code': 'unreadable_text', 'text': nt['unreadable']})
            if not sents:
                warnings.append({'n': it['n'], 'code': 'nothing_to_say', 'text': it['text']})
            lines.append({'kind': 'line', 'n': it['n'], 'who': who, 'moods': it['moods'], 'text': it['text'],
                          'caption': caption_text(re.sub(r'\[[^\]]*\]|\([^)]*\)', '', it['text'])),
                          'character': char.get('name'), 'origin': char.get('origin'),
                          'speaker_uuid': char['speaker']['speaker_uuid'] if char.get('speaker') else None,
                          'sentences': sents})
        for n, m in sorted(unknown_moods):
            warnings.append({'n': n, 'code': 'unknown_mood', 'mood': m})
        if self.kana.c2k is None and review:
            warnings.append({'n': None, 'code': 'no_model'})
        cast = []
        for who, c in chars.items():
            cast.append({'who': who, 'character': c.get('name'), 'origin': c.get('origin'),
                         'style': c.get('style'), 'adjust': c.get('adjust') or {},
                         'speaker_uuid': c['speaker']['speaker_uuid'] if c.get('speaker') else None,
                         'found': c.get('speaker') is not None})
        credits = []
        if voices is not None:
            for name in used:
                sp = voices.find(name)
                if sp is not None:
                    credits.append(dict(self.credit(sp), name=name, styles=sorted(used[name])))
        warnings.sort(key=lambda w: (w.get('n') is None, w.get('n') or 0))
        return {'gap': sc['gap'], 'sentence_gap': sc['sentence_gap'], 'lines': lines, 'cast': cast,
                'script_cast': {k: {kk: vv for kk, vv in v.items() if kk != 'n'} for k, v in sc['cast'].items()},
                'warnings': warnings + [dict(w, n=None) for w in self.cfg_warnings],
                'review': sorted(review.values(), key=lambda r: r['lines'][0]),
                'credits': credits, 'engine': voices is not None,
                'duration_hint': round(est + (0.3 if said else 0.0), 1)}

    # --------------------------------------------------------------
    # Speaking
    # --------------------------------------------------------------
    def speak(self, text, moods=(), sentence_gap=None):
        return self.speak_timed(text, moods, sentence_gap)[:2]

    def _phrases(self, p, sid, notes):
        """The engine's accent phrases for a planned sentence. If the engine
        refuses the kana notation, read the same katakana a simpler way
        rather than failing the render."""
        if p['japanese']:
            return self.engine.accent_phrases(p['kana'], sid, is_kana=False), []
        try:
            return self.engine.accent_phrases(p['kana'], sid), p['spans']
        except EngineError as e:
            if e.kind == 'down' or e.code not in (400, 422, 500):
                raise
            first = e
        # 1) every phrase accented on its first mora
        flat = re.sub(r"'", '', p['kana'])
        simple = '/'.join(ph[:1] + "'" + ph[1:] if ph else ph for ph in re.split(r'[/、]', flat.rstrip('？')))
        if p['seg']['question']:
            simple += '？'
        try:
            aps = self.engine.accent_phrases(simple, sid)
            notes.append({'code': 'kana_simplified', 'kana': p['kana'], 'detail': first.detail})
            return aps, p['spans']
        except EngineError as e:
            if e.kind == 'down':
                raise
        # 2) the katakana as plain text, read by the engine's own reader
        plain = re.sub(r"['/、？]", ' ', p['kana']).strip()
        aps = self.engine.accent_phrases(plain + ('？' if p['seg']['question'] else ''), sid, is_kana=False)
        n = sum(len(ap['moras']) for ap in aps)
        notes.append({'code': 'kana_plain', 'kana': p['kana'], 'detail': first.detail})
        return aps, (p['spans'] if n == p['moras'] else [])

    def speak_timed(self, text, moods=(), sentence_gap=None, who='ME', char=None, voices=None,
                    notes=None, cancel=None):
        """The audio, and when each sentence and word is said in it:
        [{'text', 'start', 'end', 'words': [{'word', 'start', 'end'}]}]."""
        if voices is None:
            voices = self.voices()
        if char is None:
            char = self.character(who, None, voices)
        if char.get('speaker') is None:
            raise RenderError('No voice for %s: VOICEVOX has no characters.' % who, code='no_voice', kind='voice')
        notes = notes if notes is not None else []
        out, sentences, n = [], [], 0
        sr = SR
        for i, p in enumerate(self.plan(text, moods, sentence_gap, who, char, voices, notes)):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            mood = p['mood']
            sid = p['style']['id']
            aps, spans = self._phrases(p, sid, notes)
            shape(aps, spans, mood, p['seg'], seed=zlib.crc32(p['kana'].encode('utf-8')),
                  accent_of=lambda w: loanword_accent(w['moras']))
            q = self.engine.template(sid)
            q['accent_phrases'] = aps
            q['speedScale'] = float(mood.get('speed', 1.0))
            q['intonationScale'] = float(mood.get('intonation', 1.3))
            q['pitchScale'] = 0.0                    # pitch is moved in semitones by shape()
            q['volumeScale'] = float(mood.get('volume', 1.0))
            q['prePhonemeLength'] = 0.05
            q['postPhonemeLength'] = 0.05
            q['pauseLengthScale'] = float(mood.get('pauses', 0.8))
            q['outputSamplingRate'] = SR
            q['outputStereo'] = False
            q.pop('kana', None)
            x, xsr = wav_to_array(self.engine.synthesis(q, sid))
            if xsr != SR:
                x = resample(x, xsr, SR)
            a, b = trim_bounds(x, sr)
            times, total = mora_times(aps, q)
            scale = len(x) / sr / total if total else 1.0    # 1.0 unless the engine times differently
            start, length = n / sr, (b - a) / sr

            def at(sec, start=start, length=length, a=a, scale=scale):
                return start + min(max(sec * scale - a / sr, 0.0), length)

            words = []
            if spans:
                for w, j, k in sorted(spans, key=lambda s: s[1]):
                    if j >= len(times) or k - 1 >= len(times):
                        continue
                    if words and words[-1].pop('stutter', False):  # "W-" and "Wait" are one word
                        words[-1]['end'] = at(times[k - 1][1])
                        continue
                    words.append({'word': w['word'], 'start': at(times[j][0]), 'end': at(times[k - 1][1])})
                    if w.get('stutter'):
                        words[-1]['stutter'] = True
                for w in words:
                    w.pop('stutter', None)
            else:
                # Japanese, or a sentence read the plain way: one "word" per
                # accent phrase, which is how the engine grouped the sounds.
                k = 0
                for ap in aps:
                    if not ap['moras']:
                        continue
                    j, k = k, k + len(ap['moras'])
                    if k - 1 < len(times):
                        words.append({'word': ''.join(m.get('text', '') for m in ap['moras']),
                                      'start': at(times[j][0]), 'end': at(times[k - 1][1])})
            sentences.append({'text': caption_text(p['seg']['body'] + p['seg']['sep']),
                              'start': start, 'end': start + length, 'words': words,
                              'style': p['style_name'], 'style_id': sid})
            out.append(x[a:b])
            out.append(np.zeros(int(p['seg']['pause'] * sr), np.float32))
            n += (b - a) + len(out[-1])
        if not out:
            return np.zeros(int(0.2 * sr), np.float32), sr, []
        return np.concatenate(out), sr, sentences

    # --------------------------------------------------------------
    # Rendering a whole script
    # --------------------------------------------------------------
    def render_script(self, source, out_dir, progress=None, cancel=None, script_name=None):
        """source: a path to a .txt or the script text itself."""
        self.reload_if_changed()
        if isinstance(source, str) and '\n' not in source and os.path.isfile(source):
            text, _enc = cfgmod.read_text(source)
            script_name = script_name or os.path.splitext(os.path.basename(source))[0]
        else:
            text = source
        sc = parse_script(text)
        report = progress or (lambda ev: None)
        voices = self.voices()
        lines = [it for it in sc['items'] if it['kind'] == 'line']
        if not lines:
            raise RenderError('The script has no lines to say.', code='empty_script')
        chars = {}
        warnings = [dict(w) for w in sc['warnings']]
        for it in lines:
            if it['who'] not in chars:
                chars[it['who']] = self.character(it['who'], sc['cast'], voices)
                if chars[it['who']].get('warning'):
                    warnings.append(dict(chars[it['who']]['warning'], n=it['n']))
        # Load every voice first: the first use of a voice takes seconds
        # while the engine reads its model, and progress should say so.
        styles = {}
        for it in lines:
            for p in self.plan(it['text'], it['moods'], sc['sentence_gap'], it['who'], chars[it['who']], voices):
                if p['style'] is not None:
                    styles[p['style']['id']] = (chars[it['who']]['name'], p['style']['name'])
        for k, (sid, (name, style)) in enumerate(styles.items(), 1):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            report({'stage': 'voice', 'i': k, 'total': len(styles), 'text': '%s (%s)' % (name, style)})
            self.engine.initialize(sid)
        os.makedirs(out_dir, exist_ok=True)
        pieces, timing, files, t, sr, n = [], [], [], 0.0, SR, 0
        used = {}
        width = max(2, len(str(len(lines))))
        for it in sc['items']:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            if it['kind'] == 'pause':
                pieces.append(np.zeros(int(it['seconds'] * sr), np.float32))
                t += len(pieces[-1]) / sr
                continue
            n += 1
            char = chars[it['who']]
            report({'stage': 'line', 'i': n, 'total': len(lines), 'n': it['n'], 'who': it['who'],
                    'character': char.get('name'), 'text': it['text']})
            notes = []
            try:
                x, sr, sentences = self.speak_timed(it['text'], it['moods'], sc['sentence_gap'], it['who'],
                                                    char, voices, notes, cancel)
            except EngineError as e:
                raise RenderError('Line %d: %s' % (it['n'], e), n=it['n'], code=e.code,
                                  kind='down' if e.kind == 'down' else 'error')
            for nt in notes:
                warnings.append(dict(nt, n=it['n']))
            name = '%0*d_%s.wav' % (width, n, safe_name(it['who'], 'LINE'))
            files.append((name, x))
            if pieces:
                pieces.append(np.zeros(int(sc['gap'] * sr), np.float32))
                t += len(pieces[-1]) / sr
            caption = caption_text(re.sub(r'\[[^\]]*\]|\([^)]*\)', '', it['text']))
            for s in sentences:                       # line time -> time in full.wav
                s['start'], s['end'] = t + s['start'], t + s['end']
                for w in s['words']:
                    w['start'], w['end'] = t + w['start'], t + w['end']
                used.setdefault(char['name'], set()).add(s.get('style'))
            timing.append({'start': t, 'end': t + len(x) / sr, 'who': it['who'], 'caption': caption, 'file': name,
                           'sentences': sentences, 'character': char.get('name'), 'n': it['n']})
            pieces.append(x)
            t += len(x) / sr
        report({'stage': 'write', 'i': 0, 'total': 1})
        full = np.concatenate(pieces + [np.zeros(int(0.3 * sr), np.float32)])
        # One gain for everything: a whispered line stays quieter than a shout.
        peak = float(np.max(np.abs(full))) or 1.0
        gain = 0.89 / peak
        write_wav(os.path.join(out_dir, 'full.wav'), full * gain, sr)
        for name, x in files:
            write_wav(os.path.join(out_dir, name), x * gain, sr)
        keep = {name for name, _x in files}
        for f in os.listdir(out_dir):                  # line files a longer earlier render left
            if re.fullmatch(r'\d{2,}_.+\.wav', f) and f not in keep:
                try:
                    os.remove(os.path.join(out_dir, f))
                except OSError:
                    pass
        credits = []
        for cname in used:
            sp = voices.find(cname)
            if sp is not None:
                credits.append(dict(self.credit(sp), name=cname, styles=sorted(x for x in used[cname] if x)))
        self._write_texts(out_dir, timing, full, sr, credits, text)
        result = {'dir': out_dir, 'name': os.path.basename(out_dir.rstrip('/\\')), 'length': len(full) / sr,
                  'lines': len(timing), 'warnings': warnings, 'credits': credits,
                  'files': sorted(os.listdir(out_dir))}
        report({'stage': 'done', 'i': 1, 'total': 1})
        return result

    def _write_texts(self, out_dir, timing, full, sr, credits, script_text):
        def put(name, text):
            write_file(os.path.join(out_dir, name), text.encode('utf-8'))
        rows = timing
        put('captions.srt', ''.join('%d\n%s --> %s\n%s\n\n' % (i, srt_time(r['start']), srt_time(r['end']), r['caption'])
                                    for i, r in enumerate(rows, 1)))
        # The same, one caption per sentence: what a video should follow.
        cues = [s for r in rows for s in r['sentences']]
        put('sentences.srt', ''.join('%d\n%s --> %s\n%s\n\n' % (i, srt_time(s['start']), srt_time(s['end']), s['text'])
                                     for i, s in enumerate(cues, 1)))
        put('captions.vtt', 'WEBVTT\n\n' + ''.join('%s --> %s\n%s\n\n' % (vtt_time(r['start']), vtt_time(r['end']), r['caption'])
                                                   for r in rows))
        put('sentences.vtt', 'WEBVTT\n\n' + ''.join('%s --> %s\n%s\n\n' % (vtt_time(s['start']), vtt_time(s['end']), s['text'])
                                                    for s in cues))
        # Every line, sentence and word with its start and end in full.wav (seconds).
        r3 = lambda v: round(v, 3)
        doc = {'length': r3(len(full) / sr), 'lines': [
            {'file': r['file'], 'who': r['who'], 'text': r['caption'], 'start': r3(r['start']), 'end': r3(r['end']),
             'character': r['character'], 'line': r['n'],
             'sentences': [
                 {'text': s['text'], 'start': r3(s['start']), 'end': r3(s['end']), 'style': s.get('style'),
                  'words': [{'word': wd['word'], 'start': r3(wd['start']), 'end': r3(wd['end'])} for wd in s['words']]}
                 for s in r['sentences']]}
            for r in rows],
            'credits': [c['credit'] for c in credits],
            'made_with': 'Vocana'}
        put('timing.json', json.dumps(doc, ensure_ascii=False, indent=1))
        put('timing.txt', ''.join('%6.2fs - %6.2fs  %-4s %s\n' % (r['start'], r['end'], r['who'], r['caption']) for r in rows))
        lines = [c['credit'] for c in credits]
        put('credits.txt', '\n'.join(lines) + '\n' if lines else '')
        put('script.txt', script_text if script_text.endswith('\n') else script_text + '\n')
