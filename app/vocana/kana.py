"""
English -> katakana, and katakana -> the moras VOICEVOX accepts.

Why this exists
  VOICEVOX is a Japanese voice engine. Given English it guesses: "me" becomes
  the letters "M E", and the fix people use - misspelling words until they
  sound right ("pro grami ngo") - breaks the words into pieces the engine
  then stresses one by one. So every English word becomes katakana here,
  before the engine sees it: a dictionary for the words that matter
  (words.json, which the user edits), then e2k, an English-to-katakana
  model, for everything else.

The tables and rules in this file are the ones VoxTalk shipped with and the
renders were tuned against. Changing one changes how every existing script
sounds, so tests/test_regression.py pins them to the old output.
"""

import re


# ==================================================================
# Katakana: the moras VOICEVOX accepts in its kana notation
# (taken from the engine's own mora table)
# ==================================================================
VALID = set("""
ァ ア ィ イ ゥ ウ ェ エ ォ オ カ ガ キ ギ ク グ ケ ゲ コ ゴ サ ザ シ ジ ス ズ セ ゼ ソ ゾ タ ダ チ ヂ ッ ツ ヅ テ デ ト ド
ナ ニ ヌ ネ ノ ハ バ パ ヒ ビ ピ フ ブ プ ヘ ベ ペ ホ ボ ポ マ ミ ム メ モ ャ ヤ ュ ユ ョ ヨ ラ リ ル レ ロ ヮ ワ ヰ ヱ ヲ ン
ヴ ヶ イェ ウィ ウゥ ウェ ウォ キィ キェ キャ キュ キョ ギィ ギェ ギャ ギュ ギョ クァ クィ クゥ クェ クォ クヮ グァ グィ
グゥ グェ グォ グヮ シェ シャ シュ ショ ジェ ジャ ジュ ジョ スィ ズィ チェ チャ チュ チョ ヂェ ヂャ ヂュ ヂョ ツァ ツィ
ツェ ツォ ティ テェ テャ テュ テョ ディ デェ デャ デュ デョ トゥ ドゥ ニィ ニェ ニャ ニュ ニョ ヒィ ヒェ ヒャ ヒュ ヒョ
ビィ ビェ ビャ ビュ ビョ ピィ ピェ ピャ ピュ ピョ ファ フィ フェ フォ ミィ ミェ ミャ ミュ ミョ リィ リェ リャ リュ リョ
ヴァ ヴィ ヴェ ヴォ ヴャ ヴュ ヴョ
""".split())
SMALL = set('ァィゥェォャュョヮ')
ROWS = {
    'a': 'アカガサザタダナハバパマヤラワァャヮ',
    'i': 'イキギシジチヂニヒビピミリヰィ',
    'u': 'ウクグスズツヅヌフブプムユルゥュヴ',
    'e': 'エケゲセゼテデネヘベペメレヱェ',
    'o': 'オコゴソゾトドノホボポモヨロヲォョ',
}
VOWEL_OF = {k: v for v, ks in ROWS.items() for k in ks}
VOWEL_KANA = {'a': 'ア', 'i': 'イ', 'u': 'ウ', 'e': 'エ', 'o': 'オ'}
BIG = {'ァ': 'ア', 'ィ': 'イ', 'ゥ': 'ウ', 'ェ': 'エ', 'ォ': 'オ', 'ャ': 'ヤ', 'ュ': 'ユ', 'ョ': 'ヨ', 'ヮ': 'ワ'}

KANA_WORD = re.compile(r"[ァ-ヴーぁ-ゖ]+")


def hira_to_kata(s):
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)


def moras_of(kana):
    """Split katakana into VOICEVOX moras. 'ー' becomes the vowel it lengthens
    (the kana notation has no long-vowel mark), and anything the engine would
    refuse is repaired instead of failing the whole line."""
    kana = hira_to_kata(kana)
    out = []
    i = 0
    while i < len(kana):
        c = kana[i]
        pair = kana[i:i + 2]
        if len(pair) == 2 and pair[1] in SMALL and pair in VALID:
            out.append(pair)
            i += 2
            continue
        if c == 'ー':
            if out:
                last = out[-1]
                v = VOWEL_OF.get(last[-1])
                if v:
                    out.append(VOWEL_KANA[v])
                elif last == 'ン':
                    out.append('ン')
            i += 1
            continue
        if c in SMALL:
            # a small kana that cannot combine: say it as the full-size one
            # ('フュ' is not a VOICEVOX mora -> 'フ' + 'ユ')
            out.append(BIG[c])
            i += 1
            continue
        if c in VALID:
            out.append(c)
        i += 1
    return out


def voiceable(moras):
    """A word with no vowel ('ンー' -> 'ン','ン') comes out of VOICEVOX as a
    hum about 40 dB below speech: silence, and the line jumps straight to
    the next word. Say it the way a Japanese hum is said: 'ンー' -> 'ウーン'."""
    if moras and all(m in ('ン', 'ッ') for m in moras):
        n = moras.count('ン')
        return ['ウ'] * n + ['ン'] if n else []
    return moras


def vowel(m):
    return VOWEL_OF.get(m[-1])


def special(moras, k):
    """Moras that cannot carry a Japanese accent: ン, ッ, the second half of a
    long vowel, the イ/ウ that closes a diphthong."""
    m = moras[k]
    if m in ('ン', 'ッ'):
        return True
    if k > 0 and m in 'アイウエオ':
        pv = vowel(moras[k - 1])
        if pv == VOWEL_OF.get(m) or (m == 'イ' and pv in ('a', 'e', 'o')) or (m == 'ウ' and pv == 'o'):
            return True
    return False


def loanword_accent(moras):
    """Where Japanese puts the accent in a borrowed word: on the third mora
    from the end, moved one earlier when that mora is a special one."""
    n = len(moras)
    if n <= 2:
        return 1
    k = n - 3                          # 0-based
    while k > 0 and special(moras, k):
        k -= 1
    return k + 1


# ==================================================================
# Numbers and letters
# ==================================================================
NUM = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
       'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']

# Ordinal forms of the words above, for "1st", "22nd", "100th".
ORD = {'one': 'first', 'two': 'second', 'three': 'third', 'five': 'fifth', 'eight': 'eighth',
       'nine': 'ninth', 'twelve': 'twelfth'}


def number_words(n):
    n = int(n)
    if n < 20:
        return NUM[n]
    if n < 100:
        return TENS[n // 10] + ('' if n % 10 == 0 else ' ' + NUM[n % 10])
    if n < 1000:
        return NUM[n // 100] + ' hundred' + ('' if n % 100 == 0 else ' ' + number_words(n % 100))
    if n < 1000000:
        return number_words(n // 1000) + ' thousand' + ('' if n % 1000 == 0 else ' ' + number_words(n % 1000))
    return ' '.join(NUM[int(d)] for d in str(n))


def ordinal_words(n):
    """'21' -> 'twenty first'. Only the last word changes."""
    words = number_words(n).split()
    last = words[-1]
    if last in ORD:
        words[-1] = ORD[last]
    elif last.endswith('y'):
        words[-1] = last[:-1] + 'ieth'
    else:
        words[-1] = last + 'th'
    return ' '.join(words)


LETTERS = {'a': 'エー', 'b': 'ビー', 'c': 'シー', 'd': 'ディー', 'e': 'イー', 'f': 'エフ', 'g': 'ジー', 'h': 'エイチ',
           'i': 'アイ', 'j': 'ジェー', 'k': 'ケー', 'l': 'エル', 'm': 'エム', 'n': 'エヌ', 'o': 'オー', 'p': 'ピー',
           'q': 'キュー', 'r': 'アール', 's': 'エス', 't': 'ティー', 'u': 'ユー', 'v': 'ブイ', 'w': 'ダブリュー',
           'x': 'エックス', 'y': 'ワイ', 'z': 'ズィー'}

# Small words that lean on the next real word in speech ("i am" -> one phrase)
FUNCTION = set("""
a an the i me my mine you your yours we us our they them their he him his she her it its i'm i'll i've i'd
you're you'll you've you'd we're we'll it's that's there's here's let's is am are was were be been being do does
did don't doesn't didn't can can't could couldn't would wouldn't will won't should shouldn't have has had to of in
on at for from with by as or and but so if than then just not no too very this that these those what who how when
""".split())

# Where a word's katakana came from. The studio shows this next to every
# word, so the ones a model guessed can be checked and pinned in words.json.
SOURCE_DICT = 'dict'          # words.json
SOURCE_KANA = 'kana'          # already written in kana
SOURCE_NUMBER = 'number'      # 42 -> forty two
SOURCE_LETTERS = 'letters'    # a single letter, or PC / USA / AI
SOURCE_MODEL = 'e2k'          # the English-to-katakana model guessed it
SOURCE_SPELLED = 'spelled'    # no model available: read letter by letter


class Kana:
    """English text -> katakana, word by word.

    `words` is the user's dictionary (lowercase keys). The model is loaded
    once per process: it is a few megabytes of weights and every Kana built
    after the first one shares it."""

    _model = None
    _model_tried = False

    def __init__(self, words=None, use_model=True):
        self.words = dict(words or {})
        self.c2k = self.model() if use_model else None
        self._cache = {}

    @classmethod
    def model(cls):
        if not cls._model_tried:
            cls._model_tried = True
            try:
                from e2k import C2K
                cls._model = C2K()
            except Exception:
                cls._model = None
        return cls._model

    # The original interface: just the katakana.
    def word(self, w):
        return self.lookup(w)[0]

    def lookup(self, w):
        """(katakana, source) for one word as written in a script."""
        key = (w,)
        hit = self._cache.get(key)
        if hit is None:
            hit = self._lookup(w)
            if len(self._cache) > 20000:
                self._cache.clear()
            self._cache[key] = hit
        return hit

    def _lookup(self, w):
        lw = w.lower().replace('’', "'")
        if lw in self.words:
            return self.words[lw], SOURCE_DICT
        if KANA_WORD.fullmatch(w):                          # already kana
            return hira_to_kata(w), SOURCE_KANA
        if lw.isascii() and lw.isdigit():
            return ''.join(self.word(x) for x in number_words(lw).split()), SOURCE_NUMBER
        if len(lw) == 1 and lw in LETTERS:
            return LETTERS[lw], SOURCE_LETTERS
        if w.isupper() and 1 < len(w) <= 4 and w.isalpha():  # PC, USA, AI -> letters
            return ''.join(LETTERS[c] for c in lw if c in LETTERS), SOURCE_LETTERS
        bare = lw.replace("'", '')
        if bare in self.words:
            return self.words[bare], SOURCE_DICT
        m = re.fullmatch(r'(\d+)(st|nd|rd|th)', bare)
        if m:                                               # 1st, 22nd, 100th
            return ''.join(self.word(x) for x in ordinal_words(m.group(1)).split()), SOURCE_NUMBER
        if re.search(r'\d', bare) and re.search(r'[a-z]', bare):
            # "mp3", "v2", "2d": letters and digits read as their own runs.
            # The model only knows letters, and given digits it invents.
            parts = re.findall(r'[a-z]+|\d+', bare)
            out, src = '', SOURCE_NUMBER
            for p in parts:
                if p.isdigit():
                    out += self.word(p)
                elif len(p) <= 3:
                    out += ''.join(LETTERS[c] for c in p)
                    src = SOURCE_LETTERS if src == SOURCE_NUMBER else src
                else:
                    k, s = self.lookup(p)
                    out += k
                    src = s
            return out, src
        if self.c2k is not None and bare:
            try:
                k = self.c2k(bare)
                if k:
                    return self.plural(bare, k), SOURCE_MODEL
            except Exception:
                pass
        return ''.join(LETTERS.get(c, '') for c in bare), SOURCE_SPELLED

    def plural(self, bare, k):
        """e2k sometimes drops a plural s ('supporters' -> サポーター, the same
        as 'supporter', and the listener hears one supporter). Put it back."""
        if (len(bare) < 4 or not bare.endswith('s')
                or re.search(r'(ss|us|is|[sxz]es|[cs]hes|ges|ces)$', bare)
                or self.c2k(bare[:-1]) != k):
            return k
        if bare[-2] == 't' and k.endswith('ト'):
            return k[:-1] + 'ツ'
        return k + ('ス' if bare[-2] in 'pkf' else 'ズ')
