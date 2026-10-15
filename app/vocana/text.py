"""
A line of a script -> sentences -> words -> VOICEVOX kana notation.

The rules for English are VoxTalk's, unchanged: tests/test_regression.py
holds the kana it produced for a few hundred sentences and fails on any
difference. What is new here only touches text the old code read wrongly:

  - "Mr.", "e.g.", "2.5", "amircollider.com" no longer end a sentence at
    the dot (they used to be cut in two with a pause in the middle);
  - "50%", "$5", "&" are read out instead of dropped;
  - full-width letters typed with a Japanese keyboard, and accented Latin
    letters ("café"), are read instead of skipped;
  - a sentence with kanji in it is Japanese, and goes to the engine's own
    Japanese reader rather than being stripped down to its kana.
"""

import re
import unicodedata

from .kana import FUNCTION, moras_of, loanword_accent, voiceable


# ==================================================================
# Splitting
# ==================================================================
# Sentence ends. The full-width forms are what a Japanese keyboard types.
SENT = re.compile(r'(\.{3,}|…|—|[.!?~♡❤。！？～〜]+)')
# A word: Latin letters (plain, accented or full-width), digits, kana.
LATIN = r"A-Za-z0-9À-ÖØ-öø-ɏＡ-Ｚａ-ｚ０-９"
WORD = re.compile(r"\*?[" + LATIN + r"][" + LATIN + r"'’\-]*\*?|[ァ-ヴーぁ-ゖｦ-ﾟ]+|,|;|:|、|，")
PAUSE = re.compile(r'\(\s*pause\s+(\d+(?:\.\d*)?|\.\d+)\s*s?\s*\)', re.I)
KANJI = re.compile('[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u3006]')
# Scripts VOICEVOX cannot say at all: Hebrew, Arabic and Persian, Cyrillic,
# Thai, Hangul, Devanagari. A sentence made only of these is skipped, and
# the studio says so instead of rendering silence.
_UNREADABLE = ('\u0590-\u05ff\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufefe'
               '\u0400-\u04ff\u0e00-\u0e7f\uac00-\ud7af\u0900-\u097f')
UNREADABLE = re.compile('[' + _UNREADABLE + ']')
UNREADABLE_RUN = re.compile('[' + _UNREADABLE + '\u200c]+(?:\\s+[' + _UNREADABLE + '\u200c]+)*')
READABLE = re.compile('[A-Za-z0-9\u30a1-\u30f4\u3041-\u3096\u3400-\u4dbf\u4e00-\u9fff'
                      '\uff21-\uff3a\uff41-\uff5a\uff10-\uff19\u00c0-\u024f\uff66-\uff9f]')

# Abbreviations whose dot is not the end of a sentence. Only ones that are
# unambiguous when followed by a space: "St." could be Saint or Street, so
# it stays as it was.
ABBREV = [
    (r'\bMr\.(?=\s)', 'Mister'), (r'\bMrs\.(?=\s)', 'Missus'), (r'\bMs\.(?=\s)', 'Miss'),
    (r'\bDr\.(?=\s)', 'Doctor'), (r'\bProf\.(?=\s)', 'Professor'),
    (r'\bvs\.(?=\s)', 'versus'), (r'\betc\.', 'et cetera'),
    (r'\be\.g\.', 'for example'), (r'\bi\.e\.', 'that is'),
]
TLD = r'(com|net|org|io|jp|ir|dev|app|co|me|gg|tv|ai|xyz|info|games)'


def speakable(text):
    """The rewrites that turn written forms into the words they are said as.
    Run on a whole line before it is split into sentences."""
    for pat, rep in ABBREV:
        text = re.sub(pat, rep, text, flags=re.I)
    # amircollider.com -> amircollider dot com
    text = re.sub(r'\b([A-Za-z0-9\-]+)\.' + TLD + r'\b', r'\1 dot \2', text, flags=re.I)
    # $5 -> 5 dollars, $5.99 -> 5 dollars 99 cents
    text = re.sub(r'\$(\d+)\.(\d{2})\b', lambda m: '%s %s %s cents' % (
        m.group(1), 'dollar' if m.group(1) == '1' else 'dollars', m.group(2)), text)
    text = re.sub(r'\$(\d+)\b', lambda m: '%s %s' % (m.group(1), 'dollar' if m.group(1) == '1' else 'dollars'), text)
    # 2.5 -> 2 point 5 (the dot is not a sentence end)
    text = re.sub(r'(\d)\.(?=\d)', r'\1 point ', text)
    text = re.sub(r'(\d)\s*%', r'\1 percent', text)
    text = re.sub(r'\s&\s', ' and ', text)
    return text


def fold(tok):
    """A word as the dictionary and the model expect it: plain ASCII letters
    where the writer used full-width or accented ones. Kana keep their
    voicing marks - only a mark sitting on a Latin letter is dropped."""
    if tok.isascii():
        return tok
    out, base = [], ''
    for c in unicodedata.normalize('NFKD', unicodedata.normalize('NFKC', tok)):
        if unicodedata.combining(c):
            if base.isascii() and base.isalpha():
                continue
        else:
            base = c
        out.append(c)
    return unicodedata.normalize('NFC', ''.join(out))


def split_line(text, moods, sentence_gap=None, notes=None):
    """Sentences with their moods and delivery markers. A [mood] inside the
    text switches the mood from that point on. The silence after a sentence
    follows its punctuation; sentence_gap sets it for every sentence, and a
    (pause 0.5) inside the text sets it at that point.

    Text VOICEVOX cannot say (Persian, Arabic, Korean...) is left out, and
    when `notes` is a list it is told about it, so the studio can say why a
    sentence made no sound."""
    text = speakable(text)
    text = PAUSE.sub(lambda m: ' \0%s\0 ' % m.group(1), text)
    text = re.sub(r'\([^)]*\)', ' ', text)
    text = re.sub(r'\b([AaPp])\.\s?[Mm]\.', lambda m: (' エーエム.' if m.group(1) in 'Aa' else ' ピーエム.'), text)  # 3 a.m.
    segs, current, asked = [], list(moods), {}
    for k, chunk in enumerate(re.split(r'\[([^\]]*)\]', text)):
        if k % 2:
            current = [m.strip().lower() for m in re.split(r'[\s,]+', chunk) if m.strip()]
            continue
        for j, piece in enumerate(chunk.split('\0')):
            if j % 2:                                     # the seconds of a (pause N)
                if segs:
                    asked[len(segs) - 1] = float(piece)
                continue
            parts = SENT.split(piece)
            for i in range(0, len(parts), 2):
                body, sep = parts[i], (parts[i + 1] if i + 1 < len(parts) else '')
                if not READABLE.search(body):
                    if UNREADABLE.search(body) and notes is not None:
                        notes.append({'unreadable': body.strip()})
                    if segs and sep:
                        segs[-1]['sep'] += sep
                    continue
                if UNREADABLE.search(body) and notes is not None:
                    notes.append({'unreadable': ' '.join(UNREADABLE_RUN.findall(body))})
                segs.append({'body': body, 'sep': sep, 'moods': list(current)})
    for i, s in enumerate(segs):
        b, sep = s['body'], s['sep']
        s['tilde'] = any(c in b + sep for c in '~～〜')
        s['heart'] = '♡' in b + sep or '❤' in b + sep
        s['question'] = '?' in sep or '？' in sep
        s['exclaim'] = '!' in sep or '！' in sep
        s['trail'] = sep.startswith('...') or sep.startswith('…')
        s['cut'] = sep.startswith('—')
        s['pause'] = 0.5 if s['trail'] else 0.08 if s['cut'] else 0.32 if s['question'] else 0.25
        if sentence_gap is not None and not s['cut']:
            s['pause'] = max(s['pause'], sentence_gap) if s['trail'] else sentence_gap
        if i in asked:
            s['pause'] = asked[i]
        s['japanese'] = bool(KANJI.search(b))
    if segs and len(segs) - 1 not in asked:
        segs[-1]['pause'] = 0.0
    return segs


def sentence_words(body, kana):
    """[(display_word, moras, flags)] and ',' for pauses inside a sentence."""
    out = []
    for tok in WORD.findall(body):
        if tok in (',', ';', ':', '、', '，'):
            out.append(',')
            continue
        emph = tok.startswith('*') and tok.endswith('*') and len(tok) > 2
        w = tok.strip('*')
        wf = fold(w)
        stretch = bool(re.search(r'([A-Za-z])\1\1', wf))
        w2 = re.sub(r'([A-Za-z])\1{2,}', r'\1', wf)       # Pleeease -> Please
        stutter = None
        m = re.fullmatch(r"([A-Za-z]{1,3})-(\1[A-Za-z']*)", w2, flags=re.I)
        if m:
            w2 = m.group(2)
            stutter = True
        sources = []
        if '-' in w2:                                       # well-known -> well + known
            parts = [kana.lookup(x) for x in w2.split('-') if x]
            moras = moras_of(''.join(k for k, _s in parts))
            sources = [s for _k, s in parts]
        else:
            k, s = kana.lookup(w2)
            moras = moras_of(k)
            sources = [s]
        moras = voiceable(moras)
        if not moras:
            continue
        if stutter:
            out.append({'word': w, 'moras': [moras[0]], 'stutter': True,
                        'emph': False, 'stretch': False, 'func': True, 'source': sources[0]})
            out.append(',')
        out.append({'word': w, 'moras': moras, 'emph': emph, 'stretch': stretch,
                    'func': w2.lower().replace('’', "'") in FUNCTION,
                    'source': sources[0] if len(set(sources)) == 1 else 'mixed', 'lookup': w2})
    return out


def build_kana(words, question):
    """Group words into accent phrases and write VOICEVOX kana notation.
    Returns (kana_text, [mora index ranges per word], total moras)."""
    phrases, spans = [], []
    pending = []                         # function words waiting for a content word
    idx = 0

    def flush(group, accent_word):
        nonlocal idx
        moras = []
        acc = 1
        for w in group:
            if w is accent_word:
                acc = len(moras) + loanword_accent(w['moras'])
            spans.append((w, idx + len(moras), idx + len(moras) + len(w['moras'])))
            moras += w['moras']
        if accent_word is None:
            acc = 1
        idx += len(moras)
        phrases.append({'moras': moras, 'accent': acc, 'pause': False})

    for w in words:
        if w == ',':
            if pending:
                flush(pending, None)
                pending = []
            if phrases:
                phrases[-1]['pause'] = True
            continue
        if w.get('func') and not w.get('emph'):
            pending.append(w)
            if sum(len(p['moras']) for p in pending) > 8:
                flush(pending, None)
                pending = []
            continue
        flush(pending + [w], w)
        pending = []
    if pending:
        if phrases and not phrases[-1]['pause'] and len(phrases[-1]['moras']) + sum(len(p['moras']) for p in pending) <= 12:
            last = phrases[-1]
            for p in pending:
                spans.append((p, idx, idx + len(p['moras'])))
                idx += len(p['moras'])
                last['moras'] += p['moras']
        else:
            flush(pending, None)
    text = ''
    for i, ph in enumerate(phrases):
        ms = ph['moras']
        text += ''.join(ms[:ph['accent']]) + "'" + ''.join(ms[ph['accent']:])
        if i == len(phrases) - 1:
            if question:
                text += '？'
        else:
            text += '、' if ph['pause'] else '/'
    return text, spans, idx


def japanese_text(body, kana, question):
    """A Japanese sentence for the engine's own reader: kanji and kana as
    written, any English words in it turned into katakana first."""
    def repl(m):
        tok = m.group(0)
        w = fold(tok.strip('*'))
        if w.isdigit():
            return w                     # the engine reads numbers in Japanese
        return kana.word(w)
    t = re.sub(r"\*?[A-Za-zＡ-Ｚａ-ｚÀ-ɏ][A-Za-zＡ-Ｚａ-ｚÀ-ɏ'’\-]*\*?", repl, body)
    t = unicodedata.normalize('NFKC', t).strip()
    t = re.sub(r'\s+', ' ', t)
    if question and not t.endswith('？'):
        t += '？'
    return t


def caption_text(text):
    return re.sub(r'\s+', ' ', text.replace('*', '')).strip()
