"""
Characters, their styles, and which style a mood uses.

VOICEVOX has dozens of characters and every one names its styles its own
way: Zundamon's sweet voice is あまあま, Yurei-chan's is 甘々; Takehiro has
喜び where Kotaro has わーい. A mood written for one character must still
mean something for the next one, so moods ask for a TONE (a family of
styles) and every style the engine reports is sorted into a family here.

Resolution, for one character and one mood:
  1. each tone the mood lists, in order -> that character's style in it
  2. the mood's exact style name, if the character has it
  3. the family of that style name, if the character has one
  4. the character's base style (the cast's, else its normal one)

For Zundamon with the shipped moods every step lands where VoxTalk did,
which the regression test checks. A style the table does not know yet is
still usable by name; it just is not picked by tone.
"""

import re
import unicodedata

# ==================================================================
# Style families. Order inside a list = preference when a character has
# more than one style in the family. Every talk style of VOICEVOX 0.25.2
# is listed; a name missing here falls back to step 2-4 above.
# ==================================================================
FAMILIES = {
    'normal':   ['ノーマル', 'ふつう', '人間ver.', 'つぼみ'],
    'sweet':    ['あまあま', '甘々', 'ぶりっ子', 'ロリ'],
    'happy':    ['喜び', 'わーい', 'たのしい', 'うきうき', '楽々', '明るい', '元気'],
    'tsun':     ['ツンツン', 'ツンギレ', '不機嫌', '呆れ'],
    'angry':    ['怒り', 'おこ', '人間（怒り）ver.', 'ツンギレ', '不機嫌'],
    'sexy':     ['セクシー', 'セクシー／あん子', 'しっとり', 'クイーン'],
    'whisper':  ['ささやき', '囁き', '内緒話'],
    'hush':     ['ヒソヒソ'],
    'tired':    ['ヘロヘロ', 'へろへろ', 'けだるげ', '低血圧', 'よわよわ'],
    'teary':    ['なみだめ', '泣き', 'びえーん', '悲しみ', 'かなしみ', 'かなしい', '哀しみ'],
    'defeat':   ['絶望と敗北'],
    'scared':   ['びくびく', '恐怖', 'こわがり', 'おどおど'],
    'shy':      ['人見知り', 'おどおど'],
    'surprised': ['おどろき'],
    'calm':     ['おちつき', 'のんびり', 'しっとり'],
    'strong':   ['つよつよ', '熱血', '覚醒'],
    'serious':  ['シリアス'],
    'narrator': ['読み聞かせ', 'アナウンス'],
    'announce': ['アナウンス', '実況風'],
    # Another persona of the character rather than a mood: never picked by
    # a tone, only when a cast names it ("@cast X = 後鬼 / 鬼ver.").
    'variant':  ['ぬいぐるみver.', '鬼ver.', 'ツクモちゃん', 'ボーイ', '第二形態'],
}

FAMILY_OF = {}
for _fam, _names in FAMILIES.items():
    for _n in _names:
        FAMILY_OF.setdefault(_n, _fam)

# ==================================================================
# Romanised names, so a script can be written on any keyboard:
#   @cast ME = zundamon
# Only readings that are certain are listed; a character missing here is
# still found by its Japanese name or a style id.
# ==================================================================
ALIASES = {
    '四国めたん': ['shikoku metan', 'metan'],
    'ずんだもん': ['zundamon', 'zunda'],
    '春日部つむぎ': ['kasukabe tsumugi', 'tsumugi'],
    '雨晴はう': ['amehare hau', 'hau'],
    '波音リツ': ['namine ritsu', 'ritsu'],
    '玄野武宏': ['kurono takehiro', 'takehiro'],
    '白上虎太郎': ['shirakami kotarou', 'shirakami kotaro', 'kotarou', 'kotaro'],
    '青山龍星': ['aoyama ryusei', 'ryusei'],
    '冥鳴ひまり': ['meimei himari', 'himari'],
    '九州そら': ['kyushu sora', 'sora'],
    'もち子さん': ['mochiko', 'mochikosan', 'mochiko san'],
    '剣崎雌雄': ['kenzaki mesuo', 'mesuo'],
    'WhiteCUL': ['whitecul', 'white cul'],
    '後鬼': ['goki'],
    'No.7': ['no7', 'no.7', 'number seven'],
    'ちび式じい': ['chibishiki jii', 'chibi jii'],
    '櫻歌ミコ': ['ouka miko', 'miko'],
    '小夜/SAYO': ['sayo'],
    'ナースロボ＿タイプＴ': ['nurse robo type t', 'nurserobo', 'nurse robo'],
    '†聖騎士 紅桜†': ['benizakura'],
    '雀松朱司': ['wakamatsu akashi', 'akashi'],
    '麒ヶ島宗麟': ['kigashima sourin', 'sourin'],
    '春歌ナナ': ['haruka nana', 'nana'],
    '猫使アル': ['nekotsuka aru', 'aru'],
    '猫使ビィ': ['nekotsuka bi', 'nekotsuka bii'],
    '中国うさぎ': ['chugoku usagi', 'usagi'],
    '栗田まろん': ['kurita maron', 'maron'],
    'あいえるたん': ['airutan', 'iltan'],
    '満別花丸': ['manbetsu hanamaru', 'hanamaru'],
    '琴詠ニア': ['kotoyomi nia', 'nia'],
    'Voidoll': ['voidoll'],
    'ぞん子': ['zonko'],
    '中部つるぎ': ['chubu tsurugi', 'tsurugi'],
    '離途': ['rito'],
    'ユーレイちゃん': ['yurei chan', 'yureichan', 'yurei'],
    '東北ずん子': ['tohoku zunko', 'zunko'],
    '東北きりたん': ['tohoku kiritan', 'kiritan'],
    '東北イタコ': ['tohoku itako', 'itako'],
    'あんこもん': ['ankomon'],
    '夜語トバリ': ['yogatari tobari', 'tobari'],
    '暁記ミタマ': ['mitama'],
    '里石ユカ': ['satoishi yuka', 'yuka'],
}


def norm(s):
    """Name comparison: NFKC, lowercase, no spaces/dots/dashes/underscores."""
    s = unicodedata.normalize('NFKC', str(s)).lower()
    return re.sub(r'[\s._\-・/／＿†]+', '', s)


class Voices:
    """The characters one engine has, and the lookups over them."""

    def __init__(self, speakers):
        self.speakers = speakers or []
        self._by_norm = {}
        self._by_id = {}
        for sp in self.speakers:
            self._by_norm.setdefault(norm(sp['name']), sp)
            for alias in ALIASES.get(sp['name'], []):
                self._by_norm.setdefault(norm(alias), sp)
            for st in sp['styles']:
                self._by_id[int(st['id'])] = (sp, st)

    def find(self, name):
        """A character by name, romanised name, or style id. None if absent."""
        if name is None:
            return None
        if isinstance(name, int) or (isinstance(name, str) and name.strip().isdigit()):
            hit = self._by_id.get(int(name))
            return hit[0] if hit else None
        return self._by_norm.get(norm(name))

    def style_by_id(self, sid):
        return self._by_id.get(int(sid))

    def names(self):
        return [sp['name'] for sp in self.speakers]

    @staticmethod
    def style_named(sp, name):
        if not name:
            return None
        for st in sp['styles']:
            if st['name'] == name:
                return st
        n = norm(name)
        for st in sp['styles']:
            if norm(st['name']) == n:
                return st
        return None

    @staticmethod
    def in_family(sp, family):
        names = FAMILIES.get(family, [])
        for want in names:
            for st in sp['styles']:
                if st['name'] == want:
                    return st
        return None

    def base_style(self, sp, wanted=None):
        st = self.style_named(sp, wanted) if wanted else None
        if st is None and wanted and str(wanted).strip().isdigit():
            hit = self.style_by_id(int(wanted))
            if hit and hit[0] is sp:
                st = hit[1]
        return st or self.in_family(sp, 'normal') or sp['styles'][0]

    def resolve(self, sp, mood, base=None):
        """(style, how) for this character in this mood. `base` is the cast's
        chosen style name (or None for the character's normal one)."""
        tones = mood.get('tone') or []
        if isinstance(tones, str):
            tones = [tones]
        for t in tones:
            if t == 'normal':
                continue
            st = self.in_family(sp, t)
            if st is not None:
                return st, 'tone:' + t
        want = mood.get('style')
        if want and (base is None or FAMILY_OF.get(want) not in (None, 'normal')):
            st = self.style_named(sp, want)
            if st is not None:
                return st, 'style'
            fam = FAMILY_OF.get(want)
            if fam and fam != 'normal':
                st = self.in_family(sp, fam)
                if st is not None:
                    return st, 'family:' + fam
        return self.base_style(sp, base), 'base'


def family_of(style_name):
    return FAMILY_OF.get(style_name)


# ==================================================================
# Credits and conditions, read from the character's own terms.
# ==================================================================
CREDIT = re.compile(r'[「『"“]\s*(VOICEVOX[:：][^」』"”\n]+?)\s*[」』"”]')
# Terms that limit use beyond the credit line: companies, commercial use,
# prior permission. The studio flags these; it never interprets them.
# ("非商用" alone is not one: "商用・非商用で利用可能" grants both.)
CONDITIONS = re.compile(r'ただし|事前確認|事前に|法人|企業|個別に問い合わせ|禁止|非商用（|非商用\(|のみ利用可能')
URL = re.compile(r'https?://[^\s<>「」()（）"]+')


def credit_line(name, policy):
    """'VOICEVOX:ずんだもん' - the character's own wording when its terms
    spell one out (some add a voice actor: 'VOICEVOX:Voidoll(CV:丹下桜)')."""
    if policy:
        m = CREDIT.search(policy)
        if m:
            return m.group(1).replace('：', ':').strip()
    return 'VOICEVOX:' + name


def policy_summary(name, policy):
    policy = policy or ''
    urls = []
    for u in URL.findall(policy):
        u = u.rstrip('.,;:)」）')
        if u not in urls:
            urls.append(u)
    return {
        'credit': credit_line(name, policy),
        'conditions': bool(CONDITIONS.search(policy)),
        'urls': urls,
        'policy': policy.strip(),
    }
