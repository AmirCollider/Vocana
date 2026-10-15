"""
The script format.

    # comments start with #
    gap = 0.4                         silence between lines (seconds)
    sentence_gap = 0.5                silence between the sentences of a line
    @cast ME = ずんだもん               who says the lines tagged ME
    @cast METAN = 四国めたん / ツンツン, pitch +1, speed 1.05
    ME [excited]: Hello! I'm *really* happy~
    METAN [smug]: Hmph. (pause 0.5) Fine.
    (pause 1.0)                       silence on its own line

A script written for VoxTalk is a valid Vocana script and renders the same:
everything above except @cast was already there. A line with no tag is
said by ME, as before.

The parser never refuses a script. Anything it does not understand becomes
a warning with a line number, and the studio shows it next to that line.
"""

import re

from .config import CAST_RANGES

# A speaker tag: letters (Latin or Japanese), digits, _ - . after the
# first letter. "No.7" and "ずんだもん" are tags; "3D" is not.
TAG = r"[A-Za-z_぀-ヿ一-鿿ｦ-ﾟ][\w\-.぀-ヿ一-鿿ｦ-ﾟ・ー]*"
LINE = re.compile(r'^\s*(?:(?P<who>' + TAG + r')\s*)?(?:\[(?P<moods>[^\]]*)\])?\s*[:：]\s*(?P<text>.+)$')
PAUSE_LINE = re.compile(r'^\(\s*pause\s+([\d.]+)\s*s?\s*\)$', re.I)
SETTING = re.compile(r'^(sentence_gap|gap)\s*[=:]\s*([\d.]+)\s*s?$', re.I)
CAST = re.compile(r'^@?\s*cast\s+(?P<tag>' + TAG + r')\s*[=:：]\s*(?P<spec>.*)$', re.I)
DIRECTIVE = re.compile(r'^@\s*(\w+)')
OPTION = re.compile(r'^(pitch|speed|volume|intonation)\s*[=:]?\s*([+\-]?\d+(?:\.\d+)?|[+\-]?\.\d+)$', re.I)


def parse_cast_spec(spec):
    """'四国めたん / ツンツン, pitch +1, speed 1.05' -> dict, [problems]."""
    problems = []
    parts = [p.strip() for p in re.split(r'[,،、]', spec) if p.strip()]
    if not parts:
        return None, ['empty']
    # "name / style" is split later, by whoever knows the engine's
    # characters: "小夜/SAYO" is one character's whole name.
    out = {'speaker': parts[0]}
    for p in parts[1:]:
        m = OPTION.match(p)
        if not m:
            problems.append(p)
            continue
        k, v = m.group(1).lower(), float(m.group(2))
        lo, hi = CAST_RANGES[k]
        if v < lo or v > hi:
            problems.append(p)
            v = min(max(v, lo), hi)
        out[k] = v
    if not out.get('speaker'):
        return None, ['empty']
    return out, problems


def parse_script(text):
    """{'gap', 'sentence_gap', 'cast', 'items', 'warnings'}.

    items: {'kind': 'line', 'n': line number, 'who', 'moods', 'text'}
           {'kind': 'pause', 'n': line number, 'seconds'}
    cast:  {TAG: {'speaker', 'style'?, 'pitch'?, ...}} declared in the script
    """
    gap, sentence_gap = 0.6, None
    items, cast, warnings = [], {}, []
    for n, raw in enumerate(text.splitlines(), 1):
        s = raw.strip().lstrip('﻿')
        if not s or s.startswith('#'):
            continue
        m = PAUSE_LINE.match(s)
        if m:
            try:
                items.append({'kind': 'pause', 'n': n, 'seconds': min(float(m.group(1)), 60.0)})
            except ValueError:
                warnings.append({'n': n, 'code': 'bad_number', 'text': s})
            continue
        m = SETTING.match(s)
        if m:
            try:
                v = min(float(m.group(2)), 30.0)
            except ValueError:
                warnings.append({'n': n, 'code': 'bad_number', 'text': s})
                continue
            if m.group(1).lower() == 'gap':
                gap = v
            else:
                sentence_gap = v
            continue
        m = CAST.match(s)
        if m:
            spec, problems = parse_cast_spec(m.group('spec'))
            tag = m.group('tag').upper()
            if spec is None:
                warnings.append({'n': n, 'code': 'bad_cast', 'who': tag, 'text': s})
            else:
                cast[tag] = dict(spec, n=n)
                for p in problems:
                    warnings.append({'n': n, 'code': 'bad_cast_option', 'who': tag, 'text': p})
            continue
        m = DIRECTIVE.match(s)
        if m:
            warnings.append({'n': n, 'code': 'unknown_directive', 'text': s})
            continue
        m = LINE.match(s)
        if m and (m.group('who') or m.group('moods')):
            moods = [x.lower() for x in re.split(r'[\s,]+', m.group('moods') or '') if x]
            items.append({'kind': 'line', 'n': n, 'who': (m.group('who') or 'ME').upper(),
                          'moods': moods, 'text': m.group('text').strip()})
        else:
            items.append({'kind': 'line', 'n': n, 'who': 'ME', 'moods': [], 'text': s})
    return {'gap': gap, 'sentence_gap': sentence_gap, 'cast': cast, 'items': items, 'warnings': warnings}


def cast_line(tag, spec):
    """The @cast line for a cast entry - what the studio writes back."""
    head = spec['speaker']
    if spec.get('style'):
        head += ' / ' + spec['style']
    opts = []
    for k in ('pitch', 'speed', 'volume', 'intonation'):
        if k in spec and spec[k] is not None:
            v = float(spec[k])
            neutral = 0.0 if k == 'pitch' else 1.0
            if abs(v - neutral) < 1e-9:
                continue
            txt = ('%+g' % v) if k == 'pitch' else ('%g' % v)
            opts.append('%s %s' % (k, txt))
    return '@cast %s = %s' % (tag, ', '.join([head] + opts))
