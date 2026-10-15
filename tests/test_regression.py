"""
Vocana must sound exactly like VoxTalk did for everything VoxTalk could say.

  * test_kana: 503 sentences (tests/corpus.txt plus 400 random ones) give
    the same VOICEVOX kana, mood and pause as VoxTalk's own output, which
    fixtures/make_fixtures.py recorded from the original program.
  * test_sample_audio: the original sample script, rendered with the
    original words.json and moods.json, produces byte-identical WAV, SRT
    and timing files. Needs VOICEVOX 0.25.2 running on 127.0.0.1:50021
    (other engine versions synthesise differently); skipped otherwise.
  * test_sample_audio_new_moods: the same render with Vocana's shipped
    moods.json (which adds tones and new moods) is still byte-identical -
    the tones resolve to the very styles VoxTalk used for Zundamon.

Run:  python -m unittest discover -s tests   (from the product folder)
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app'))

from vocana.engine import Engine  # noqa: E402
from vocana.render import Vocana  # noqa: E402

FIX = os.path.join(HERE, 'fixtures')


def data_dir(moods='moods-voxtalk.json'):
    d = tempfile.mkdtemp(prefix='vocana-test-')
    shutil.copyfile(os.path.join(FIX, 'words-voxtalk.json'), os.path.join(d, 'words.json'))
    src = os.path.join(FIX, moods) if moods.endswith('voxtalk.json') else os.path.join(ROOT, 'app', 'vocana', 'defaults', 'moods.json')
    shutil.copyfile(src, os.path.join(d, 'moods.json'))
    return d


def engine_version():
    return Engine().alive(timeout=1)


class Kana(unittest.TestCase):
    def test_kana(self):
        vt = Vocana(data_dir=data_dir())
        with open(os.path.join(HERE, 'expected_kana.json'), encoding='utf-8') as f:
            cases = json.load(f)
        bad = []
        for c in cases:
            got = [['/'.join(p['seg']['moods']), p['kana'], p['seg']['pause']] for p in vt.plan(c['text'])]
            if got != c['plan']:
                bad.append((c['text'], c['plan'], got))
        self.assertEqual(bad, [], '%d of %d differ, first: %r' % (len(bad), len(cases), bad[:1]))


@unittest.skipUnless(engine_version() == '0.25.2', 'needs VOICEVOX 0.25.2 on 127.0.0.1:50021')
class SampleAudio(unittest.TestCase):
    def render(self, moods):
        d = data_dir(moods)
        out = os.path.join(d, 'out')
        vt = Vocana(data_dir=d)
        with open(os.path.join(FIX, 'Sample-voxtalk.txt'), encoding='utf-8') as f:
            text = f.read()
        vt.render_script(text, out)
        return out

    def check(self, out):
        want = {}
        with open(os.path.join(FIX, 'sample-voxtalk-0.25.2.sha256')) as f:
            for line in f:
                h, name = line.split()
                want[name] = h
        for name, h in want.items():
            with open(os.path.join(out, name), 'rb') as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), h, name)

    def test_sample_audio(self):
        self.check(self.render('moods-voxtalk.json'))

    def test_sample_audio_new_moods(self):
        self.check(self.render('shipped'))


if __name__ == '__main__':
    unittest.main()
