"""Builds expected_kana.json from the ORIGINAL VoxTalk (voxtalk.py), once.
Usage: python make_fixtures.py path/to/original/folder
The original is not shipped; the fixture it produced is."""
import json, os, random, re, sys
sys.path.insert(0, sys.argv[1])
import voxtalk  # noqa: E402

here = os.path.dirname(os.path.abspath(__file__))
vt = voxtalk.VoxTalk(os.path.join(sys.argv[1], 'moods.json'))
corpus = [l.rstrip('\n') for l in open(os.path.join(here, 'corpus.txt'), encoding='utf-8') if l.strip()]
vocab = sorted(set(re.findall(r"[A-Za-z][A-Za-z']*", ' '.join(corpus))) | set(k for k in vt.kana.words))
rng = random.Random(1234)
punct = ['.', '!', '?', '...', '~', ' ♡', '!!', '?!', ',', ' —']
for _ in range(400):
    n = rng.randint(1, 9)
    words = [rng.choice(vocab) for _ in range(n)]
    if rng.random() < 0.2:
        i = rng.randrange(n); words[i] = '*%s*' % words[i]
    if rng.random() < 0.1:
        i = rng.randrange(n); w = words[i].strip('*')
        if len(w) > 1 and w[0].isalpha(): words[i] = w[0] + '-' + w
    if rng.random() < 0.1:
        i = rng.randrange(n); w = words[i].strip('*')
        m = re.search(r'[aeiou]', w)
        if m: words[i] = w[:m.end()] + w[m.start()] * 2 + w[m.end():]
    s = ' '.join(words)
    if rng.random() < 0.3: s = s[0].upper() + s[1:]
    if rng.random() < 0.15: s += ' ' + str(rng.randint(0, 2500))
    corpus.append(s + rng.choice(punct))
out = []
for s in corpus:
    out.append({'text': s, 'plan': [['/'.join(p['seg']['moods']), p['kana'], p['seg']['pause']] for p in vt.plan(s)]})
json.dump(out, open(os.path.join(here, 'expected_kana.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(out), 'cases')
