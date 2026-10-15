"""
The studio server: who may talk to it, and what it does when they do.
Runs a real server on a free port with a temporary data folder. The tests
that need sound are skipped when VOICEVOX is not running on 50021.
"""

import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'app'))

from vocana import server as srv  # noqa: E402
from vocana.engine import Engine  # noqa: E402
from vocana.paths import layout  # noqa: E402

ENGINE = Engine().alive(timeout=1)


class Studio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tempfile.mkdtemp(prefix='vocana-srv-')
        layout(cls.data)
        cls.st = srv.Studio(data_dir=cls.data)
        cls.httpd = srv.bind(cls.st, 0)
        cls.st.server = cls.httpd
        cls.port = cls.st.port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        shutil.rmtree(cls.data, ignore_errors=True)

    def req(self, method, path, body=None, token=True, headers=None, host=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=120)
        h = {'Host': host or '127.0.0.1:%d' % self.port}
        if token:
            h['X-Vocana-Token'] = self.st.token
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            h['Content-Type'] = 'application/json'
        h.update(headers or {})
        c.request(method, path, data, h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw.decode('utf-8')), r
        except ValueError:
            return r.status, raw, r

    # -- who may talk ---------------------------------------------------
    def test_token_required(self):
        self.assertEqual(self.req('GET', '/api/status', token=False)[0], 403)
        self.assertEqual(self.req('GET', '/api/status', headers={'X-Vocana-Token': 'nope'}, token=False)[0], 403)
        self.assertEqual(self.req('GET', '/api/status')[0], 200)

    def test_ping_needs_no_token(self):
        s, d, _ = self.req('GET', '/api/ping', token=False)
        self.assertEqual((s, d['app']), (200, 'Vocana'))

    def test_dns_rebinding_refused(self):
        self.assertEqual(self.req('GET', '/', token=False, host='evil.example:%d' % self.port)[0], 403)
        self.assertEqual(self.req('GET', '/api/status', host='attacker.test')[0], 403)
        self.assertEqual(self.req('GET', '/', token=False, host='localhost:%d' % self.port)[0], 200)

    def test_cross_origin_post_refused(self):
        s, d, _ = self.req('POST', '/api/settings', {'lang': 'fa'}, headers={'Origin': 'https://evil.example'})
        self.assertEqual((s, d['error']), (403, 'bad_origin'))

    def test_form_post_refused(self):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('POST', '/api/quit', 'x=1', {'Host': '127.0.0.1:%d' % self.port, 'X-Vocana-Token': self.st.token,
                                                 'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(c.getresponse().status, 415)
        c.close()

    def test_page_has_token_and_csp(self):
        s, raw, r = self.req('GET', '/', token=False)
        self.assertEqual(s, 200)
        self.assertIn(self.st.token.encode(), raw)
        self.assertIn("script-src 'self'", r.getheader('Content-Security-Policy'))
        self.assertEqual(r.getheader('X-Content-Type-Options'), 'nosniff')

    def test_static_types(self):
        for path, ctype in (('/static/app.js', 'text/javascript'), ('/static/app.css', 'text/css'),
                            ('/brand/vocana-64.png', 'image/png'), ('/fonts/Vazirmatn-Variable.woff2', 'font/woff2')):
            s, _raw, r = self.req('GET', path, token=False)
            self.assertEqual(s, 200, path)
            self.assertTrue(r.getheader('Content-Type').startswith(ctype), path)

    def test_path_traversal_refused(self):
        for path in ('/static/../vocana/server.py', '/static/..%2f..%2fvocana.py', '/brand/.hidden',
                     '/api/renders/..', '/api/renders/../../etc', '/api/scripts/..%2f..%2fwords',
                     '/renders/../app/launch.py'):
            s = self.req('GET', path)[0]
            self.assertIn(s, (403, 404), path)
        s, d, _ = self.req('POST', '/api/scripts/save', {'name': '../../evil', 'text': 'ME: hi'})
        self.assertEqual(s, 200)
        self.assertTrue(os.path.isfile(os.path.join(self.data, 'scripts', '.._.._evil.txt')) or
                        os.path.isfile(os.path.join(self.data, 'scripts', d['name'] + '.txt')))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.data), 'evil.txt')))

    # -- what it does ---------------------------------------------------
    def test_scripts_round_trip(self):
        s, d, _ = self.req('POST', '/api/scripts/save', {'name': 'Round trip', 'text': 'ME: Hello ♡\n'})
        self.assertEqual((s, d['name']), (200, 'Round trip'))
        s, d, _ = self.req('POST', '/api/scripts/save', {'name': 'Round trip', 'text': 'ME: Other\n'})
        self.assertEqual((s, d['error']), (409, 'exists'))
        s, d, _ = self.req('GET', '/api/scripts/Round%20trip')
        self.assertEqual(d['text'], 'ME: Hello ♡\n')
        names = [x['name'] for x in self.req('GET', '/api/scripts')[1]['scripts']]
        self.assertIn('Sample', names)

    def test_words_validation(self):
        s, d, _ = self.req('POST', '/api/words', {'words': {'Vocana': 'ボカナ', 'bad': '', 'x' * 200: 'ア'}})
        self.assertEqual(s, 200)
        self.assertEqual(d['words'], {'vocana': 'ボカナ'})
        s, d, _ = self.req('POST', '/api/words/test', {'text': 'Vocana says hello'})
        self.assertEqual([w['source'] for w in d['words']][0], 'dict')

    def test_moods_cannot_lose_normal(self):
        s, d, _ = self.req('POST', '/api/moods', {'moods': {'happy': {'speed': 1.1}}})
        self.assertEqual((s, d['error']), (400, 'normal_required'))
        s, d, _ = self.req('POST', '/api/moods/reset', {})
        self.assertIn('excited', d['moods'])

    def test_plan(self):
        s, d, _ = self.req('POST', '/api/plan', {'text': 'ME [excited]: Hello!\n(pause 1)\nME: Bye.'})
        self.assertEqual(s, 200)
        self.assertEqual([l['kind'] for l in d['lines']], ['line', 'pause', 'line'])

    def test_bad_json(self):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request('POST', '/api/plan', '{not json', {'Host': '127.0.0.1:%d' % self.port, 'X-Vocana-Token': self.st.token,
                                                     'Content-Type': 'application/json'})
        r = c.getresponse()
        self.assertEqual(r.status, 400)
        c.close()

    # -- with VOICEVOX --------------------------------------------------
    @unittest.skipUnless(ENGINE, 'VOICEVOX is not running')
    def test_voices_and_terms(self):
        s, d, _ = self.req('GET', '/api/voices')
        self.assertGreater(len(d['characters']), 0)
        z = next(c for c in d['characters'] if c['name'] == 'ずんだもん')
        s, info, _ = self.req('GET', '/api/voice?uuid=' + z['uuid'])
        self.assertEqual(info['credit'], 'VOICEVOX:ずんだもん')
        self.assertFalse(info['conditions'])
        icon = info['styles'][0]['icon']
        s, raw, r = self.req('GET', icon, token=False)
        self.assertEqual(s, 200)
        self.assertTrue(r.getheader('Content-Type').startswith('image/'))

    @unittest.skipUnless(ENGINE, 'VOICEVOX is not running')
    def test_preview_and_render(self):
        text = '@cast M = 四国めたん\nM [happy]: Hello there!\nME [cute]: Hi! ♡\n'
        s, d, _ = self.req('POST', '/api/preview', {'text': text, 'n': 2})
        self.assertEqual((s, d['character']), (200, '四国めたん'))
        s, raw, r = self.req('GET', d['url'], token=False)
        self.assertEqual((s, raw[:4]), (200, b'RIFF'))
        s, job, _ = self.req('POST', '/api/render', {'text': text, 'name': 'Test render'})
        self.assertEqual(s, 200)
        for _ in range(240):
            s, job, _ = self.req('GET', '/api/jobs/' + job['id'])
            if job['status'] != 'running':
                break
            time.sleep(0.5)
        self.assertEqual(job['status'], 'done', job.get('error'))
        self.assertEqual(sorted(c['credit'] for c in job['result']['credits']), ['VOICEVOX:ずんだもん', 'VOICEVOX:四国めたん'])
        files = self.req('GET', '/api/renders/Test%20render')[1]['files']
        for f in ('01_M.wav', '02_ME.wav', 'full.wav', 'timing.json', 'credits.txt', 'captions.vtt', 'script.txt'):
            self.assertIn(f, files)
        s, raw, r = self.req('GET', '/api/renders/Test%20render/zip', token=False, headers={})
        self.assertEqual(s, 403)                                    # media URLs carry the token in ?t=
        s, raw, r = self.req('GET', '/api/renders/Test%20render/zip?t=' + self.st.token, token=False)
        self.assertEqual((s, raw[:2]), (200, b'PK'))
        s, raw, r = self.req('GET', '/api/renders/Test%20render/full.wav?t=' + self.st.token, token=False,
                             headers={'Range': 'bytes=0-99'})
        self.assertEqual((s, len(raw)), (206, 100))
        s, d, _ = self.req('POST', '/api/render', {'text': text, 'name': 'Test render'})
        self.assertEqual(s, 200)


if __name__ == '__main__':
    unittest.main()
