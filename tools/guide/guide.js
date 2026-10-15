(function () {
  'use strict';
  var SAMPLE = __SAMPLE_TIMING__;
  var MOODS = __MOODS__;
  var W = {
    en: { copy: 'Copy', copied: 'Copied', lines: 'Lines', filter: 'Filter moods…', mood: 'Mood', tone: 'Tone', zstyle: 'Zundamon’s style', feel: 'How it sounds',
      noaudio: 'The sample sound is in renders/Sample/full.wav next to this guide. If it does not play here, open that file directly.',
      search: 'Search problems…', none: 'Nothing matches.',
      exp: { tag: 'speaker tag: who says the line', mood: 'mood for the whole line', moodBad: 'not one of the shipped moods — “normal” would be used',
        inmood: 'mood changes from here on', emph: 'emphasis: higher and longer', stretch: 'stretched: the long vowel is held', stutter: 'stutter',
        pause: 'a pause of exactly this many seconds', aside: 'in round brackets: not spoken', excl: 'ends higher (excited)', q: 'a question: rises at the end',
        tilde: 'playful: stretched and rising', heart: 'sweet ending', dots: 'trails off, then a pause', dash: 'cut off', kana: 'katakana: said as written',
        castline: '@cast: which character reads this tag', setting: 'silence setting', pauseline: 'silence on its own line', comment: 'a comment: not spoken', none: 'Write a line to see what each part does.' } },
    fa: { copy: 'کپی', copied: 'کپی شد', lines: 'خط‌ها', filter: 'جست‌وجوی حال‌وهوا…', mood: 'حال‌وهوا', tone: 'لحن', zstyle: 'سبک زوندامون', feel: 'چه حسی دارد',
      noaudio: 'صدای نمونه در renders/Sample/full.wav کنار همین راهنماست. اگر این‌جا پخش نشد، خود فایل را باز کنید.',
      search: 'جست‌وجوی مشکل…', none: 'چیزی پیدا نشد.',
      exp: { tag: 'برچسب گوینده: چه کسی این خط را می‌گوید', mood: 'حال‌وهوای کل خط', moodBad: 'جزو حال‌وهواهای آماده نیست — به جایش «normal» به کار می‌رود',
        inmood: 'حال‌وهوا از این‌جا به بعد عوض می‌شود', emph: 'تأکید: زیرتر و کشیده‌تر', stretch: 'کشیده: واکه‌ی بلند نگه داشته می‌شود', stutter: 'لکنت',
        pause: 'مکثی دقیقاً به همین ثانیه', aside: 'داخل پرانتز: گفته نمی‌شود', excl: 'آخرش بالا می‌رود (پرهیجان)', q: 'سؤالی: آخرش بالا می‌رود',
        tilde: 'بازیگوش: کشیده و رو به بالا', heart: 'پایان مهربان', dots: 'آرام ول می‌شود و بعد مکث', dash: 'حرف قطع می‌شود', kana: 'کاتاکانا: همان‌طور که نوشته شده خوانده می‌شود',
        castline: '‏@cast: کدام شخصیت این برچسب را می‌خواند', setting: 'تنظیم سکوت', pauseline: 'سکوت در یک خط جدا', comment: 'توضیح: گفته نمی‌شود', none: 'یک خط بنویسید تا ببینید هر بخشش چه کار می‌کند.' } },
    ja: { copy: 'コピー', copied: 'コピーしました', lines: 'セリフ', filter: 'ムードを検索…', mood: 'ムード', tone: 'トーン', zstyle: 'ずんだもんのスタイル', feel: '聞こえ方',
      noaudio: 'サンプル音声はこのガイドの隣の renders/Sample/full.wav にあります。ここで再生できない場合はそのファイルを直接開いてください。',
      search: 'トラブルを検索…', none: '該当なし。',
      exp: { tag: '話者タグ: 誰のセリフか', mood: 'この行全体のムード', moodBad: '標準のムードにないため「normal」になります',
        inmood: 'ここからムードが変わる', emph: '強調: 高く、長く', stretch: '伸ばし: 長母音を保つ', stutter: 'どもり',
        pause: 'ちょうどこの秒数の間', aside: '丸かっこ: 読まない', excl: '語尾が上がる (元気)', q: '疑問: 語尾が上がる',
        tilde: '遊び心: 伸ばして上げる', heart: '甘い語尾', dots: '言いよどんで、間をあける', dash: '途切れる', kana: 'カタカナ: 書いたとおりに読む',
        castline: '@cast: このタグをどのキャラクターが読むか', setting: '無音の設定', pauseline: '単独の行で無音', comment: 'コメント: 読まない', none: '1 行書くと、各部分の意味が表示されます。' } }
  };
  var FEEL = {
    normal: ['Clear and friendly; the base every other mood starts from.', 'واضح و دوستانه؛ پایه‌ی همه‌ی حال‌وهواهای دیگر.', 'はっきり、親しみやすく。ほかのムードの土台。'],
    excited: ['High energy, big jumps, a strong rise on “!”.', 'پرانرژی، با پرش‌های بزرگ و اوج زیاد روی «!».', '元気いっぱい。大きく弾み、「!」で大きく上がる。'],
    happy: ['Bright and warm.', 'روشن و گرم.', '明るく、あたたかく。'],
    cheeky: ['A little mischievous; ends lifted.', 'کمی شیطون؛ آخر جمله بالا.', 'ちょっといたずらっぽく、語尾を上げて。'],
    flustered: ['Fast, high and jumpy — caught off guard.', 'تند، زیر و پرپرش — غافلگیر.', '速く、高く、ドタバタ。不意をつかれた感じ。'],
    shout: ['Loud and high.', 'بلند و زیر.', '大きく、高く。'],
    deadpan: ['Flat on purpose: almost no melody.', 'عمداً یکنواخت: تقریباً بی‌ملودی.', 'わざと平坦。抑揚ほぼなし。'],
    shy: ['Soft, lower, quieter.', 'نرم، بم‌تر، آرام‌تر.', 'やわらかく、低めに、小さめに。'],
    cute: ['Sweet and bouncy.', 'شیرین و پرجست‌وخیز.', '甘く、弾むように。'],
    pleading: ['Sweet, rising ends, the last syllable held.', 'شیرین، آخر رو به بالا، هجای آخر کشیده.', '甘く、語尾を上げて伸ばす。'],
    innocent: ['Sweet and wide-eyed.', 'شیرین و معصوم.', '甘く、無邪気に。'],
    teasing: ['Tsun-tsun, playful rise.', 'تسون‌تسون، با اوج بازیگوشانه.', 'ツンツン、からかうように上げて。'],
    pouting: ['Tsun-tsun, ends drawn out.', 'تسون‌تسون، آخر جمله کش‌دار.', 'ツンツン、語尾を引きずって。'],
    smug: ['Tsun-tsun, slow and sure of itself.', 'تسون‌تسون، آرام و از خودراضی.', 'ツンツン、ゆっくり自信たっぷりに。'],
    angry: ['Hard and loud; falling ends.', 'تند و بلند؛ آخر جمله رو به پایین.', '強く大きく、語尾を下げて。'],
    dark: ['Low, slow and flat — menacing.', 'بم، آرام و یکنواخت — تهدیدآمیز.', '低く、ゆっくり、平坦に。不穏な感じ。'],
    serious: ['Lower and steady.', 'بم‌تر و محکم.', '低めで落ち着いて。'],
    calm: ['Even and relaxed.', 'یکنواخت و آسوده.', '穏やかに、リラックスして。'],
    narrator: ['Storytelling: steady, longer comma pauses.', 'راوی: پیوسته، با مکث بلندتر سر ویرگول.', '読み聞かせ。安定して、読点の間を長めに。'],
    surprised: ['Very high, big rise on “!”.', 'خیلی زیر، اوج زیاد روی «!».', 'とても高く、「!」で大きく上がる。'],
    scared: ['Trembling and high.', 'لرزان و زیر.', '震えるように、高めに。'],
    sleepy: ['Slow, low, fading ends.', 'آرام، بم، آخر جمله محو.', 'ゆっくり、低く、語尾が消えていく。'],
    sad: ['Teary; ends fall.', 'بغض‌کرده؛ آخر جمله پایین می‌افتد.', '涙ぐんで、語尾を下げて。'],
    defeated: ['Teary and slow, ends drop a lot.', 'بغض‌آلود و آرام، آخر جمله خیلی پایین.', '涙ぐんでゆっくり、語尾を大きく下げて。'],
    whisper: ['A whisper (louder, so it is heard).', 'نجوا (بلندتر تا شنیده شود).', 'ささやき (聞こえるよう音量を上げて)。'],
    asmr: ['A close hush, ASMR-style.', 'پچ‌پچ نزدیک، به سبک ASMR.', '近くでヒソヒソ。ASMR 風。']
  };
  var LANGS = ['fa', 'en', 'ja'];
  var lang = 'en';

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem('vocana-guide.' + k); localStorage.setItem('vocana-guide.' + k, v); } catch (e) { return null; } }

  // ---------------- language & theme ----------------
  function pickLang() {
    var saved = store('lang');
    var hash = (location.hash.match(/^#(fa|en|ja)$/) || [])[1];
    if (hash) return hash;
    if (saved && LANGS.indexOf(saved) >= 0) return saved;
    var nav = ((navigator.languages && navigator.languages[0]) || navigator.language || 'en').toLowerCase();
    return nav.indexOf('fa') === 0 ? 'fa' : nav.indexOf('ja') === 0 ? 'ja' : 'en';
  }
  function setLang(l) {
    lang = l;
    store('lang', l);
    document.documentElement.lang = l;
    document.documentElement.dir = l === 'fa' ? 'rtl' : 'ltr';
    $$('.L').forEach(function (el) { el.classList.toggle('on', el.getAttribute('lang') === l); });
    $$('.langs button').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.l === l ? 'true' : 'false'); });
    document.title = $('.L.on h1') ? 'Vocana — ' + $('.L.on .hero .tag').textContent : 'Vocana';
    buildToc();
    widgets();
  }
  function setTheme(t) {
    if (t === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.dataset.theme = t;
    store('theme', t);
    var b = $('.themebtn');
    if (b) {
      var d = { dark: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z', light: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
        auto: 'M12 22a10 10 0 1 0 0-20v20zM12 2a10 10 0 0 1 0 20' }[t] || '';
      b.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="' + d + '"/></svg>';
    }
  }

  // ---------------- table of contents ----------------
  var spy;
  function buildToc() {
    var toc = $('.toc');
    toc.innerHTML = '';
    $$('.L.on section[id]').forEach(function (s) {
      var h = $('h2', s);
      if (!h) return;
      var a = document.createElement('a');
      a.href = '#' + s.id;
      var clone = h.cloneNode(true);
      $$('.n', clone).forEach(function (x) { x.remove(); });
      a.textContent = clone.textContent.trim();
      a.dataset.id = s.id;
      toc.appendChild(a);
    });
    if (spy) spy.disconnect();
    if (window.IntersectionObserver) {
      spy = new IntersectionObserver(function (ents) {
        ents.forEach(function (e) {
          if (e.isIntersecting) $$('.toc a').forEach(function (a) { a.classList.toggle('on', a.dataset.id === e.target.id); });
        });
      }, { rootMargin: '-20% 0px -70% 0px' });
      $$('.L.on section[id]').forEach(function (s) { spy.observe(s); });
    }
  }

  // ---------------- widgets ----------------
  function copyText(t, btn) {
    function done() { var o = btn.textContent; btn.textContent = W[lang].copied; setTimeout(function () { btn.textContent = W[lang].copy; }, 1300); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(done, function () { legacy(t); done(); });
    else { legacy(t); done(); }
  }
  function legacy(t) {
    var ta = document.createElement('textarea'); ta.value = t; ta.style.position = 'fixed'; ta.style.top = '-1000px';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) { /* nothing else to try */ } ta.remove();
  }
  function copyButtons() {
    $$('.L.on pre').forEach(function (pre) {
      if ($('.copy', pre)) { $('.copy', pre).textContent = W[lang].copy; return; }
      var text = pre.textContent;
      var b = document.createElement('button');
      b.className = 'copy'; b.type = 'button'; b.textContent = W[lang].copy;
      b.addEventListener('click', function () { copyText(text, b); });
      pre.appendChild(b);
    });
  }
  var audio;
  function player() {
    $$('.L.on .w-player').forEach(function (box) {
      if (box.dataset.done) return;
      box.dataset.done = '1';
      box.className += ' player';
      audio = audio || new Audio();
      var a = document.createElement('audio');
      a.controls = true; a.preload = 'metadata'; a.src = 'renders/Sample/full.wav';
      var kara = document.createElement('div'); kara.className = 'kara'; kara.innerHTML = '<span>♪</span>';
      var lines = document.createElement('div'); lines.className = 'plines';
      SAMPLE.lines.forEach(function (ln) {
        var b = document.createElement('button');
        b.type = 'button';
        b.innerHTML = '<span class="t">' + ln.start.toFixed(1) + 's</span><span>' + esc(ln.text) + '</span>';
        b.addEventListener('click', function () { a.currentTime = ln.start + 0.01; a.play(); });
        lines.appendChild(b);
      });
      var err = document.createElement('p'); err.className = 'note'; err.style.display = 'none'; err.textContent = W[lang].noaudio;
      a.addEventListener('error', function () { err.style.display = 'block'; });
      box.appendChild(a); box.appendChild(kara); box.appendChild(lines); box.appendChild(err);
      var lastS = null, raf = 0;
      function tick() {
        var tm = a.currentTime, found = null, who = '', li = -1;
        SAMPLE.lines.forEach(function (ln, i) { ln.sentences.forEach(function (s) { if (tm >= s.start - 0.02 && tm <= s.end + 0.15) { found = s; who = ln.who + ' · ' + (ln.character || ''); li = i; } }); });
        $$('button', lines).forEach(function (b, i) { b.classList.toggle('on', i === li); });
        if (found !== lastS) {
          lastS = found;
          kara.innerHTML = found ? '<small>' + esc(who) + '</small><span>' + found.words.map(function (w, i) { return '<span class="w" data-i="' + i + '">' + esc(w.word) + '</span>'; }).join(' ') + '</span>' : '<span>♪</span>';
        }
        if (found) found.words.forEach(function (w, i) { var el = $('.w[data-i="' + i + '"]', kara); if (el) el.classList.toggle('on', tm >= w.start && tm < w.end + 0.04); });
        if (!a.paused) raf = requestAnimationFrame(tick);
      }
      a.addEventListener('play', function () { cancelAnimationFrame(raf); tick(); });
      a.addEventListener('seeked', tick);
    });
  }
  function hlLine(line, notes) {
    var tr = line.trim();
    if (!tr) return '';
    if (tr[0] === '#') { notes.push(['#', W[lang].exp.comment]); return '<span class="t-com">' + esc(line) + '</span>'; }
    var m = /^(\s*)(sentence_gap|gap)(\s*[=:]\s*)([\d.]+)\s*$/i.exec(line);
    if (m) { notes.push([m[2] + ' =', W[lang].exp.setting]); return '<span class="t-dir">' + esc(m[2]) + '</span>' + esc(m[3]) + '<span class="t-pause">' + esc(m[4]) + '</span>'; }
    m = /^(\s*)(@?cast)(\s+)(\S+?)(\s*[=:：]\s*)(.*)$/i.exec(line);
    if (m) { notes.push(['@cast', W[lang].exp.castline]); return '<span class="t-dir">' + esc(m[2]) + '</span>' + esc(m[3]) + '<span class="t-tag">' + esc(m[4]) + '</span>' + esc(m[5]) + '<span class="t-kana">' + esc(m[6]) + '</span>'; }
    if (/^\s*\(\s*pause\s+[\d.]+\s*s?\s*\)\s*$/i.test(line)) { notes.push(['(pause N)', W[lang].exp.pauseline]); return '<span class="t-pause">' + esc(line) + '</span>'; }
    m = /^(\s*)([A-Za-z_぀-ヿ一-鿿][\w\-.぀-ヿ一-鿿]*)?(\s*)(\[[^\]]*\])?(\s*)([:：])(\s*)(.*)$/.exec(line);
    var out = '', text = line;
    if (m && (m[2] || m[4])) {
      if (m[2]) { out += '<span class="t-tag">' + esc(m[2]) + '</span>'; notes.push([m[2], W[lang].exp.tag]); }
      if (m[4]) {
        var bad = m[4].slice(1, -1).split(/[\s,]+/).filter(function (x) { return x && !MOODS[x.toLowerCase()]; });
        out += esc(m[3]) + '<span class="' + (bad.length ? 't-bad' : 't-mood') + '">' + esc(m[4]) + '</span>';
        notes.push([m[4], bad.length ? W[lang].exp.moodBad : W[lang].exp.mood]);
      }
      out += esc(m[5]) + esc(m[6]) + esc(m[7]);
      text = m[8];
    }
    var re = /(\[[^\]]*\])|(\(\s*pause\s+[\d.]+\s*s?\s*\))|(\([^)]*\))|(\*[^*\s][^*]*\*)|(\b([A-Za-z])\6?-\6[A-Za-z']*)|(\b[A-Za-z]*([A-Za-z])\8\8[A-Za-z]*\b)|(\.{3,}|…)|(—)|(~|～)|(♡|❤)|(\?|？)|(!|！)|([ぁ-ヿ]+)/g;
    var last = 0, k;
    var seen = {};
    function note(key, label) { if (!seen[key]) { seen[key] = 1; notes.push([label, W[lang].exp[key]]); } }
    while ((k = re.exec(text))) {
      out += esc(text.slice(last, k.index));
      var tok = esc(k[0]);
      if (k[1]) { out += '<span class="t-mood">' + tok + '</span>'; note('inmood', k[1]); }
      else if (k[2]) { out += '<span class="t-pause">' + tok + '</span>'; note('pause', k[2]); }
      else if (k[3]) { out += '<span class="t-com">' + tok + '</span>'; note('aside', k[3]); }
      else if (k[4]) { out += '<span class="t-emph">' + tok + '</span>'; note('emph', k[4]); }
      else if (k[5]) { out += '<span class="t-str">' + tok + '</span>'; note('stutter', k[5]); }
      else if (k[7]) { out += '<span class="t-str">' + tok + '</span>'; note('stretch', k[7]); }
      else if (k[9]) { out += '<span class="t-punct">' + tok + '</span>'; note('dots', k[9]); }
      else if (k[10]) { out += '<span class="t-punct">' + tok + '</span>'; note('dash', '—'); }
      else if (k[11]) { out += '<span class="t-punct">' + tok + '</span>'; note('tilde', '~'); }
      else if (k[12]) { out += '<span class="t-punct">' + tok + '</span>'; note('heart', '♡'); }
      else if (k[13]) { out += '<span class="t-punct">' + tok + '</span>'; note('q', '?'); }
      else if (k[14]) { out += '<span class="t-punct">' + tok + '</span>'; note('excl', '!'); }
      else if (k[15]) { out += '<span class="t-kana">' + tok + '</span>'; note('kana', k[15]); }
      last = k.index + k[0].length;
    }
    return out + esc(text.slice(last));
  }
  function playground() {
    $$('.L.on .w-play').forEach(function (box) {
      if (box.dataset.done) return;
      box.dataset.done = '1';
      var ta = document.createElement('textarea');
      ta.className = 'play'; ta.spellcheck = false;
      ta.value = box.dataset.line || "ME [cute]: W-Wait... you *really* made this? Pleeease show me~ ♡ (pause 0.5) [excited] It's amazing!";
      var out = document.createElement('div'); out.className = 'hl';
      var ul = document.createElement('ul'); ul.className = 'explain';
      function run() {
        var notes = [];
        out.innerHTML = ta.value.split('\n').map(function (l) { return hlLine(l, notes); }).join('\n') || '&nbsp;';
        ul.innerHTML = notes.length ? notes.map(function (n) { return '<li><code>' + esc(n[0]) + '</code><span>' + esc(n[1]) + '</span></li>'; }).join('') : '<li>' + esc(W[lang].exp.none) + '</li>';
      }
      ta.addEventListener('input', run);
      box.appendChild(ta); box.appendChild(out); box.appendChild(ul);
      run();
    });
  }
  function moodsTable() {
    $$('.L.on .w-moods').forEach(function (box) {
      if (box.dataset.done) return;
      box.dataset.done = '1';
      var idx = { fa: 1, en: 0, ja: 2 }[lang];
      var q = document.createElement('input'); q.type = 'search'; q.placeholder = W[lang].filter;
      var wrap = document.createElement('div'); wrap.className = 'tablewrap';
      var tb = document.createElement('table');
      tb.innerHTML = '<thead><tr><th>' + esc(W[lang].mood) + '</th><th>' + esc(W[lang].tone) + '</th><th>' + esc(W[lang].zstyle) + '</th><th>' + esc(W[lang].feel) + '</th></tr></thead><tbody></tbody>';
      wrap.appendChild(tb);
      function paint() {
        var term = q.value.trim().toLowerCase();
        $('tbody', tb).innerHTML = Object.keys(MOODS).filter(function (m) {
          var f = (FEEL[m] || [''])[idx] || '';
          return !term || m.indexOf(term) >= 0 || f.toLowerCase().indexOf(term) >= 0;
        }).map(function (m) {
          var md = MOODS[m], tone = md.tone ? (Array.isArray(md.tone) ? md.tone.join(' → ') : md.tone) : '—';
          return '<tr><td><code>[' + esc(m) + ']</code></td><td><code>' + esc(tone) + '</code></td><td>' + esc(md.style || 'ノーマル') + '</td><td>' + esc((FEEL[m] || [''])[idx] || '') + '</td></tr>';
        }).join('');
      }
      q.addEventListener('input', paint);
      box.appendChild(q); box.appendChild(wrap);
      paint();
    });
  }
  function troubleSearch() {
    $$('.L.on .w-trouble').forEach(function (box) {
      if (box.dataset.done) return;
      box.dataset.done = '1';
      var q = document.createElement('input'); q.type = 'search'; q.placeholder = W[lang].search;
      var none = document.createElement('p'); none.textContent = W[lang].none; none.style.display = 'none';
      box.insertBefore(q, box.firstChild);
      box.appendChild(none);
      q.addEventListener('input', function () {
        var term = q.value.trim().toLowerCase(), any = false;
        $$('details', box).forEach(function (d) { var hit = !term || d.textContent.toLowerCase().indexOf(term) >= 0; d.style.display = hit ? '' : 'none'; if (hit) any = true; if (term && hit) d.open = true; });
        none.style.display = any ? 'none' : 'block';
      });
    });
  }
  function wrapTables() {
    // A wide table scrolls inside its own box; the page never scrolls sideways.
    $$('.L table').forEach(function (t) {
      if (t.parentElement.classList.contains('tablewrap')) return;
      var w = document.createElement('div');
      w.className = 'tablewrap';
      t.parentElement.insertBefore(w, t);
      w.appendChild(t);
    });
  }
  function widgets() { wrapTables(); copyButtons(); player(); playground(); moodsTable(); troubleSearch(); }

  // ---------------- start ----------------
  $$('.langs button').forEach(function (b) { b.addEventListener('click', function () { setLang(b.dataset.l); }); });
  $('.themebtn').addEventListener('click', function () {
    var cur = store('theme') || 'auto';
    setTheme({ auto: 'light', light: 'dark', dark: 'auto' }[cur] || 'auto');
  });
  setTheme(store('theme') || 'auto');
  setLang(pickLang());
  if (location.hash && !/^#(fa|en|ja)$/.test(location.hash)) {
    var target = document.getElementById(location.hash.slice(1)) || $('.L.on [data-anchor="' + location.hash.slice(1) + '"]');
    if (target) setTimeout(function () { target.scrollIntoView(); }, 50);
  }
})();
