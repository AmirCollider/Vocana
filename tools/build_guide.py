"""
Builds Guide.html - the offline guide in the product folder - from
tools/guide/ (shell, CSS, JS and one HTML body per language).

    python tools/build_guide.py

Everything the guide needs is put inside the one file - the Persian font,
the logo, the sample render's timing, the shipped moods - so it opens by
double-click with no server and no internet. Only renders/Sample/full.wav
is read from beside it.
"""

import base64
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
G = os.path.join(HERE, 'guide')
sys.path.insert(0, os.path.join(ROOT, 'app'))

from vocana import VERSION, RELEASE_DATE  # noqa: E402


def read(*p, mode='r'):
    with open(os.path.join(*p), mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


def b64(*p):
    return base64.b64encode(read(*p, mode='rb')).decode('ascii')


def main():
    timing = json.loads(read(ROOT, 'renders', 'Sample', 'timing.json'))
    slim = {'length': timing['length'], 'lines': [
        {'who': l['who'], 'character': l.get('character'), 'text': l['text'], 'start': l['start'], 'end': l['end'],
         'sentences': [{'start': s['start'], 'end': s['end'], 'text': s['text'],
                        'words': [{'word': w['word'], 'start': w['start'], 'end': w['end']} for w in s['words']]}
                       for s in l['sentences']]} for l in timing['lines']]}
    moods = json.loads(read(ROOT, 'app', 'vocana', 'defaults', 'moods.json'))['moods']
    js = read(G, 'guide.js').replace('__SAMPLE_TIMING__', json.dumps(slim, ensure_ascii=False)) \
                            .replace('__MOODS__', json.dumps(moods, ensure_ascii=False))
    css = read(G, 'guide.css').replace('__FONT_B64__', b64(ROOT, 'app', 'fonts', 'Vazirmatn-Variable.woff2'))
    html = read(G, 'shell.html')
    for key, val in (('__CSS__', css), ('__JS__', js), ('__FA__', read(G, 'fa.html')), ('__EN__', read(G, 'en.html')),
                     ('__JA__', read(G, 'ja.html'))):
        html = html.replace(key, val)
    html = html.replace('__LOGO_B64__', b64(ROOT, 'app', 'brand', 'vocana-256.webp'))
    html = html.replace('__VERSION__', VERSION).replace('__DATE__', RELEASE_DATE)
    left = [k for k in ('__FONT_B64__', '__LOGO_B64__', '__SAMPLE_TIMING__', '__MOODS__', '__VERSION__', '__DATE__', '__CSS__', '__JS__') if k in html]
    if left:
        raise SystemExit('placeholders left: %s' % left)
    with open(os.path.join(ROOT, 'Guide.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(html)
    print('Guide.html: %.0f KB' % (len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
