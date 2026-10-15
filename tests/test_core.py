"""
The parts of Vocana that need no engine: text rules, the script format,
characters and moods, the user's files. Real engine data (the character
list and every character's terms from VOICEVOX 0.25.2) is in fixtures/.

Run:  python -m unittest discover -s tests   (from the product folder)
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app'))

from vocana import config as cfgmod  # noqa: E402
from vocana.kana import Kana  # noqa: E402
from vocana.render import Vocana, safe_name, srt_time, vtt_time  # noqa: E402
from vocana.script import parse_script, cast_line  # noqa: E402
from vocana.text import split_line, speakable, fold  # noqa: E402
from vocana.voices import Voices, policy_summary, FAMILY_OF  # noqa: E402

FIX = os.path.join(HERE, 'fixtures')
DEFAULTS = os.path.join(ROOT, 'app', 'vocana', 'defaults')


def load(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return json.load(f)


def tmpdata():
    d = tempfile.mkdtemp(prefix='vocana-core-')
    for n in ('words.json', 'moods.json'):
        shutil.copyfile(os.path.join(DEFAULTS, n), os.path.join(d, n))
    return d


class Text(unittest.TestCase):
    def setUp(self):
        self.vt = Vocana(data_dir=tmpdata(), engine_url='http://127.0.0.1:9')   # nothing listens on port 9

    def kana(self, text):
        return [p['kana'].replace("'", '').replace('/', '') for p in self.vt.plan(text)]

    def test_dot_is_not_a_sentence_end(self):
        for text in ('Mr. Smith is here.', 'Version 2.5 is out.', 'Visit amircollider.com today!', 'Cats, dogs, etc. are fine.'):
            self.assertEqual(len(split_line(text, ['normal'])), 1, text)

    def test_written_forms_are_said(self):
        self.assertIn('ポイント', ''.join(self.kana('It is 2.5 now.')))
        self.assertIn('ドット', ''.join(self.kana('Go to amircollider.com')))
        self.assertIn('パアセント', ''.join(self.kana('Fifty 50% off')))
        self.assertIn('ダラアズ', ''.join(self.kana('It costs $5.')))
        self.assertIn('Mister', speakable('Mr. Smith'))

    def test_full_width_and_accents(self):
        self.assertEqual(fold('Ｈｅｌｌｏ'), 'Hello')
        self.assertEqual(fold('café'), 'cafe')
        self.assertEqual(fold('ｶﾞｷﾞ'), 'ガギ')           # voicing marks survive
        self.assertEqual(self.kana('Ｈｅｌｌｏ！'), self.kana('Hello!'))

    def test_ordinals_and_mixed_tokens(self):
        k = Kana({})
        self.assertEqual(k.lookup('1st')[1], 'number')
        self.assertTrue(k.word('mp3').endswith('スリー'))
        self.assertTrue(k.word('21st'))

    def test_japanese_sentence_goes_to_the_engine_reader(self):
        segs = split_line('今日はいい天気ですね。', ['normal'])
        self.assertTrue(segs[0]['japanese'])
        self.assertFalse(split_line('Hehe ♡ エヘヘ', ['normal'])[0]['japanese'])
        self.assertFalse(split_line('ヴァイオリン ヵ', ['normal'])[0]['japanese'])

    def test_unreadable_text_is_reported_not_spoken(self):
        notes = []
        segs = split_line('Hello! سلام دنیا.', ['normal'], notes=notes)
        self.assertEqual(len(segs), 1)
        self.assertEqual(notes, [{'unreadable': 'سلام دنیا'}])
        self.assertEqual(segs[-1]['pause'], 0.0)       # no trailing silence for the skipped part


class Script(unittest.TestCase):
    def test_voxtalk_scripts_parse_the_same(self):
        with open(os.path.join(FIX, 'Sample-voxtalk.txt'), encoding='utf-8') as f:
            sc = parse_script(f.read())
        lines = [it for it in sc['items'] if it['kind'] == 'line']
        self.assertEqual(len(lines), 8)
        self.assertEqual(sc['gap'], 0.4)
        self.assertEqual(lines[0]['who'], 'ME')
        self.assertEqual(lines[0]['moods'], ['excited'])
        self.assertEqual(sc['warnings'], [])

    def test_cast_lines(self):
        sc = parse_script('@cast METAN = 四国めたん / ツンツン, pitch +1, speed 1.05\n'
                          'cast zunda: zundamon\n'
                          '@cast SAYO = 小夜/SAYO\n'
                          '@cast BAD = \n'
                          '@cast X = ずんだもん, loud\n'
                          'METAN [smug]: Hmph.\n')
        self.assertEqual(sc['cast']['METAN']['speaker'], '四国めたん / ツンツン')
        self.assertEqual(sc['cast']['METAN']['pitch'], 1.0)
        self.assertEqual(sc['cast']['METAN']['speed'], 1.05)
        self.assertEqual(sc['cast']['ZUNDA']['speaker'], 'zundamon')
        self.assertEqual(sc['cast']['SAYO']['speaker'], '小夜/SAYO')
        codes = [w['code'] for w in sc['warnings']]
        self.assertEqual(sorted(codes), ['bad_cast', 'bad_cast_option'])
        self.assertEqual(len([it for it in sc['items'] if it['kind'] == 'line']), 1)   # no @cast line is spoken

    def test_tags_and_colons(self):
        sc = parse_script('ずんだもん [happy]：こんにちは\nNo.7: Hello.\n﻿ME: BOM line\n@title Nope\n# comment\n(pause 1.5)\n')
        lines = [it for it in sc['items'] if it['kind'] == 'line']
        self.assertEqual([l['who'] for l in lines], ['ずんだもん', 'NO.7', 'ME'])
        self.assertEqual(sc['items'][-1], {'kind': 'pause', 'n': 6, 'seconds': 1.5})
        self.assertEqual([w['code'] for w in sc['warnings']], ['unknown_directive'])

    def test_cast_line_round_trip(self):
        line = cast_line('METAN', {'speaker': '四国めたん', 'style': 'ツンツン', 'pitch': 1.0, 'speed': 1.0, 'volume': 0.9})
        self.assertEqual(line, '@cast METAN = 四国めたん / ツンツン, pitch +1, volume 0.9')
        self.assertEqual(parse_script(line)['cast']['METAN']['volume'], 0.9)


class Characters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.voices = Voices(load('speakers-0.25.2.json'))
        cfg, warnings = cfgmod.load_moods(os.path.join(DEFAULTS, 'moods.json'))
        assert not warnings, warnings
        cls.moods = cfg['moods']

    def mood(self, name):
        m = dict(self.moods['normal'])
        m.update(self.moods[name])
        return m

    def test_every_style_has_a_family(self):
        missing = sorted({st['name'] for sp in self.voices.speakers for st in sp['styles']} - set(FAMILY_OF))
        self.assertEqual(missing, [], 'add these styles to FAMILIES in voices.py')

    def test_every_character_every_mood_resolves(self):
        for sp in self.voices.speakers:
            names = {st['name'] for st in sp['styles']}
            for m in self.moods:
                st, _how = self.voices.resolve(sp, self.mood(m))
                self.assertIn(st['name'], names, (sp['name'], m))

    def test_zundamon_keeps_voxtalk_styles(self):
        zunda = self.voices.find('ずんだもん')
        old = load('moods-voxtalk.json')['moods']
        # sad and defeated were changed on purpose: they borrowed なみだめ,
        # which trembles on every vowel, and the owner heard them as shaky
        # and broken. They are low and flat ノーマル now. A VoxTalk user's
        # own moods.json is kept as it is, so their renders do not change.
        changed = {'sad', 'defeated'}
        for m, spec in old.items():
            if m in changed:
                continue
            st, _how = self.voices.resolve(zunda, self.mood(m))
            self.assertEqual(st['name'], spec.get('style', 'ノーマル'), m)

    def test_tones_use_each_characters_own_styles(self):
        def style(char, mood):
            return self.voices.resolve(self.voices.find(char), self.mood(mood))[0]['name']
        self.assertEqual(style('玄野武宏', 'happy'), '喜び')
        self.assertEqual(style('白上虎太郎', 'excited'), 'わーい')
        self.assertEqual(style('ユーレイちゃん', 'cute'), '甘々')
        self.assertEqual(style('中部つるぎ', 'defeated'), '絶望と敗北')
        self.assertEqual(style('猫使ビィ', 'shy'), '人見知り')
        self.assertEqual(style('春日部つむぎ', 'whisper'), 'ノーマル')   # one style only: it is used

    def test_cast_base_style_replaces_normal(self):
        metan = self.voices.find('metan')
        st, _ = self.voices.resolve(metan, self.mood('normal'), 'ツンツン')
        self.assertEqual(st['name'], 'ツンツン')
        st, _ = self.voices.resolve(metan, self.mood('cute'), 'ツンツン')
        self.assertEqual(st['name'], 'あまあま')

    def test_find_by_alias_and_id(self):
        self.assertEqual(self.voices.find('Zundamon')['name'], 'ずんだもん')
        self.assertEqual(self.voices.find('shikoku metan')['name'], '四国めたん')
        self.assertEqual(self.voices.find('3')['name'], 'ずんだもん')
        self.assertEqual(self.voices.find('小夜/SAYO')['name'], '小夜/SAYO')
        self.assertIsNone(self.voices.find('nobody'))

    def test_credit_lines_from_terms(self):
        pol = load('policies-0.25.2.json')
        self.assertEqual(policy_summary('Voidoll', pol['Voidoll'])['credit'], 'VOICEVOX:Voidoll(CV:丹下桜)')
        self.assertEqual(policy_summary('里石ユカ', pol['里石ユカ'])['credit'], 'VOICEVOX:里石ユカ（つぼみ）')
        flagged = sorted(n for n, p in pol.items() if policy_summary(n, p)['conditions'])
        self.assertEqual(flagged, sorted(['青山龍星', 'もち子さん', '後鬼', 'No.7', 'Voidoll', 'ぞん子', 'ユーレイちゃん']))
        self.assertEqual(policy_summary('X', '')['credit'], 'VOICEVOX:X')


class Files(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='vocana-files-')

    def path(self, name):
        return os.path.join(self.d, name)

    def test_notepad_bom_and_encodings(self):
        with open(self.path('w.json'), 'wb') as f:
            f.write('﻿{"hello": "ハロー"}'.encode('utf-8'))
        words, warnings = cfgmod.load_words(self.path('w.json'))
        self.assertEqual(words, {'hello': 'ハロー'})
        self.assertEqual(warnings, [])
        with open(self.path('s.txt'), 'wb') as f:
            f.write('ME: Hello ♡'.encode('utf-16'))
        self.assertEqual(cfgmod.read_text(self.path('s.txt')), ('ME: Hello ♡', 'utf-16'))
        with open(self.path('a.txt'), 'wb') as f:
            f.write('ME: caf\xe9'.encode('cp1252'))
        self.assertEqual(cfgmod.read_text(self.path('a.txt'))[0], 'ME: café')

    def test_broken_json_falls_back_and_says_where(self):
        with open(self.path('moods.json'), 'w', encoding='utf-8') as f:
            f.write('{"moods": {"normal": {"speed": 1.0,}}}')
        cfg, warnings = cfgmod.load_moods(self.path('moods.json'))
        self.assertEqual(warnings[0]['code'], 'moods_invalid')
        self.assertIn('line 1', warnings[0]['message'])
        self.assertIn('excited', cfg['moods'])                 # the shipped moods, until it is fixed

    def test_out_of_range_values_are_clamped(self):
        with open(self.path('moods.json'), 'w', encoding='utf-8') as f:
            json.dump({'moods': {'normal': {'speed': 0, 'pitch': 40, 'volume': 'loud'}}}, f)
        cfg, warnings = cfgmod.load_moods(self.path('moods.json'))
        self.assertEqual(cfg['moods']['normal']['speed'], 0.5)
        self.assertEqual(cfg['moods']['normal']['pitch'], 12.0)
        self.assertNotIn('volume', cfg['moods']['normal'])
        self.assertEqual(sorted(w['code'] for w in warnings), ['mood_clamped', 'mood_clamped', 'mood_value'])

    def test_word_without_kana_is_ignored(self):
        with open(self.path('w.json'), 'w', encoding='utf-8') as f:
            json.dump({'_about': 'x', 'ok': 'オーケー', 'bad': 'abc', 'empty': ''}, f)
        words, warnings = cfgmod.load_words(self.path('w.json'))
        self.assertEqual(words, {'ok': 'オーケー'})
        self.assertEqual(sorted(w['code'] for w in warnings), ['word_empty', 'word_no_kana'])

    def test_atomic_save_keeps_notes(self):
        p = self.path('words.json')
        cfgmod.save_words(p, {'Zeta': 'ゼータ', 'alpha': 'アルファ'})
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(list(data), ['_about', 'alpha', 'zeta'])
        self.assertFalse([n for n in os.listdir(self.d) if n.endswith('.tmp')])

    def test_settings_types(self):
        p = self.path('settings.json')
        s = cfgmod.save_settings(p, {'lang': 'fa', 'port': 'x', 'app_window': 1, 'theme': 'neon'})
        self.assertEqual(s['lang'], 'fa')
        self.assertEqual(s['port'], 50210)
        self.assertIs(s['app_window'], True)
        self.assertEqual(s['theme'], 'auto')

    def test_safe_names_and_times(self):
        self.assertEqual(safe_name('CON'), 'render')
        self.assertEqual(safe_name('a/b:c*?'), 'a_b_c_')
        self.assertEqual(safe_name('小夜/SAYO'), '小夜_SAYO')
        self.assertEqual(srt_time(3661.5), '01:01:01,500')
        self.assertEqual(vtt_time(0.25), '00:00:00.250')


class Plan(unittest.TestCase):
    """plan_script with the engine closed: everything but the character check."""

    def test_offline_plan(self):
        vt = Vocana(data_dir=tmpdata(), engine_url='http://127.0.0.1:9')
        with open(os.path.join(DEFAULTS, 'scripts', 'Duet.txt'), encoding='utf-8') as f:
            plan = vt.plan_script(f.read())
        self.assertFalse(plan['engine'])
        lines = [l for l in plan['lines'] if l['kind'] == 'line']
        self.assertEqual(len(lines), 11)
        self.assertEqual({c['who'] for c in plan['cast']}, {'ZUNDA', 'METAN'})
        self.assertTrue(any(s['japanese'] for l in lines for s in l['sentences']))
        self.assertGreater(plan['duration_hint'], 20)

    def test_unknown_mood_warns_with_line(self):
        vt = Vocana(data_dir=tmpdata(), engine_url='http://127.0.0.1:9')
        plan = vt.plan_script('ME [happpy]: Hi!\nME: Hello [whisperr] there.')
        found = sorted((w['n'], w['mood']) for w in plan['warnings'] if w['code'] == 'unknown_mood')
        self.assertEqual(found, [(1, 'happpy'), (2, 'whisperr')])


if __name__ == '__main__':
    unittest.main()
