/* Vocana studio - the page half. No framework and no build step: the DOM is
   made with h(), text always goes in as text, and every request carries the
   per-start token from the boot block. */
(function () {
  'use strict';

  var BOOT = JSON.parse(document.getElementById('boot').textContent);
  var I18N = window.VOCANA_I18N;
  var TOKEN = BOOT.token;

  // ==================================================================
  // State
  // ==================================================================
  var S = {
    lang: 'en', theme: 'auto', status: null, plan: null, planSeq: 0, voices: null, voiceInfo: {},
    script: { name: '', text: '', saved: '', mtime: 0 }, settings: null, renders: null, words: null, moods: null,
    job: null, lastResult: null, curLine: 0, view: '', lost: false, beatFails: 0, preview: null, editor: null,
    showKana: true, routeArg: ''
  };
  var audio = new Audio();
  audio.preload = 'auto';

  // ==================================================================
  // Small helpers
  // ==================================================================
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function h(tag, props) {
    var parts = tag.split('.');
    var el = document.createElement(parts[0] || 'div');
    if (parts.length > 1) el.className = parts.slice(1).join(' ');
    props = props || {};
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v === undefined || v === null || v === false) return;
      if (k === 'class') el.className += (el.className ? ' ' : '') + v;
      else if (k === 'text') el.textContent = v;
      else if (k === 'html') el.innerHTML = v;   // only ever built from esc()-ed parts
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.slice(0, 2) === 'on' && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === 'value') el.value = v;
      else if (k === 'checked') el.checked = !!v;
      else if (k === 'selected') el.selected = !!v;
      else if (k === 'disabled') el.disabled = !!v;
      else el.setAttribute(k, v === true ? '' : String(v));
    });
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, kid) {
    if (kid === null || kid === undefined || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { add(el, k); }); return; }
    el.appendChild(typeof kid === 'object' ? kid : document.createTextNode(String(kid)));
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments, me = this; clearTimeout(t); t = setTimeout(function () { fn.apply(me, a); }, ms); };
  }
  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem('vocana.' + key) || 'null');
      if (val === null) localStorage.removeItem('vocana.' + key);
      else localStorage.setItem('vocana.' + key, JSON.stringify(val));
    } catch (e) { return null; }
  }

  // ==================================================================
  // Language
  // ==================================================================
  function systemLang() {
    var l = (navigator.languages && navigator.languages[0]) || navigator.language || 'en';
    l = l.toLowerCase();
    if (l.indexOf('fa') === 0) return 'fa';
    if (l.indexOf('ja') === 0) return 'ja';
    return 'en';
  }
  function fmtNum(n, digits) {
    if (typeof n !== 'number') return n;
    var opts = { maximumFractionDigits: digits === undefined ? 1 : digits };
    try { return new Intl.NumberFormat(S.lang === 'fa' ? 'fa-IR' : S.lang, opts).format(n); } catch (e) { return String(n); }
  }
  function t(key, vars) {
    var s;
    if (vars && vars.n === 1 && I18N[S.lang] && I18N[S.lang][key + '.one'] !== undefined) s = I18N[S.lang][key + '.one'];
    if (s === undefined) s = (I18N[S.lang] && I18N[S.lang][key]);
    if (s === undefined) s = I18N.en[key];
    if (s === undefined) return key;
    if (vars) {
      s = s.replace(/\{(\w+)\}/g, function (m, k) {
        var v = vars[k];
        if (v === undefined || v === null) return '';
        return typeof v === 'number' ? fmtNum(v) : String(v);
      });
    }
    return s;
  }
  function applyLang() {
    var lang = (S.settings && S.settings.lang) || BOOT.lang || 'auto';
    S.lang = lang === 'auto' ? systemLang() : lang;
    if (!I18N[S.lang]) S.lang = 'en';
    document.documentElement.lang = S.lang;
    document.documentElement.dir = S.lang === 'fa' ? 'rtl' : 'ltr';
  }
  function applyTheme() {
    var th = (S.settings && S.settings.theme) || BOOT.theme || 'auto';
    S.theme = th;
    var dark = th === 'dark' || (th === 'auto' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }
  function fmtDur(sec) {
    if (!isFinite(sec)) return '';
    if (sec < 60) return t('c.seconds', { s: Math.round(sec * 10) / 10 });
    var m = Math.floor(sec / 60), s = Math.round(sec - m * 60);
    var txt = m + ':' + (s < 10 ? '0' : '') + s;
    return S.lang === 'fa' ? txt.replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; }) : txt;
  }
  function clock(sec) {
    if (!isFinite(sec)) sec = 0;
    var m = Math.floor(sec / 60), s = sec - m * 60;
    return m + ':' + (s < 10 ? '0' : '') + s.toFixed(1);
  }

  // ==================================================================
  // Icons (24px, stroke)
  // ==================================================================
  var ICONS = {
    script: 'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4',
    cast: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75',
    renders: 'M3 12h2 M7 7v10 M11 4v16 M15 8v8 M19 10v4 M21 12h0',
    words: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z M9 7h7 M9 11h5',
    moods: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M8 14s1.5 2 4 2 4-2 4-2 M9 9h.01 M15 9h.01',
    settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z',
    guide: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z',
    install: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3',
    play: 'M7 4l13 8-13 8z', pause: 'M7 4h4v16H7z M14 4h4v16h-4z', stop: 'M6 6h12v12H6z',
    save: 'M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z M17 21v-8H7v8 M7 3v5h8',
    folder: 'M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z',
    download: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3',
    plus: 'M12 5v14 M5 12h14', trash: 'M3 6h18 M8 6V4h8v2 M19 6l-1 14H6L5 6',
    x: 'M18 6L6 18 M6 6l12 12', check: 'M20 6L9 17l-5-5',
    warn: 'M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z M12 9v4 M12 17h.01',
    info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 16v-4 M12 8h.01',
    copy: 'M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1',
    refresh: 'M23 4v6h-6 M1 20v-6h6 M3.5 9a9 9 0 0 1 14.9-3.4L23 10 M1 14l4.6 4.4A9 9 0 0 0 20.5 15',
    sun: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4',
    moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
    auto: 'M12 22a10 10 0 1 0 0-20v20z M12 2a10 10 0 0 1 0 20',
    open: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6 M15 3h6v6 M10 14L21 3',
    upload: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12',
    sparkle: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z',
    back: 'M11 17l-5-5 5-5 M18 17l-5-5 5-5', fwd: 'M13 17l5-5-5-5 M6 17l5-5-5-5',
    keyboard: 'M20 5H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z M6 9h.01 M10 9h.01 M14 9h.01 M18 9h.01 M8 13h8',
    power: 'M18.4 6.6a9 9 0 1 1-12.8 0 M12 2v10', search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3',
    mic: 'M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v4 M8 23h8',
    edit: 'M12 20h9 M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z',
    loader: 'M12 2v4 M12 18v4 M4.9 4.9l2.8 2.8 M16.3 16.3l2.8 2.8 M2 12h4 M18 12h4 M4.9 19.1l2.8-2.8 M16.3 7.7l2.8-2.8'
  };
  function icon(name, cls) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', name === 'play' ? 'currentColor' : 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('aria-hidden', 'true');
    if (cls) svg.setAttribute('class', cls);
    (ICONS[name] || '').split(' M').forEach(function (d, i) {
      var p = document.createElementNS(ns, 'path');
      p.setAttribute('d', (i ? 'M' : '') + d);
      svg.appendChild(p);
    });
    return svg;
  }
  function btn(label, ic, onclick, cls, attrs) {
    var b = h('button.btn' + (cls ? '.' + cls.split(' ').join('.') : ''), Object.assign({ type: 'button', onclick: onclick }, attrs || {}));
    if (ic) b.appendChild(icon(ic));
    if (label) b.appendChild(h('span', { text: label }));
    if (!label && attrs && attrs.title) b.setAttribute('aria-label', attrs.title);
    return b;
  }
  function busyBtn(b, on) {
    if (on) {
      b.disabled = true;
      b.dataset.busy = '1';
      var sp = icon('loader', 'spin');
      sp.classList.add('busy-icon');
      b.insertBefore(sp, b.firstChild);
    } else {
      b.disabled = false;
      delete b.dataset.busy;
      $$('.busy-icon', b).forEach(function (x) { x.remove(); });
    }
  }

  // ==================================================================
  // Talking to the studio server
  // ==================================================================
  function api(path, body, opts) {
    opts = opts || {};
    var init = { method: body === undefined ? 'GET' : 'POST', headers: { 'X-Vocana-Token': TOKEN }, cache: 'no-store' };
    if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    return fetch(path, init).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) {
          var err = new Error(data.message || data.error || ('HTTP ' + r.status));
          err.status = r.status; err.code = data.error; err.data = data;
          if (r.status === 403 && data.error === 'bad_token') showLost(true);
          throw err;
        }
        S.beatFails = 0;
        if (S.lost) hideLost();
        return data;
      });
    }, function (e) {
      var err = new Error(e.message || 'network');
      err.network = true;
      throw err;
    });
  }
  function media(path) { return path + (path.indexOf('?') < 0 ? '?' : '&') + 't=' + encodeURIComponent(TOKEN); }
  function failToast(e) {
    if (e && e.network) return;
    if (e && e.code === 'engine_down') { toast(t('engine.needed'), 'bad'); return; }
    toast((e && e.message) || t('c.error'), 'bad');
  }

  // ==================================================================
  // Toasts and dialogs
  // ==================================================================
  var toastBox;
  function toast(text, kind, ms) {
    if (!toastBox) { toastBox = h('div.toasts', { role: 'status', 'aria-live': 'polite' }); document.body.appendChild(toastBox); }
    var el = h('div.toast' + (kind === 'bad' ? '.bad' : ''), {}, icon(kind === 'bad' ? 'warn' : 'check'), h('div.t', { text: text }),
      h('button', { type: 'button', 'aria-label': t('c.close'), onclick: function () { el.remove(); } }, icon('x')));
    toastBox.appendChild(el);
    setTimeout(function () { el.remove(); }, ms || (kind === 'bad' ? 7000 : 3500));
  }
  function dialog(opts) {
    return new Promise(function (resolve) {
      var prev = document.activeElement;
      var ov = h('div.overlay', { role: 'presentation' });
      var dlg = h('div.dialog' + (opts.wide ? '.wide' : ''), { role: 'dialog', 'aria-modal': 'true', 'aria-label': opts.title || '' });
      var input = null;
      function done(v) { ov.remove(); document.removeEventListener('keydown', onKey, true); if (prev && prev.focus) prev.focus(); resolve(v); }
      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); done(null); }
        if (e.key === 'Tab') {
          var f = $$('button, input, select, textarea, a[href], [tabindex="0"]', dlg).filter(function (x) { return !x.disabled && x.offsetParent !== null; });
          if (!f.length) return;
          if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
          else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
        }
      }
      var head = h('header', {}, h('h2', { text: opts.title || '' }), h('button.btn.icon.ghost.sm', { type: 'button', 'aria-label': t('c.close'), onclick: function () { done(null); } }, icon('x')));
      var body = h('div.body');
      if (opts.text) body.appendChild(h('p', { text: opts.text, style: { whiteSpace: 'pre-line', margin: '4px 0 8px' } }));
      if (opts.content) add(body, typeof opts.content === 'function' ? opts.content(done) : opts.content);
      if (opts.prompt !== undefined) {
        input = h('input', { type: 'text', value: opts.prompt || '', 'aria-label': opts.title || '', dir: opts.inputDir || 'auto' });
        input.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); done(input.value); } });
        body.appendChild(input);
      }
      var foot = h('footer');
      (opts.buttons || [{ label: t('c.ok'), value: true, primary: true }]).forEach(function (b) {
        foot.appendChild(btn(b.label, b.icon, function () { done(input && b.value === true ? input.value : b.value); },
          b.primary ? 'primary' : (b.danger ? 'danger solid' : '')));
      });
      add(dlg, [head, body, opts.noFooter ? null : foot]);
      ov.appendChild(dlg);
      ov.addEventListener('mousedown', function (e) { if (e.target === ov) done(null); });
      document.body.appendChild(ov);
      document.addEventListener('keydown', onKey, true);
      setTimeout(function () { (input || $('footer .btn.primary', dlg) || $('footer .btn', dlg) || dlg).focus(); if (input) input.select(); }, 10);
    });
  }
  function confirmBox(text, okLabel, danger) {
    return dialog({ title: 'Vocana', text: text, buttons: [{ label: t('c.cancel'), value: false }, { label: okLabel || t('c.ok'), value: true, primary: !danger, danger: danger }] });
  }
  function copyText(text, msg) {
    var ok = function () { toast(msg || t('c.copied')); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok, function () { fallbackCopy(text); ok(); });
    } else { fallbackCopy(text); ok(); }
  }
  function fallbackCopy(text) {
    var ta = h('textarea', { style: { position: 'fixed', top: '-1000px' } });
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* nothing more to try */ }
    ta.remove();
  }
  function showLost(badToken) {
    if (S.lost) return;
    S.lost = true;
    var box = h('div.lost', { id: 'lost', role: 'alertdialog' }, h('img', { src: '/brand/vocana-128.png', alt: '' }),
      h('h2', { text: t('conn.lost'), style: { margin: 0 } }), h('p.muted', { text: t('conn.lost_body') }),
      h('div', {}, btn(t('conn.reload'), 'refresh', function () { location.reload(); }, 'primary')));
    document.body.appendChild(box);
    if (badToken) S.lostToken = true;
  }
  function hideLost() {
    if (S.lostToken) return;
    S.lost = false;
    var b = $('#lost');
    if (b) b.remove();
  }

  // ==================================================================
  // Script text: parsing helpers shared by the editor and the cast page
  // ==================================================================
  var TAG_RE = '[A-Za-z_\\u3040-\\u30ff\\u4e00-\\u9fff\\uff66-\\uff9f][\\w\\-.\\u3040-\\u30ff\\u4e00-\\u9fff\\uff66-\\uff9f]*';
  var LINE_RE = new RegExp('^(\\s*)(' + TAG_RE + ')?(\\s*)(\\[[^\\]]*\\])?(\\s*)([:：])(\\s*)(.*)$');
  var CAST_RE = new RegExp('^(\\s*)(@?\\s*cast)(\\s+)(' + TAG_RE + ')(\\s*[=:：]\\s*)(.*)$', 'i');
  var SET_RE = /^(\s*)(sentence_gap|gap)(\s*[=:]\s*)([\d.]+\s*s?)(\s*)$/i;
  var PAUSE_RE = /^\s*\(\s*pause\s+[\d.]+\s*s?\s*\)\s*$/i;

  function tagColor(tag) {
    var hsh = 0;
    for (var i = 0; i < tag.length; i++) hsh = (hsh * 31 + tag.charCodeAt(i)) >>> 0;
    var hues = [150, 205, 265, 330, 25, 45, 180, 290, 110, 0];
    var hue = hues[hsh % hues.length];
    var dark = document.documentElement.dataset.theme === 'dark';
    return 'hsl(' + hue + ' ' + (dark ? '65%' : '55%') + ' ' + (dark ? '70%' : '38%') + ')';
  }
  function moodSet() {
    var m = S.moods && S.moods.moods;
    return m ? m : null;
  }
  function hlText(s) {
    var out = '';
    var re = /(\[[^\]]*\])|(\(\s*pause\s+[\d.]+\s*s?\s*\))|(\([^)]*\))|(\*[^*\s][^*]*\*)|(\b[A-Za-z]*([A-Za-z])\6\6[A-Za-z]*\b)|(\.{3,}|[!?~♡❤…—！？～〜。]+)|([\u3041-\u30ff\u4e00-\u9fff\uff66-\uff9f]+)/g;
    var last = 0, m;
    var moods = moodSet();
    while ((m = re.exec(s))) {
      out += esc(s.slice(last, m.index));
      var tok = esc(m[0]);
      if (m[1]) {
        var bad = moods && m[1].slice(1, -1).split(/[\s,]+/).some(function (x) { return x && !moods[x.toLowerCase()]; });
        out += '<span class="' + (bad ? 't-mood-bad' : 't-mood') + '">' + tok + '</span>';
      } else if (m[2]) out += '<span class="t-pause">' + tok + '</span>';
      else if (m[3]) out += '<span class="t-com">' + tok + '</span>';
      else if (m[4]) out += '<span class="t-emph">' + tok + '</span>';
      else if (m[5]) out += '<span class="t-str">' + tok + '</span>';
      else if (m[7]) out += '<span class="t-punct">' + tok + '</span>';
      else if (m[8]) out += '<span class="t-kana">' + tok + '</span>';
      else out += tok;
      last = m.index + m[0].length;
    }
    return out + esc(s.slice(last));
  }
  function hlLine(line) {
    var tr = line.trim();
    if (!tr) return '';
    if (tr[0] === '#') return '<span class="t-com">' + esc(line) + '</span>';
    var m = SET_RE.exec(line);
    if (m) return esc(m[1]) + '<span class="t-dir">' + esc(m[2]) + '</span>' + esc(m[3]) + '<span class="t-pause">' + esc(m[4]) + '</span>' + esc(m[5]);
    m = CAST_RE.exec(line);
    if (m) {
      return esc(m[1]) + '<span class="t-dir">' + esc(m[2]) + '</span>' + esc(m[3]) +
        '<span class="t-tag" style="color:' + tagColor(m[4].toUpperCase()) + '">' + esc(m[4]) + '</span>' +
        '<span class="t-colon">' + esc(m[5]) + '</span><span class="t-kana">' + esc(m[6]) + '</span>';
    }
    if (PAUSE_RE.test(line)) return '<span class="t-pause">' + esc(line) + '</span>';
    if (/^\s*@/.test(line)) return '<span class="t-dir">' + esc(line) + '</span>';
    m = LINE_RE.exec(line);
    if (m && (m[2] || m[4])) {
      var tag = (m[2] || 'ME').toUpperCase();
      return esc(m[1]) + (m[2] ? '<span class="t-tag" style="color:' + tagColor(tag) + '">' + esc(m[2]) + '</span>' : '') +
        esc(m[3]) + (m[4] ? hlText(m[4]) : '') + esc(m[5]) + '<span class="t-colon">' + esc(m[6]) + '</span>' + esc(m[7]) + hlText(m[8]);
    }
    return hlText(line);
  }
  function lineOffsets(text) {
    var offs = [0];
    for (var i = 0; i < text.length; i++) if (text.charCodeAt(i) === 10) offs.push(i + 1);
    return offs;
  }
  function setCastLine(text, tag, spec) {
    var lines = text.split('\n');
    var line = null;
    if (spec) {
      var head = spec.speaker + (spec.style ? ' / ' + spec.style : '');
      var opts = [];
      if (spec.pitch && Math.abs(spec.pitch) > 1e-9) opts.push('pitch ' + (spec.pitch > 0 ? '+' : '') + (+spec.pitch.toFixed(2)));
      if (spec.speed && Math.abs(spec.speed - 1) > 1e-9) opts.push('speed ' + (+spec.speed.toFixed(2)));
      if (spec.volume && Math.abs(spec.volume - 1) > 1e-9) opts.push('volume ' + (+spec.volume.toFixed(2)));
      line = '@cast ' + tag + ' = ' + [head].concat(opts).join(', ');
    }
    var idx = -1, lastCast = -1;
    for (var i = 0; i < lines.length; i++) {
      var m = CAST_RE.exec(lines[i]);
      if (m) {
        lastCast = i;
        if (m[4].toUpperCase() === tag.toUpperCase()) idx = i;
      }
    }
    if (idx >= 0) {
      if (line === null) lines.splice(idx, 1); else lines[idx] = line;
    } else if (line !== null) {
      var at = lastCast >= 0 ? lastCast + 1 : 0;
      if (lastCast < 0) {
        // after the leading comments, but before the first blank line or setting
        at = 0;
        while (at < lines.length && lines[at].trim()[0] === '#') at++;
      }
      lines.splice(at, 0, line);
    }
    return lines.join('\n');
  }

  // ==================================================================
  // The editor: a textarea over a highlighted copy of its text
  // ==================================================================
  function Editor(onChange, onCursor) {
    var wrap = h('div.editor');
    var pre = h('pre', { 'aria-hidden': 'true' });
    var ta = h('textarea', { spellcheck: 'false', autocomplete: 'off', autocapitalize: 'off', autocorrect: 'off', wrap: 'soft', dir: 'ltr', 'aria-label': t('nav.script') });
    wrap.appendChild(pre);
    wrap.appendChild(ta);
    var marks = {}, playing = 0, cur = 0;
    function paint() {
      var lines = ta.value.split('\n');
      var html = '';
      for (var i = 0; i < lines.length; i++) {
        var n = i + 1;
        var cls = 'ln' + (n === cur ? ' cur' : '') + (marks[n] ? ' has-warn' : '') + (n === playing ? ' playing' : '');
        html += '<span class="' + cls + '" data-n="' + n + '">' + (hlLine(lines[i]) || '&#8203;') + '</span>';
      }
      pre.innerHTML = html;
      pre.scrollTop = ta.scrollTop;
    }
    function cursorLine() {
      var pos = ta.selectionStart || 0;
      var n = 1;
      var v = ta.value;
      for (var i = 0; i < pos && i < v.length; i++) if (v.charCodeAt(i) === 10) n++;
      return n;
    }
    function updCursor() {
      var n = cursorLine();
      if (n !== cur) {
        var old = pre.querySelector('.ln.cur');
        if (old) old.classList.remove('cur');
        cur = n;
        var el = pre.querySelector('[data-n="' + n + '"]');
        if (el) el.classList.add('cur');
        onCursor(n);
      }
    }
    ta.addEventListener('input', function () { paint(); onChange(ta.value); updCursor(); });
    ta.addEventListener('scroll', function () { pre.scrollTop = ta.scrollTop; });
    ['keyup', 'click', 'select', 'focus'].forEach(function (ev) { ta.addEventListener(ev, updCursor); });
    if (window.ResizeObserver) new ResizeObserver(function () { pre.scrollTop = ta.scrollTop; }).observe(wrap);
    var api_ = {
      el: wrap, ta: ta,
      get: function () { return ta.value; },
      set: function (v) { ta.value = v; cur = 0; paint(); updCursor(); },
      repaint: paint,
      marks: function (m) { marks = m || {}; paint(); },
      playing: function (n) { playing = n || 0; paint(); },
      line: cursorLine,
      insert: function (text, selectInner) {
        ta.focus();
        var ok = false;
        try { ok = document.execCommand('insertText', false, text); } catch (e) { ok = false; }
        if (!ok) { ta.setRangeText(text, ta.selectionStart, ta.selectionEnd, 'end'); ta.dispatchEvent(new Event('input')); }
        if (selectInner) {
          var end = ta.selectionEnd;
          ta.setSelectionRange(end - text.length + selectInner[0], end - text.length + selectInner[1]);
        }
      },
      wrapSel: function (before, after, placeholder) {
        var s = ta.selectionStart, e = ta.selectionEnd;
        var sel = ta.value.slice(s, e) || placeholder || '';
        api_.insert(before + sel + after, [before.length, before.length + sel.length]);
      },
      replaceAll: function (v) {
        // Through the undo stack when the browser allows it.
        ta.focus();
        var top = ta.scrollTop;
        ta.setSelectionRange(0, ta.value.length);
        var ok = false;
        try { ok = document.execCommand('insertText', false, v); } catch (e) { ok = false; }
        if (!ok) { ta.value = v; ta.dispatchEvent(new Event('input')); }
        ta.setSelectionRange(0, 0);
        ta.scrollTop = top;
      },
      goLine: function (n, select) {
        var offs = lineOffsets(ta.value);
        var a = offs[n - 1] || 0, b = (offs[n] || ta.value.length + 1) - 1;
        ta.focus();
        ta.setSelectionRange(a, select ? b : a);
        var el = pre.querySelector('[data-n="' + n + '"]');
        if (el) ta.scrollTop = Math.max(0, el.offsetTop - ta.clientHeight / 3);
        updCursor();
      }
    };
    paint();
    return api_;
  }

  // ==================================================================
  // Status, heartbeat, engine
  // ==================================================================
  function loadStatus() {
    return api('/api/status').then(function (st) {
      var was = S.status && S.status.engine && S.status.engine.version;
      S.status = st;
      if (!S.settings) { S.settings = st.settings; applyLang(); applyTheme(); }
      renderPill();
      renderBanners();
      var now = st.engine && st.engine.version;
      if (!was && now) {
        S.voices = null;
        if (S.view === 'cast' || S.view === 'script') { schedulePlan(true); if (S.view === 'cast') route(); }
      }
      return st;
    });
  }
  function pollStatus() {
    loadStatus().catch(function (e) {
      if (e.network) { S.beatFails++; if (S.beatFails >= 2) showLost(); }
    }).then(function () {
      var e = S.status && S.status.engine;
      var fast = !e || !e.version || e.starting;
      setTimeout(pollStatus, fast ? 2500 : 9000);
    });
  }
  function heartbeat() {
    api('/api/heartbeat', {}).catch(function () { /* the status poll reports a closed studio */ });
  }
  function startEngine(b) {
    if (b) busyBtn(b, true);
    return api('/api/engine/start', {}).then(function (r) {
      if (!r.started && r.reason === 'not_found') {
        dialog({ title: t('engine.get'), text: t('engine.notfound'), buttons: [{ label: t('c.close'), value: false }, { label: t('engine.get'), value: true, primary: true }] })
          .then(function (v) { if (v) window.open('https://voicevox.hiroshiba.jp/', '_blank', 'noopener'); });
      } else if (!r.started && r.reason !== 'running') toast(t('engine.start_failed'), 'bad');
      return loadStatus();
    }).catch(failToast).then(function () { if (b) busyBtn(b, false); });
  }
  function engineOn() { return !!(S.status && S.status.engine && S.status.engine.version); }

  // ==================================================================
  // Shell
  // ==================================================================
  var shell = {};
  var NAV = [['script', 'script'], ['cast', 'cast'], ['renders', 'renders'], ['words', 'words'], ['moods', 'moods']];
  function buildShell() {
    var app = clear($('#app'));
    var langSel = h('select', { 'aria-label': t('lang.label'), style: { width: 'auto' }, onchange: function () { saveSettings({ lang: langSel.value }).then(rebuild); } },
      [['auto', t('lang.auto')], ['fa', 'فارسی'], ['en', 'English'], ['ja', '日本語']].map(function (o) {
        return h('option', { value: o[0], selected: ((S.settings && S.settings.lang) || 'auto') === o[0], text: o[1] });
      }));
    var themeIcon = S.theme === 'dark' ? 'moon' : S.theme === 'light' ? 'sun' : 'auto';
    var top = h('header.top', {},
      h('a.brand', { href: '#script' }, h('img', { src: '/brand/vocana-64.png', alt: '' }), h('div', {}, h('b', { text: 'Vocana' }), h('small', { text: t('app.tagline') }))),
      h('div.grow'),
      h('div.top-tools', {},
        shell.pill = h('span'),
        langSel,
        btn('', themeIcon, function () {
          var next = { auto: 'light', light: 'dark', dark: 'auto' }[S.theme] || 'auto';
          saveSettings({ theme: next }).then(rebuild);
        }, 'icon ghost', { title: t('theme.toggle') + ': ' + t('theme.' + S.theme) }),
        btn('', 'keyboard', showKeys, 'icon ghost', { title: t('kb.title') })));
    var side = h('nav.side', { 'aria-label': 'Vocana' });
    NAV.forEach(function (n) {
      side.appendChild(h('a', { href: '#' + n[0], 'data-view': n[0] }, icon(n[1]), h('span', { text: t('nav.' + n[0]) })));
    });
    side.appendChild(h('div.sep'));
    side.appendChild(h('a', { href: '#settings', 'data-view': 'settings' }, icon('settings'), h('span', { text: t('nav.settings') })));
    side.appendChild(h('a', { href: '/guide', target: '_blank', rel: 'noopener' }, icon('guide'), h('span', { text: t('nav.guide') })));
    if (BOOT.windows && !BOOT.installed) side.appendChild(h('a', { href: '#install', 'data-view': 'install' }, icon('install'), h('span', { text: t('nav.install') })));
    side.appendChild(h('div.spacer'));
    side.appendChild(h('div.ver', { text: 'Vocana ' + BOOT.version }));
    shell.main = h('main', { id: 'main', tabindex: '-1' });
    shell.banners = h('div');
    add(app, [top, side, shell.main]);
    renderPill();
  }
  function rebuild() {
    applyLang();
    applyTheme();
    var keep = S.editor ? S.editor.get() : null;
    S.editor = null;
    buildShell();
    route();
    if (keep !== null && S.editor) S.editor.set(keep);
  }
  function renderPill() {
    if (!shell.pill) return;
    var e = S.status && S.status.engine;
    var cls = 'off', label = t('engine.off');
    if (e && e.version) { cls = 'on'; label = t('engine.on', { v: e.version }); }
    else if (e && e.starting) { cls = 'starting'; label = t('engine.starting'); }
    var pill = h('button.pill.' + cls, { type: 'button', title: e ? e.url : '', onclick: function () { if (cls === 'off') startEngine(); else go('settings'); } },
      h('span.dot'), h('span.label', { text: label }));
    shell.pill.replaceWith(pill);
    shell.pill = pill;
  }
  function renderBanners() {
    var box = $('#banners');
    if (!box) return;
    clear(box);
    var st = S.status;
    if (!st) return;
    var e = st.engine;
    if (e && !e.version && ['script', 'cast', 'moods', 'words'].indexOf(S.view) >= 0) {
      var found = e.found && (e.found.engine || e.found.app);
      box.appendChild(h('div.banner.' + (e.starting ? 'info' : 'warn'), {}, icon(e.starting ? 'loader' : 'warn', e.starting ? 'spin' : ''),
        h('div.grow', { text: e.starting ? t('engine.starting') : t('engine.needed') }),
        e.starting ? null : (found ? btn(t('engine.start'), 'power', function () { startEngine(this); }, 'sm primary')
          : btn(t('engine.get'), 'open', function () { window.open('https://voicevox.hiroshiba.jp/', '_blank', 'noopener'); }, 'sm'))));
    }
    if (st.update && st.update.available) {
      box.appendChild(h('div.banner.ok', {}, icon('sparkle'), h('div.grow', { text: t('update.available', { v: st.update.version }) }),
        btn(t('update.get'), 'open', function () { window.open(st.update.url || BOOT.homepage, '_blank', 'noopener'); }, 'sm')));
    }
  }
  function showKeys() {
    var rows = [['Ctrl + S', t('kb.save')], ['Ctrl + Enter', t('kb.preview')], ['Ctrl + Shift + Enter', t('kb.render')], ['?', t('kb.help')]];
    dialog({ title: t('kb.title'), content: h('div.kb', {}, rows.map(function (r) { return [h('kbd', { text: r[0], class: 'ltr' }), h('span', { text: r[1] })]; })) });
  }
  function saveSettings(vals) {
    return api('/api/settings', vals).then(function (s) { S.settings = s; return s; }).catch(failToast);
  }

  // ==================================================================
  // Router
  // ==================================================================
  function go(view) { location.hash = '#' + view; }
  function route() {
    var hash = decodeURIComponent((location.hash || '').slice(1));
    var view = hash.split(/[/=]/)[0] || 'script';
    var arg = hash.indexOf('/') > 0 ? hash.slice(hash.indexOf('/') + 1) : '';
    if (hash.indexOf('script=') === 0) {
      view = 'script';
      if (S.started) openScriptByName(hash.slice(7)); else S.pendingScript = hash.slice(7);
      history.replaceState(null, '', '#script');
    }
    if (!VIEWS[view]) view = 'script';
    S.view = view;
    S.routeArg = arg;
    $$('.side a[data-view]').forEach(function (a) { if (a.dataset.view === view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    var main = clear(shell.main);
    var v = h('div.view');
    v.appendChild(h('div', { id: 'banners' }));
    main.appendChild(v);
    VIEWS[view](v, arg);
    renderBanners();
  }
  window.addEventListener('hashchange', route);

  // ==================================================================
  // Script view
  // ==================================================================
  var schedulePlan = debounce(function () { runPlan(); }, 420);
  function runPlan(force) {
    var text = S.editor ? S.editor.get() : S.script.text;
    var seq = ++S.planSeq;
    return api('/api/plan', { text: text }).then(function (p) {
      if (seq !== S.planSeq) return;
      S.plan = p;
      paintPlan();
      loadAvatars(p);
    }).catch(function (e) { if (!e.network) failToast(e); });
  }
  function dirty() { return S.editor && S.editor.get() !== S.script.saved; }
  function updateDirty() {
    var d = $('#dirty');
    if (d) d.classList.toggle('hidden', !dirty());
    document.title = (dirty() ? '• ' : '') + (S.script.name || t('c.untitled')) + ' — Vocana';
  }
  var saveDraft = debounce(function () {
    if (!S.editor) return;
    if (dirty()) store('draft', { name: S.script.name, text: S.editor.get(), base: S.script.saved, at: Date.now() });
    else store('draft', null);
  }, 800);

  function viewScript(v) {
    var nameIn = h('input.name', { type: 'text', value: S.script.name || '', placeholder: t('c.untitled'), 'aria-label': t('script.name'), dir: 'auto' });
    nameIn.addEventListener('change', function () { S.script.renamed = nameIn.value.trim(); updateDirty(); });
    var renderBtn = btn(t('script.render'), 'mic', function () { doRender(); }, 'primary', { id: 'renderBtn', title: 'Ctrl+Shift+Enter' });
    var bar = h('div.script-bar', {},
      nameIn, h('span.dirty-dot.hidden', { id: 'dirty', title: t('c.unsaved') }),
      btn(t('script.open'), 'folder', openScriptDialog, ''),
      btn(t('script.new'), 'plus', newScript, ''),
      btn(t('script.save'), 'save', function () { saveScript(nameIn.value); }, '', { title: 'Ctrl+S' }),
      btn('', 'upload', importFile, 'icon', { title: t('script.import') }),
      btn('', 'download', exportFile, 'icon', { title: t('script.export') }),
      h('div.grow'),
      btn(t('script.ai'), 'sparkle', copyScriptPrompt, 'ghost', { title: t('script.ai_write') }),
      renderBtn);
    S.editor = Editor(function (text) {
      S.script.text = text;
      updateDirty();
      saveDraft();
      schedulePlan();
    }, function (n) {
      S.curLine = n;
      $$('.linecard.cur').forEach(function (c) { c.classList.remove('cur'); });
      var card = $('.linecard[data-n="' + n + '"]');
      if (card) { card.classList.add('cur'); }
    });
    var size = (S.settings && S.settings.editor_size) || 15;
    S.editor.el.style.setProperty('--ed-size', size + 'px');
    var tools = h('div.editor-tools', {}, h('span.label', { text: t('script.insert') }),
      insertSelect(t('script.ins_speaker'), function () {
        var tags = speakerTags();
        return tags.map(function (x) { return [x, x]; });
      }, function (tag) { insertAtLineStart(tag + ' [normal]: '); }),
      insertSelect(t('script.ins_mood'), function () {
        return Object.keys((S.moods && S.moods.moods) || {}).map(function (m) { return [m, m]; });
      }, function (m) { S.editor.insert('[' + m + '] '); }),
      btn(t('script.ins_pause'), '', function () { S.editor.insert(' (pause 0.5) '); }, 'sm ghost'),
      btn(t('script.ins_emph'), '', function () { S.editor.wrapSel('*', '*', 'word'); }, 'sm ghost'),
      btn(t('script.ins_cast'), '', function () { go('cast'); }, 'sm ghost'));
    var drop = h('div.drop-hint.hidden', { text: t('script.drop') });
    var foot = h('div.editor-foot', {}, h('span', { id: 'summary' }), h('span.grow'), h('span', { text: t('script.preview_hint') }));
    var edWrap = h('div.editor-wrap', {}, tools, S.editor.el, foot, drop);
    edWrap.addEventListener('dragover', function (e) { if (hasFile(e)) { e.preventDefault(); drop.classList.remove('hidden'); } });
    edWrap.addEventListener('dragleave', function (e) { if (e.target === drop) drop.classList.add('hidden'); });
    edWrap.addEventListener('drop', function (e) {
      drop.classList.add('hidden');
      if (!hasFile(e)) return;
      e.preventDefault();
      readFile(e.dataTransfer.files[0]);
    });
    var kanaToggle = h('label.switch.small', {}, h('input', { type: 'checkbox', checked: S.showKana, onchange: function () { S.showKana = this.checked; store('kana', S.showKana); paintPlan(); } }), h('span', { text: t('script.kana_show') }));
    var right = h('div.lines-col', {},
      h('div.card', { id: 'renderCard', class: 'hidden' }),
      h('div.card', {}, h('div.lines-head', {}, h('h2', { text: t('script.lines') }), kanaToggle), h('div.lines', { id: 'lines' })),
      h('div.card', { id: 'checks' }));
    add(v, [bar, h('div.split', {}, edWrap, right)]);
    if (S.script.text) S.editor.set(S.script.text);
    updateDirty();
    if (S.plan) paintPlan();
    runPlan();
    if (S.job && S.job.status === 'running') paintJob();
    else if (S.lastResult) paintResult(S.lastResult);
    setTimeout(function () { S.editor.ta.focus(); }, 30);
  }
  function hasFile(e) { return e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types || [], 'Files') >= 0; }
  function insertSelect(label, options, onPick) {
    var sel = h('select', { 'aria-label': label });
    function fill() {
      clear(sel);
      sel.appendChild(h('option', { value: '', text: label + '…' }));
      options().forEach(function (o) { sel.appendChild(h('option', { value: o[0], text: o[1] })); });
    }
    sel.addEventListener('focus', fill);
    sel.addEventListener('mousedown', fill);
    sel.addEventListener('change', function () { var v = sel.value; sel.value = ''; if (v) onPick(v); });
    fill();
    return sel;
  }
  function speakerTags() {
    var tags = {};
    (S.plan ? S.plan.cast : []).forEach(function (c) { tags[c.who] = 1; });
    if (!Object.keys(tags).length) tags.ME = 1;
    return Object.keys(tags);
  }
  function insertAtLineStart(text) {
    var ta = S.editor.ta;
    var v = ta.value, pos = ta.selectionStart;
    var start = v.lastIndexOf('\n', pos - 1) + 1;
    var lineEnd = v.indexOf('\n', pos); if (lineEnd < 0) lineEnd = v.length;
    var line = v.slice(start, lineEnd);
    if (line.trim()) { ta.setSelectionRange(lineEnd, lineEnd); S.editor.insert('\n' + text); }
    else { ta.setSelectionRange(start, lineEnd); S.editor.insert(text); }
  }

  // -- the line list and the checks ----------------------------------
  function paintPlan() {
    var p = S.plan;
    var box = $('#lines');
    if (!box || !p) return;
    clear(box);
    var marks = {};
    p.warnings.forEach(function (w) { if (w.n) marks[w.n] = (marks[w.n] || []).concat([w]); });
    if (S.editor) S.editor.marks(marks);
    var lines = p.lines.filter(function (l) { return l.kind === 'line'; });
    if (!p.lines.length) box.appendChild(h('div.empty', {}, h('img', { src: '/brand/vocana-128.png', alt: '' }), h('div', { text: t('script.empty') })));
    p.lines.forEach(function (ln) {
      if (ln.kind === 'pause') {
        box.appendChild(h('div.linecard.pause', { 'data-n': ln.n, onclick: function () { S.editor.goLine(ln.n); } }, h('div.avatar.sm', {}, '⏸'), h('div.muted.small', { text: t('script.pause', { s: ln.seconds }) })));
        return;
      }
      var card = h('div.linecard' + (marks[ln.n] ? '.has-warn' : '') + (ln.n === S.curLine ? '.cur' : ''), { 'data-n': ln.n, tabindex: '0' });
      card.addEventListener('click', function (e) { if (!e.target.closest('button')) S.editor.goLine(ln.n, false); });
      card.addEventListener('keydown', function (e) { if (e.key === 'Enter') previewLine(ln.n); });
      var playB = btn('', 'play', function () { previewLine(ln.n, playB); }, 'icon sm', { title: t('script.preview_line') });
      var meta = h('div.meta');
      var seen = {};
      ln.sentences.forEach(function (s) {
        var key = (s.moods || []).join('+') + '>' + s.style;
        if (seen[key]) return;
        seen[key] = 1;
        meta.appendChild(h('span.chip.mood', { text: (s.moods || ['normal']).join(' + ') }));
        if (s.style) meta.appendChild(h('span.chip.style', { text: s.style }));
        if (s.japanese) meta.appendChild(h('span.chip.info', { text: '日本語' }));
      });
      add(card, [avatarFor(ln.who, ln.speaker_uuid, ln.sentences[0] && ln.sentences[0].style_id),
        h('div.who', {}, h('span', { text: ln.who, style: { color: tagColor(ln.who) } }), h('span.cname', { text: ln.character || '' }), h('span.muted.small', { text: '· ' + t('c.line', { n: ln.n }) })),
        playB,
        h('div.txt', { text: ln.caption || ln.text, dir: 'auto' }),
        meta]);
      if (S.showKana) {
        var k = ln.sentences.map(function (s) { return s.kana; }).join('  ');
        if (k) card.appendChild(h('div.kana', { text: k, dir: 'ltr' }));
      }
      (marks[ln.n] || []).forEach(function (w) { card.appendChild(h('div.wl', { text: warnText(w) })); });
      box.appendChild(card);
    });
    // summary
    var sum = $('#summary');
    if (sum) {
      var voices = {};
      lines.forEach(function (l) { if (l.character) voices[l.character] = 1; });
      sum.textContent = t('script.summary', { lines: lines.length, chars: Object.keys(voices).length, dur: fmtDur(p.duration_hint) });
    }
    paintChecks();
  }
  function warnText(w) {
    var key = 'w.' + w.code;
    var txt = I18N.en[key] ? t(key, w) : (w.message || w.code);
    return txt;
  }
  function paintChecks() {
    var box = $('#checks');
    var p = S.plan;
    if (!box || !p) return;
    clear(box);
    var ws = p.warnings;
    box.appendChild(h('h2', {}, icon(ws.length ? 'warn' : 'check'), h('span', { text: ws.length ? t('script.warnings', { n: ws.length }) : t('script.no_warnings') })));
    if (!p.engine) box.appendChild(h('p.hint', { text: t('script.offline') }));
    if (ws.length) {
      var list = h('div.warnlist');
      ws.forEach(function (w) {
        list.appendChild(h('button', { type: 'button', onclick: function () { if (w.n) S.editor.goLine(w.n, true); } },
          h('span.n', { text: w.n ? '#' + w.n : '•' }), h('span', { text: warnText(w) })));
      });
      box.appendChild(list);
    }
    if (p.review && p.review.length) {
      box.appendChild(h('h3', { text: t('script.review') }));
      box.appendChild(h('p.hint', { text: t('script.review_hint') }));
      var r = h('div.review');
      p.review.slice(0, 80).forEach(function (rv) {
        var hear = btn('', 'play', function () { hearText(rv.word, hear); }, 'icon sm ghost', { title: t('c.hear') });
        r.appendChild(h('span.rw', {}, h('span.ltr', { text: rv.word }), h('span.k', { text: rv.kana }), hear,
          btn(t('script.review_add'), '', function () { fixWord(rv.word, rv.kana); }, 'sm ghost')));
      });
      box.appendChild(r);
    }
  }
  function fixWord(word, kana) {
    dialog({
      title: word, prompt: kana, inputDir: 'ltr',
      content: h('p.hint', { text: t('words.kana_help') }),
      buttons: [{ label: t('c.cancel'), value: null }, { label: t('c.save'), value: true, primary: true }]
    }).then(function (v) {
      if (!v || !v.trim()) return;
      if (!/[\u3041-\u30fa]/.test(v)) { toast(t('words.invalid_kana'), 'bad'); return; }
      loadWords().then(function () {
        var w = Object.assign({}, S.words.words);
        w[word.toLowerCase()] = v.trim();
        return api('/api/words', { words: w }).then(function (r) { S.words = r; toast(t('words.saved')); runPlan(); });
      }).catch(failToast);
    });
  }

  // -- avatars ----------------------------------------------------------
  function initials(name) { return (name || '?').replace(/^[^\w\u3040-\u9fff]+/, '').slice(0, 1).toUpperCase(); }
  function avatarFor(who, uuid, styleId, cls) {
    var av = h('div.avatar' + (cls ? '.' + cls : ''), { style: { background: tagColor(who) } });
    var info = uuid && S.voiceInfo[uuid];
    var src = null;
    if (info && info.styles) {
      var st = info.styles.filter(function (s) { return s.id === styleId; })[0] || info.styles[0];
      src = st && st.icon;
    }
    if (src) av.appendChild(h('img', { src: src, alt: '' }));
    else av.appendChild(document.createTextNode(initials(who)));
    if (uuid) av.dataset.uuid = uuid;
    return av;
  }
  function voiceInfo(uuid) {
    if (S.voiceInfo[uuid]) return Promise.resolve(S.voiceInfo[uuid]);
    if (S.voiceInfo['p:' + uuid]) return S.voiceInfo['p:' + uuid];
    var p = api('/api/voice?uuid=' + encodeURIComponent(uuid)).then(function (info) { S.voiceInfo[uuid] = info; return info; });
    S.voiceInfo['p:' + uuid] = p;
    p.catch(function () { delete S.voiceInfo['p:' + uuid]; });
    return p;
  }
  function loadAvatars(p) {
    var need = {};
    (p.cast || []).forEach(function (c) { if (c.speaker_uuid && !S.voiceInfo[c.speaker_uuid]) need[c.speaker_uuid] = 1; });
    var list = Object.keys(need);
    if (!list.length) return;
    Promise.all(list.map(function (u) { return voiceInfo(u).catch(function () { return null; }); })).then(function () {
      if (S.view === 'script') paintPlan();
    });
  }
  function loadVoices(refresh) {
    if (S.voices && !refresh) return Promise.resolve(S.voices);
    return api('/api/voices' + (refresh ? '?refresh=1' : '')).then(function (v) { S.voices = v; return v; });
  }

  // -- previews -------------------------------------------------------
  function stopAudio() {
    audio.pause();
    if (S.preview && S.preview.stop) S.preview.stop();
    S.preview = null;
  }
  function playPreview(res, card, b) {
    stopAudio();
    audio.src = res.url;
    var words = [];
    res.sentences.forEach(function (s) { s.words.forEach(function (w) { words.push(w); }); });
    var txt = card && $('.txt', card);
    var oldTxt = txt ? txt.textContent : '';
    var spans = [];
    if (txt && words.length) {
      clear(txt);
      words.forEach(function (w, i) {
        var sp = h('span.w', { text: w.word });
        spans.push(sp);
        txt.appendChild(sp);
        if (i < words.length - 1) txt.appendChild(document.createTextNode(' '));
      });
    }
    var raf = 0;
    function tick() {
      var tm = audio.currentTime;
      for (var i = 0; i < words.length; i++) spans[i] && spans[i].classList.toggle('on', tm >= words[i].start && tm < words[i].end + 0.05);
      raf = requestAnimationFrame(tick);
    }
    var state = {
      stop: function () {
        cancelAnimationFrame(raf);
        if (txt) txt.textContent = oldTxt;
        if (b) { clear(b); b.appendChild(icon('play')); }
        if (S.editor) S.editor.playing(0);
      }
    };
    S.preview = state;
    if (b) { clear(b); b.appendChild(icon('stop')); }
    if (S.editor && res.n) S.editor.playing(res.n);
    audio.onended = function () { if (S.preview === state) stopAudio(); };
    audio.play().then(tick, function () { stopAudio(); });
  }
  function previewLine(n, b) {
    if (S.preview && b && $('svg path', b) && S.preview.n === n) { stopAudio(); return; }
    if (!engineOn()) { toast(t('engine.needed'), 'bad'); return; }
    var card = $('.linecard[data-n="' + n + '"]');
    b = b || (card && $('.btn', card));
    if (b) busyBtn(b, true);
    api('/api/preview', { text: S.editor.get(), n: n }).then(function (res) {
      if (b) busyBtn(b, false);
      playPreview(res, card, b);
      if (S.preview) S.preview.n = n;
      (res.warnings || []).forEach(function (w) { toast(warnText(w)); });
    }).catch(function (e) { if (b) busyBtn(b, false); failToast(e); });
  }
  function hearText(text, b, character) {
    if (!engineOn()) { toast(t('engine.needed'), 'bad'); return Promise.resolve(); }
    if (b) busyBtn(b, true);
    return api('/api/preview', { line: 'ME: ' + text, character: character || null }).then(function (res) {
      if (b) busyBtn(b, false);
      playPreview(res, null, null);
    }).catch(function (e) { if (b) busyBtn(b, false); failToast(e); });
  }
  function hearLine(line, character, b) {
    if (!engineOn()) { toast(t('engine.needed'), 'bad'); return; }
    if (b) busyBtn(b, true);
    api('/api/preview', { line: line, character: character || null }).then(function (res) {
      if (b) busyBtn(b, false);
      playPreview(res, null, null);
    }).catch(function (e) { if (b) busyBtn(b, false); failToast(e); });
  }

  // -- open / save / new / import -------------------------------------
  function guardDirty() {
    if (!dirty()) return Promise.resolve(true);
    return dialog({ title: 'Vocana', text: t('script.confirm_discard', { name: S.script.name || t('c.untitled') }),
      buttons: [{ label: t('c.keep'), value: false }, { label: t('c.discard'), value: true, danger: true }] });
  }
  function setScript(name, text, opts) {
    S.script = { name: name, text: text, saved: (opts && opts.unsaved) ? '' : text, mtime: (opts && opts.mtime) || 0 };
    S.plan = null;
    if (S.view !== 'script') {
      // The script view picks the text up when it is shown next.
      if (opts && opts.show) go('script');
      return;
    }
    if (S.editor) S.editor.set(text);
    var n = $('.script-bar .name');
    if (n) n.value = name;
    updateDirty();
    runPlan();
  }
  function openScriptByName(name) {
    return api('/api/scripts/' + encodeURIComponent(name)).then(function (r) {
      setScript(r.name, r.text, { mtime: r.mtime, show: S.started });
      if (r.encoding && r.encoding !== 'utf-8') toast(t('script.encoding', { enc: r.encoding }));
      toast(t('script.imported', { name: r.name }));
    }).catch(failToast);
  }
  function openScriptDialog() {
    guardDirty().then(function (ok) {
      if (!ok) return;
      api('/api/scripts').then(function (r) {
        var filter = h('input', { type: 'search', placeholder: t('script.filter'), dir: 'auto' });
        var list = h('div.rlist', { style: { maxHeight: '50vh' } });
        function paint() {
          clear(list);
          var q = filter.value.toLowerCase();
          var items = r.scripts.filter(function (s) { return !q || s.name.toLowerCase().indexOf(q) >= 0; });
          if (!items.length) list.appendChild(h('div.empty', { text: t('script.none') }));
          items.forEach(function (s) {
            list.appendChild(h('div.ritem', { tabindex: '0', onclick: function () { done(s.name); }, onkeydown: function (e) { if (e.key === 'Enter') done(s.name); } },
              h('b', { text: s.name, dir: 'auto' }), h('span.muted.small', { text: new Date(s.mtime * 1000).toLocaleString(S.lang) })));
          });
        }
        var done;
        filter.addEventListener('input', paint);
        dialog({
          title: t('script.open_title'),
          content: function (d) { done = d; paint(); setTimeout(function () { filter.focus(); }, 20); return [filter, h('div', { style: { height: '8px' } }), list, h('p.hint', { text: r.folder, dir: 'ltr' })]; },
          buttons: [{ label: t('c.cancel'), value: null }, { label: t('renders.folder'), value: '__folder', icon: 'folder' }]
        }).then(function (name) {
          if (name === '__folder') { api('/api/open', { what: 'scripts' }).catch(failToast); return; }
          if (name) openScriptByName(name);
        });
      }).catch(failToast);
    });
  }
  function newScript() {
    guardDirty().then(function (ok) {
      if (!ok) return;
      var tpl = '# ' + t('c.untitled') + '\n@cast ME = ' + ((S.moods && S.moods.speaker) || 'ずんだもん') + '\ngap = 0.4\n\nME [happy]: Hello! \n';
      setScript('', tpl, { unsaved: true, show: true });
      setTimeout(function () { if (S.editor) S.editor.goLine(5); }, 50);
    });
  }
  function saveScript(name, overwrite) {
    name = (name || '').trim() || S.script.name;
    if (!name) {
      return dialog({ title: t('script.name'), prompt: '', buttons: [{ label: t('c.cancel'), value: null }, { label: t('c.save'), value: true, primary: true }] })
        .then(function (v) { if (v && v.trim()) return saveScript(v.trim()); });
    }
    var text = S.editor ? S.editor.get() : S.script.text;
    var replacing = overwrite || name === S.script.name;
    return api('/api/scripts/save', { name: name, text: text, overwrite: replacing }).then(function (r) {
      S.script.name = r.name;
      S.script.saved = text;
      var n = $('.script-bar .name');
      if (n) n.value = r.name;
      updateDirty();
      store('draft', null);
      toast(t('script.saved', { name: r.name }));
      return r;
    }).catch(function (e) {
      if (e.code === 'exists') {
        return confirmBox(t('script.exists', { name: e.data.name }), t('c.save')).then(function (ok) { if (ok) return saveScript(name, true); });
      }
      failToast(e);
    });
  }
  function importFile() {
    var inp = h('input', { type: 'file', accept: '.txt,text/plain' });
    inp.addEventListener('change', function () { if (inp.files[0]) readFile(inp.files[0]); });
    inp.click();
  }
  function readFile(file) {
    if (!file) return;
    guardDirty().then(function (ok) {
      if (!ok) return;
      var r = new FileReader();
      r.onload = function () {
        var buf = new Uint8Array(r.result);
        var text;
        try { text = new TextDecoder('utf-8', { fatal: true }).decode(buf); }
        catch (e) {
          try { text = new TextDecoder(buf[0] === 0xff && buf[1] === 0xfe ? 'utf-16le' : 'windows-1252').decode(buf); } catch (e2) { text = ''; }
          toast(t('script.encoding', { enc: 'ANSI' }));
        }
        text = text.replace(/^\ufeff/, '').replace(/\r\n?/g, '\n');
        setScript(file.name.replace(/\.txt$/i, ''), text, { unsaved: true, show: true });
        toast(t('script.imported', { name: file.name }));
      };
      r.readAsArrayBuffer(file);
    });
  }
  function exportFile() {
    var text = S.editor ? S.editor.get() : S.script.text;
    var blob = new Blob([text.replace(/\n/g, '\r\n')], { type: 'text/plain;charset=utf-8' });
    var a = h('a', { href: URL.createObjectURL(blob), download: (S.script.name || 'script') + '.txt' });
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function copyScriptPrompt() {
    var moods = Object.keys((S.moods && S.moods.moods) || {}).join(', ');
    var chars = (S.voices && S.voices.characters ? S.voices.characters.map(function (c) { return c.name; }) : ['ずんだもん', '四国めたん']).join(', ');
    copyText(t('ai.script', { moods: moods, characters: chars }), t('script.ai_copied'));
  }

  // -- rendering --------------------------------------------------------
  function doRender() {
    if (S.job && S.job.status === 'running') { toast(t('render.busy'), 'bad'); return; }
    if (!engineOn()) { toast(t('engine.needed'), 'bad'); return; }
    var nameEl = $('.script-bar .name');
    var name = (nameEl && nameEl.value.trim()) || S.script.name;
    var pre = Promise.resolve();
    if (!name) pre = saveScript('').then(function () { name = S.script.name; });
    else if (dirty() || name !== S.script.name) pre = saveScript(name);
    pre.then(function () {
      if (!name) return;
      return api('/api/render', { text: S.editor.get(), name: name }).then(function (job) {
        S.job = job;
        S.lastResult = null;
        paintJob();
        pollJob(job.id);
      });
    }).catch(failToast);
  }
  function pollJob(id) {
    api('/api/jobs/' + id).then(function (job) {
      S.job = job;
      paintJob();
      if (job.status === 'running') setTimeout(function () { pollJob(id); }, 450);
      else if (job.status === 'done') { S.lastResult = job.result; S.renders = null; paintResult(job.result); toast(t('render.done', { name: job.result.name, len: fmtDur(job.result.length) })); }
      else if (job.status === 'cancelled') { toast(t('render.cancelled')); paintJob(); }
      else if (job.status === 'error') {
        var msg = job.error && job.error.kind === 'down' ? t('render.engine_down') : (job.error && job.error.message) || t('render.failed');
        toast(msg, 'bad', 10000);
        if (job.error && job.error.n && S.editor) S.editor.goLine(job.error.n, true);
      }
    }).catch(function (e) { if (e.network) setTimeout(function () { pollJob(id); }, 1500); else failToast(e); });
  }
  function paintJob() {
    var box = $('#renderCard');
    var rb = $('#renderBtn');
    var job = S.job;
    if (!box || !job) return;
    box.classList.remove('hidden');
    clear(box);
    var running = job.status === 'running';
    if (rb) { rb.disabled = running; }
    var p = job.progress || {};
    var label = t('render.start');
    var frac = 0;
    if (p.stage === 'voice') { label = t('render.voice', { i: p.i, n: p.total, name: p.text }); frac = 0.08 * p.i / p.total; }
    else if (p.stage === 'line') { label = t('render.line', { i: p.i, n: p.total, who: (p.character || p.who) }); frac = 0.08 + 0.88 * (p.i - 1) / p.total; }
    else if (p.stage === 'write') { label = t('render.write'); frac = 0.97; }
    else if (p.stage === 'done') frac = 1;
    if (job.status === 'error') label = (job.error && job.error.kind === 'down') ? t('render.engine_down') : ((job.error && job.error.message) || t('render.failed'));
    if (job.status === 'cancelled') label = t('render.cancelled');
    add(box, h('div.render-card', {},
      h('div.status', {}, running ? icon('loader', 'spin') : icon(job.status === 'error' ? 'warn' : 'info'), h('span.grow', { text: label, title: p.text || '' }),
        running ? btn(t('script.stop'), 'stop', function () { api('/api/jobs/' + job.id + '/cancel', {}).catch(failToast); }, 'sm danger') : null),
      running ? h('div.progress', {}, h('div', { style: { width: Math.round(frac * 100) + '%' } })) : null,
      running && p.text && p.stage === 'line' ? h('div.small.muted.ltr', { text: p.text }) : null));
  }
  function paintResult(res) {
    var box = $('#renderCard');
    var rb = $('#renderBtn');
    if (rb) rb.disabled = false;
    if (!box) return;
    box.classList.remove('hidden');
    clear(box);
    var a = h('audio', { controls: true, src: media('/api/renders/' + encodeURIComponent(res.name) + '/full.wav'), style: { width: '100%' } });
    add(box, [h('h2', {}, icon('check'), h('span', { text: t('render.done', { name: res.name, len: fmtDur(res.length) }) })), a,
      res.credits && res.credits.length ? h('div.credit', { style: { marginTop: '8px' } }, h('code', { text: res.credits.map(function (c) { return c.credit; }).join(', ') }),
        btn('', 'copy', function () { copyText(res.credits.map(function (c) { return c.credit; }).join('\n')); }, 'icon sm ghost', { title: t('c.copy') })) : null,
      res.warnings && res.warnings.length ? h('details', { style: { marginTop: '8px' } }, h('summary', { text: t('render.warnings', { n: res.warnings.length }) }),
        h('div.warnlist', {}, res.warnings.map(function (w) { return h('button', { type: 'button', onclick: function () { if (w.n) S.editor.goLine(w.n, true); } }, h('span.n', { text: w.n ? '#' + w.n : '•' }), h('span', { text: warnText(w) })); }))) : null,
      h('div.btn-row', { style: { marginTop: '10px' } },
        btn(t('render.open'), 'renders', function () { go('renders/' + encodeURIComponent(res.name)); }, 'primary sm'),
        btn(t('renders.folder'), 'folder', function () { api('/api/open', { what: 'render', name: res.name }).catch(failToast); }, 'sm'))]);
  }

  // ==================================================================
  // Cast view
  // ==================================================================
  function viewCast(v) {
    add(v, [h('div.view-head', {}, h('h1', { text: t('nav.cast') })), h('p.lead', { text: t('cast.intro') })]);
    var inScript = h('div.card', {}, h('h2', {}, icon('cast'), h('span', { text: t('cast.in_script') + (S.script.name ? ' — ' + S.script.name : '') })), h('div', { id: 'castTable' }, h('div.muted', { text: t('c.loading') })));
    var defaults = h('div.card', { id: 'castDefault' });
    var browse = h('div.card', {}, h('h2', {}, icon('search'), h('span', { text: t('cast.browse') })), h('div', { id: 'charGrid' }, h('div.muted', { text: t('c.loading') })));
    add(v, [inScript, defaults, browse]);
    Promise.all([loadMoods(), runPlan()]).then(function () {
      if (!document.contains(inScript)) return;
      if (!engineOn()) {
        clear($('#charGrid')).appendChild(h('div.empty', {}, h('img', { src: '/brand/vocana-128.png', alt: '' }), h('div', { text: t('cast.engine_needed') })));
        paintCastTable(null);
        return;
      }
      loadVoices().then(function (voices) { if (!document.contains(inScript)) return; paintCastTable(voices); paintDefault(voices); paintGrid(voices); }).catch(failToast);
    });
  }
  function paintDefault(voices) {
    var box = $('#castDefault');
    if (!box) return;
    clear(box);
    var cur = S.moods && S.moods.speaker;
    var sel = h('select', { style: { maxWidth: '320px' }, onchange: function () { api('/api/moods', { speaker: sel.value }).then(function (m) { S.moods = m; toast(t('settings.saved')); runPlan().then(function () { paintCastTable(voices); }); }).catch(failToast); } },
      voices.characters.map(function (c) { return h('option', { value: c.name, selected: c.name === cur, text: c.name }); }));
    add(box, [h('h2', {}, icon('mic'), h('span', { text: t('cast.default_voice') })), h('div.row', {}, sel, h('span.hint.grow', { text: t('cast.default_voice_hint') }))]);
  }
  function specFromCast(c) {
    return { speaker: c.character, style: c.style || null, pitch: (c.adjust && c.adjust.pitch) || 0, speed: (c.adjust && c.adjust.speed) || 1, volume: (c.adjust && c.adjust.volume) || 1 };
  }
  function applyCast(tag, spec) {
    var text = setCastLine(S.editor ? S.editor.get() : S.script.text, tag, spec);
    S.script.text = text;
    if (S.editor) S.editor.replaceAll(text);
    else { updateDirty(); }
    store('draft', { name: S.script.name, text: text, base: S.script.saved, at: Date.now() });
    return runPlan();
  }
  function paintCastTable(voices) {
    var box = $('#castTable');
    if (!box) return;
    clear(box);
    var p = S.plan;
    if (!p || !p.cast.length) { box.appendChild(h('div.empty', { text: t('cast.none') })); return; }
    var table = h('table.cast-table');
    p.cast.forEach(function (c) {
      var spec = specFromCast(c);
      var charObj = voices && voices.characters.filter(function (x) { return x.name === c.character; })[0];
      var styleSel = h('select', { style: { width: 'auto', maxWidth: '200px' }, disabled: !charObj }, h('option', { value: '', text: t('cast.style_auto') }),
        (charObj ? charObj.styles : []).map(function (s) { return h('option', { value: s.name, selected: s.name === c.style, text: s.name + (s.family ? ' · ' + t('tone.' + s.family) : '') }); }));
      styleSel.addEventListener('change', function () { spec.style = styleSel.value || null; applyCast(c.who, spec); });
      function slider(key, min, max, step, fmt) {
        var out = h('output', { text: fmt(spec[key]) });
        var r = h('input', { type: 'range', min: min, max: max, step: step, value: spec[key], 'aria-label': t('cast.' + key) });
        r.addEventListener('input', function () { out.textContent = fmt(+r.value); });
        r.addEventListener('change', function () { spec[key] = +r.value; applyCast(c.who, spec); });
        return h('td.num', {}, h('div.small.muted', { text: t('cast.' + key) }), h('div.row', {}, r, out));
      }
      var pick = h('button.picker-btn', { type: 'button', onclick: function () {
        pickCharacter(c.character).then(function (name) { if (name) { spec.speaker = name; spec.style = null; applyCast(c.who, spec).then(function () { paintCastTable(voices); }); } });
      }, disabled: !voices }, avatarFor(c.who, c.speaker_uuid, null, 'sm'), h('span', { text: c.character || t('cast.choose') }));
      var origin = h('div.small.muted', { text: t('cast.origin_' + (c.origin || 'default')) });
      if (!c.found && voices) origin = h('div.small', { style: { color: 'var(--bad)' }, text: t('w.cast_unknown_character', { name: c.character, who: c.who }) });
      var hear = btn('', 'play', function () { var l = (p.lines.filter(function (x) { return x.kind === 'line' && x.who === c.who; })[0]); if (l) previewLine(l.n, hear); }, 'icon sm', { title: t('c.hear') });
      table.appendChild(h('tr', {},
        h('td', {}, h('div.tag', { text: c.who, style: { color: tagColor(c.who) } })),
        h('td', {}, pick, origin),
        h('td', {}, h('div.small.muted', { text: t('cast.style') }), styleSel),
        slider('pitch', -6, 6, 0.5, function (x) { return (x > 0 ? '+' : '') + x; }),
        slider('speed', 0.7, 1.3, 0.01, function (x) { return (+x).toFixed(2); }),
        slider('volume', 0.5, 1.6, 0.05, function (x) { return (+x).toFixed(2); }),
        h('td', {}, hear)));
    });
    box.appendChild(table);
    box.appendChild(h('div.row', { style: { marginTop: '6px' } }, h('span.hint.grow', { text: t('cast.apply_hint') }),
      btn(t('cast.make_default'), 'save', function () {
        var cast = {};
        p.cast.forEach(function (c) { if (c.found) { var s = specFromCast(c); cast[c.who] = { speaker: s.speaker }; if (s.style) cast[c.who].style = s.style; ['pitch', 'speed', 'volume'].forEach(function (k) { var neutral = k === 'pitch' ? 0 : 1; if (Math.abs(s[k] - neutral) > 1e-9) cast[c.who][k] = s[k]; }); } });
        api('/api/moods', { cast: cast }).then(function (m) { S.moods = m; toast(t('cast.made_default')); }).catch(failToast);
      }, 'sm')));
    loadAvatars(p);
  }
  function charCard(c, onClick, selected) {
    var ic = h('div.ic');
    var el = h('div.char' + (selected ? '.sel' : ''), { tabindex: '0', onclick: onClick, onkeydown: function (e) { if (e.key === 'Enter') onClick(); } },
      ic, h('b', { text: c.name }), h('small', { text: (c.aliases && c.aliases[0] ? c.aliases[0] + ' · ' : '') + t('cast.styles', { n: c.styles.length }) }));
    var info = S.voiceInfo[c.uuid];
    function setIcon(info) { var s = info && info.styles && info.styles[0]; if (s && s.icon) { clear(ic).appendChild(h('img', { src: s.icon, alt: '', loading: 'lazy' })); } }
    if (info) setIcon(info);
    else ic.dataset.uuid = c.uuid;
    return el;
  }
  function lazyIcons(root) {
    var pending = $$('.ic[data-uuid]', root);
    var i = 0;
    function next() {
      if (i >= pending.length) return;
      var ic = pending[i++];
      var u = ic.dataset.uuid;
      voiceInfo(u).then(function (info) {
        var s = info && info.styles && info.styles[0];
        $$('.ic[data-uuid="' + u + '"]').forEach(function (x) { if (s && s.icon) { clear(x).appendChild(h('img', { src: s.icon, alt: '' })); } delete x.dataset.uuid; });
      }).catch(function () { /* leave the blank square */ }).then(next);
    }
    for (var k = 0; k < 4; k++) next();
  }
  function filterChars(list, q) {
    q = (q || '').trim().toLowerCase();
    if (!q) return list;
    return list.filter(function (c) {
      return c.name.toLowerCase().indexOf(q) >= 0 || (c.aliases || []).some(function (a) { return a.indexOf(q) >= 0; }) ||
        c.styles.some(function (s) { return s.name.indexOf(q) >= 0; });
    });
  }
  function paintGrid(voices) {
    var box = $('#charGrid');
    if (!box) return;
    clear(box);
    var used = {};
    (S.plan ? S.plan.cast : []).forEach(function (c) { used[c.character] = 1; });
    var q = h('input', { type: 'search', placeholder: t('cast.search'), dir: 'auto', style: { maxWidth: '360px' } });
    var grid = h('div.char-grid', { style: { marginTop: '10px' } });
    function paint() {
      clear(grid);
      filterChars(voices.characters, q.value).forEach(function (c) { grid.appendChild(charCard(c, function () { showCharacter(c); }, used[c.name])); });
      lazyIcons(grid);
    }
    q.addEventListener('input', debounce(paint, 120));
    add(box, [h('div.row', {}, q, h('span.muted.small', { text: t('cast.count', { n: voices.characters.length }) })), grid]);
    paint();
  }
  function pickCharacter(current) {
    return loadVoices().then(function (voices) {
      var q = h('input', { type: 'search', placeholder: t('cast.search'), dir: 'auto' });
      var grid = h('div.char-grid', { style: { marginTop: '10px' } });
      var done;
      function paint() {
        clear(grid);
        filterChars(voices.characters, q.value).forEach(function (c) { grid.appendChild(charCard(c, function () { done(c.name); }, c.name === current)); });
        lazyIcons(grid);
      }
      q.addEventListener('input', debounce(paint, 120));
      return dialog({ title: t('cast.choose'), wide: true, noFooter: true, content: function (d) { done = d; paint(); setTimeout(function () { q.focus(); }, 20); return [q, grid]; } });
    });
  }
  function showCharacter(c) {
    voiceInfo(c.uuid).then(function (info) {
      var styles = h('div.styles-list');
      info.styles.forEach(function (s) {
        var hearEn = btn(t('cast.hear_english'), 'play', function () { hearLine('ME: Hello! This is how I sound in English. Nice to meet you!', c.name + '/' + s.name, hearEn); }, 'sm');
        var samples = (s.samples || []).slice(0, 3).map(function (u, i) {
          return btn(String(i + 1), 'play', function () { stopAudio(); audio.src = u; audio.play().catch(function () {}); }, 'sm ghost', { title: t('cast.samples') + ' ' + (i + 1) });
        });
        styles.appendChild(h('div.style-row', {}, s.icon ? h('img', { src: s.icon, alt: '' }) : h('span.avatar.sm', { text: initials(s.name) }),
          h('div.grow', {}, h('b', { text: s.name }), s.family ? h('span.chip', { text: t('tone.' + s.family), style: { marginInlineStart: '6px' } }) : null),
          samples, hearEn));
      });
      var content = h('div.detail', {},
        h('div', {}, info.portrait ? h('img.portrait', { src: info.portrait, alt: c.name }) : null),
        h('div', {},
          info.aliases && info.aliases.length ? h('p.muted', { text: info.aliases.join(' · '), dir: 'ltr' }) : null,
          h('h3', { text: t('cast.credit') }),
          h('div.credit', {}, h('code', { text: info.credit }), btn('', 'copy', function () { copyText(info.credit); }, 'icon sm ghost', { title: t('c.copy') })),
          info.conditions ? h('div.banner.warn', { style: { marginTop: '10px' } }, icon('warn'), h('div.grow', { text: t('cast.conditions') })) : null,
          h('h3', { text: t('cast.terms') }),
          info.policy ? h('div.policy', { text: info.policy, lang: 'ja', dir: 'ltr' }) : h('p.muted', { text: t('cast.no_terms') }),
          h('p.hint', { text: t('cast.terms_note') }),
          info.urls && info.urls.length ? h('div.btn-row', {}, info.urls.map(function (u) { return h('a.btn.sm', { href: u, target: '_blank', rel: 'noopener noreferrer' }, icon('open'), h('span', { text: u.replace(/^https?:\/\//, '').slice(0, 40) })); })) : null,
          h('h3', { text: t('cast.styles', { n: info.styles.length }) }), styles));
      dialog({
        title: c.name, wide: true, content: content,
        buttons: [{ label: t('c.close'), value: null }, { label: t('cast.use_as'), value: 'use', primary: true }]
      }).then(function (v) {
        if (v !== 'use') return;
        var suggest = ((c.aliases && c.aliases[c.aliases.length - 1]) || 'VOICE').toUpperCase().replace(/[^A-Z0-9_]/g, '');
        dialog({ title: t('cast.use_tag_prompt'), prompt: suggest, inputDir: 'ltr', buttons: [{ label: t('c.cancel'), value: null }, { label: t('c.ok'), value: true, primary: true }] }).then(function (tag) {
          tag = (tag || '').trim().toUpperCase().replace(/\s+/g, '_');
          if (!tag) return;
          if (S.view !== 'cast' && S.view !== 'script') go('script');
          applyCast(tag, { speaker: c.name }).then(function () { if (S.view === 'cast') paintCastTable(S.voices); toast('@cast ' + tag + ' = ' + c.name); });
        });
      });
    }).catch(failToast);
  }

  // ==================================================================
  // Renders view
  // ==================================================================
  var player = { name: null, timing: null, peaks: null, raf: 0 };
  function viewRenders(v, arg) {
    add(v, h('div.view-head', {}, h('h1', { text: t('nav.renders') }), h('div.grow'),
      btn(t('renders.folder'), 'folder', function () { api('/api/open', { what: 'renders' }).catch(failToast); }, 'sm')));
    var grid = h('div.renders-grid', {}, h('div.rlist', { id: 'rlist' }), h('div', { id: 'rdetail' }));
    v.appendChild(grid);
    api('/api/renders').then(function (r) {
      S.renders = r.renders;
      var list = $('#rlist');
      if (!list || !document.contains(grid)) return;
      if (!r.renders.length) {
        clear(grid).appendChild(h('div.empty', { style: { gridColumn: '1 / -1' } }, h('img', { src: '/brand/vocana-128.png', alt: '' }), h('div', { text: t('renders.none') })));
        return;
      }
      var sel = decodeURIComponent(arg || '') || r.renders[0].name;
      r.renders.forEach(function (it) {
        list.appendChild(h('div.ritem' + (it.name === sel ? '.sel' : ''), { tabindex: '0', onclick: function () { history.replaceState(null, '', '#renders/' + encodeURIComponent(it.name)); selectRender(it.name); }, 'data-name': it.name },
          h('b', { text: it.name, dir: 'auto' }),
          h('span.small.muted', { text: [it.length ? fmtDur(it.length) : '', it.lines ? t('renders.lines') + ' ' + fmtNum(it.lines) : '', new Date(it.mtime * 1000).toLocaleDateString(S.lang)].filter(Boolean).join(' · ') }),
          it.characters && it.characters.length ? h('span.small', { text: it.characters.join('、') }) : null));
      });
      selectRender(sel);
    }).catch(failToast);
  }
  function selectRender(name) {
    $$('.ritem').forEach(function (x) { x.classList.toggle('sel', x.dataset.name === name); });
    stopAudio();
    cancelAnimationFrame(player.raf);
    player.name = name;
    var box = clear($('#rdetail'));
    box.appendChild(h('div.card', {}, h('div.muted', { text: t('c.loading') })));
    var base = '/api/renders/' + encodeURIComponent(name) + '/';
    Promise.all([api(base), fetch(media(base + 'timing.json')).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; })]).then(function (res) {
      if (player.name !== name) return;
      var files = res[0].files, tj = res[1];
      player.timing = tj;
      clear(box);
      var wave = h('div.wave', {}, h('canvas'), h('div.head', { style: { left: '0' } }));
      var playB = btn('', 'play', function () { if (audio.paused) audio.play(); else audio.pause(); }, 'icon primary', { title: t('player.play') });
      var time = h('span.time.ltr', { text: '0:00.0' });
      var kara = h('div.karaoke', {}, h('span.muted', { text: '♪' }));
      audio.src = media(base + 'full.wav');
      audio.onplay = function () { clear(playB).appendChild(icon('pause')); loop(); };
      audio.onpause = function () { clear(playB).appendChild(icon('play')); };
      audio.onended = audio.onpause;
      wave.addEventListener('click', function (e) {
        var r = wave.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width;
        if (audio.duration) { audio.currentTime = x * audio.duration; draw(); }
      });
      var main = h('div.card', {},
        h('h2', {}, icon('renders'), h('span', { text: name, dir: 'auto' }), tj ? h('span.chip', { text: fmtDur(tj.length) }) : null),
        wave,
        h('div.transport', {}, btn('', 'back', function () { audio.currentTime = Math.max(0, audio.currentTime - 5); }, 'icon', { title: t('player.back') }), playB,
          btn('', 'fwd', function () { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 5); }, 'icon', { title: t('player.fwd') }), time, h('div.grow'),
          btn(t('renders.ai_video'), 'sparkle', function () { copyVideoPrompt(name, tj); }, 'sm ghost')),
        kara);
      var lines = h('div.rlines');
      if (tj) tj.lines.forEach(function (ln, i) {
        lines.appendChild(h('div.rline', { 'data-i': i, onclick: function (e) {
          if (e.target.closest('button')) return;
          audio.currentTime = ln.start; audio.play();
        } }, h('span.t.ltr', { text: clock(ln.start) }), h('span', { text: ln.who, style: { color: tagColor(ln.who), fontWeight: 700, fontSize: '12px' } }),
          h('span', { text: ln.text, dir: 'auto' }),
          btn('', 'play', function () { stopAudio(); var a2 = new Audio(media(base + ln.file)); a2.play(); }, 'icon sm ghost', { title: t('files.line') })));
      });
      var credits = (tj && tj.credits) || [];
      var filesBox = h('div.files');
      files.forEach(function (f) {
        var desc = /^\d+_/.test(f) ? t('files.line') : t('files.' + f);
        if (desc === 'files.' + f) desc = '';
        filesBox.appendChild(h('div.file-row', {}, h('code', { text: f }), h('span.grow', { text: desc }),
          h('a.btn.sm.icon', { href: media(base + encodeURIComponent(f)) + '&download=1', download: f, title: t('c.download'), 'aria-label': t('c.download') }, icon('download'))));
      });
      add(box, [main,
        credits.length ? h('div.card', {}, h('h2', {}, icon('info'), h('span', { text: t('renders.credits') })),
          h('div.credit', {}, h('code', { text: credits.join(', ') }), btn('', 'copy', function () { copyText(credits.join('\n')); }, 'icon sm ghost', { title: t('c.copy') }))) : null,
        tj ? h('div.card', {}, h('h2', {}, icon('script'), h('span', { text: t('renders.lines') })), lines) : null,
        h('div.card', {}, h('h2', {}, icon('download'), h('span', { text: t('renders.files') })), filesBox,
          h('div.btn-row', { style: { marginTop: '10px' } },
            h('a.btn.primary.sm', { href: media(base + 'zip'), download: name + '.zip' }, icon('download'), h('span', { text: t('renders.zip') })),
            btn(t('renders.folder'), 'folder', function () { api('/api/open', { what: 'render', name: name }).catch(failToast); }, 'sm'),
            h('div.grow'),
            btn(t('c.delete'), 'trash', function () {
              confirmBox(t('renders.delete_confirm', { name: name }), t('c.delete'), true).then(function (ok) {
                if (!ok) return;
                stopAudio();
                api(base + 'delete', {}).then(function () { toast(t('renders.deleted')); history.replaceState(null, '', '#renders'); route(); }).catch(failToast);
              });
            }, 'sm danger')))]);
      // waveform
      fetch(media(base + 'full.wav')).then(function (r) { return r.arrayBuffer(); }).then(function (buf) {
        var AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        var ac = new AC();
        return ac.decodeAudioData(buf).then(function (ab) {
          var data = ab.getChannelData(0);
          var n = 600, step = Math.max(1, Math.floor(data.length / n)), peaks = [];
          for (var i = 0; i < n; i++) {
            var m = 0;
            for (var j = i * step; j < (i + 1) * step && j < data.length; j += 4) { var a = Math.abs(data[j]); if (a > m) m = a; }
            peaks.push(m);
          }
          player.peaks = peaks;
          ac.close && ac.close();
          draw();
        });
      }).catch(function () { /* the player still works without a waveform */ });
      function draw() {
        var cv = $('canvas', wave);
        if (!cv) return;
        var w = cv.clientWidth, hgt = cv.clientHeight, dpr = window.devicePixelRatio || 1;
        cv.width = w * dpr; cv.height = hgt * dpr;
        var c = cv.getContext('2d');
        c.scale(dpr, dpr);
        var peaks = player.peaks || [];
        var pos = audio.duration ? audio.currentTime / audio.duration : 0;
        var css = getComputedStyle(document.documentElement);
        var played = css.getPropertyValue('--brand').trim() || '#2f7a4d', rest = css.getPropertyValue('--line-2').trim() || '#ccc';
        var bw = w / (peaks.length || 1);
        for (var i = 0; i < peaks.length; i++) {
          var ph = Math.max(1.5, peaks[i] * (hgt - 10));
          c.fillStyle = (i / peaks.length) <= pos ? played : rest;
          c.fillRect(i * bw, (hgt - ph) / 2, Math.max(1, bw - 1), ph);
        }
        if (tj) {
          c.fillStyle = css.getPropertyValue('--gold').trim() || '#b9923a';
          tj.lines.forEach(function (ln) { if (audio.duration) c.fillRect(ln.start / audio.duration * w, 0, 1, 6); });
        }
        $('.head', wave).style.left = (pos * 100) + '%';
      }
      var lastS = -1, lastW = -1;
      function karaoke() {
        if (!tj) return;
        var tm = audio.currentTime;
        var found = null, li = -1;
        tj.lines.forEach(function (ln, i) { ln.sentences.forEach(function (s) { if (tm >= s.start - 0.02 && tm <= s.end + 0.15) { found = s; li = i; } }); });
        $$('.rline', box).forEach(function (r) { r.classList.toggle('on', +r.dataset.i === li); });
        var sid = found ? tj.lines[li].sentences.indexOf(found) + li * 1000 : -1;
        if (sid !== lastS) {
          lastS = sid; lastW = -1;
          clear(kara);
          if (!found) { kara.appendChild(h('span.muted', { text: '♪' })); return; }
          kara.appendChild(h('span.who', { text: tj.lines[li].who + (tj.lines[li].character ? ' · ' + tj.lines[li].character : '') }));
          var row = h('span');
          if (found.words.length) found.words.forEach(function (w, i) { row.appendChild(h('span.w', { text: w.word, 'data-i': i })); row.appendChild(document.createTextNode(' ')); });
          else row.textContent = found.text;
          kara.appendChild(row);
        }
        if (found) {
          var wi = -1;
          found.words.forEach(function (w, i) { if (tm >= w.start && tm < w.end + 0.04) wi = i; });
          if (wi !== lastW) { lastW = wi; $$('.w', kara).forEach(function (x) { x.classList.toggle('on', +x.dataset.i === wi); }); }
        }
      }
      function loop() {
        time.textContent = clock(audio.currentTime) + ' / ' + clock(audio.duration || (tj && tj.length) || 0);
        draw();
        karaoke();
        if (!audio.paused && player.name === name) player.raf = requestAnimationFrame(loop);
      }
      audio.onseeked = loop;
      audio.onloadedmetadata = function () { draw(); time.textContent = clock(0) + ' / ' + clock(audio.duration); };
      player.draw = draw;
    }).catch(failToast);
  }
  window.addEventListener('resize', debounce(function () { if (S.view === 'renders' && player.draw) player.draw(); }, 100));
  function copyVideoPrompt(name, tj) {
    var base = '/api/renders/' + encodeURIComponent(name) + '/';
    fetch(media(base + 'script.txt')).then(function (r) { return r.ok ? r.text() : ''; }).catch(function () { return ''; }).then(function (script) {
      copyText(t('ai.video', { len: fmtDur(tj ? tj.length : 0), credits: tj && tj.credits ? tj.credits.join(', ') : '', script: script }), t('renders.ai_copied'));
    });
  }

  // ==================================================================
  // Dictionary
  // ==================================================================
  function loadWords() { return api('/api/words').then(function (w) { S.words = w; return w; }); }
  function viewWords(v) {
    add(v, [h('div.view-head', {}, h('h1', { text: t('nav.words') }), h('div.grow'), h('span.chip', { id: 'wcount' }),
      btn('', 'folder', function () { api('/api/open', { what: 'data' }).catch(failToast); }, 'icon sm ghost', { title: t('settings.open_data') })),
      h('p.lead', { text: t('words.intro') })]);
    var two = h('div.two');
    var left = h('div.card');
    var right = h('div', {}, h('div.card', { id: 'wtest' }), h('div.card', { id: 'wreview' }));
    two.appendChild(left);
    two.appendChild(right);
    v.appendChild(two);
    loadWords().then(function () { if (!document.contains(left)) return; paintWords(left); paintWordTest(); paintWordReview(); }).catch(failToast);
  }
  function paintWords(box) {
    clear(box);
    var words = S.words.words;
    var wc = $('#wcount');
    if (wc) wc.textContent = t('words.count', { n: Object.keys(words).length });
    var q = h('input', { type: 'search', placeholder: t('words.search'), dir: 'ltr' });
    var nw = h('input', { type: 'text', placeholder: t('words.word'), dir: 'ltr' });
    var nk = h('input', { type: 'text', placeholder: t('words.kana'), dir: 'ltr' });
    var hearNew = btn('', 'play', function () { if (nw.value.trim()) hearText(nw.value.trim(), hearNew); }, 'icon', { title: t('c.hear') });
    function addWord() {
      var w = nw.value.trim().toLowerCase(), k = nk.value.trim();
      if (!w) { toast(t('words.empty_word'), 'bad'); nw.focus(); return; }
      if (!/[\u3041-\u30fa]/.test(k)) { toast(t('words.invalid_kana'), 'bad'); nk.focus(); return; }
      var next = Object.assign({}, words);
      var existed = next[w] !== undefined;
      next[w] = k;
      saveWords(next).then(function () { nw.value = ''; nk.value = ''; if (existed) toast(t('words.dup', { word: w })); paintWords(box); });
    }
    nk.addEventListener('keydown', function (e) { if (e.key === 'Enter') addWord(); });
    nw.addEventListener('blur', function () {
      if (nw.value.trim() && !nk.value.trim()) api('/api/words/test', { text: nw.value.trim() }).then(function (r) { if (r.words[0] && !nk.value) nk.placeholder = r.words[0].kana; }).catch(function () {});
    });
    var tbody = h('tbody');
    function paint() {
      clear(tbody);
      var term = q.value.trim().toLowerCase();
      Object.keys(words).sort().filter(function (k) { return !term || k.indexOf(term) >= 0 || words[k].indexOf(term) >= 0; }).slice(0, 2000).forEach(function (k) {
        var hearB = btn('', 'play', function () { hearText(k, hearB); }, 'icon sm ghost', { title: t('c.hear') });
        var kanaCell = h('td.kana', { text: words[k], tabindex: '0', title: t('c.edit') });
        function edit() {
          var inp = h('input', { type: 'text', value: words[k], dir: 'ltr' });
          clear(kanaCell).appendChild(inp);
          inp.focus(); inp.select();
          function commit(save) {
            var val = inp.value.trim();
            if (save && val && val !== words[k]) {
              if (!/[\u3041-\u30fa]/.test(val)) { toast(t('words.invalid_kana'), 'bad'); return; }
              var next = Object.assign({}, words); next[k] = val;
              saveWords(next).then(function () { paintWords(box); });
            } else kanaCell.textContent = words[k];
          }
          inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') commit(true); if (e.key === 'Escape') commit(false); });
          inp.addEventListener('blur', function () { commit(true); });
        }
        kanaCell.addEventListener('dblclick', edit);
        kanaCell.addEventListener('keydown', function (e) { if (e.key === 'Enter') edit(); });
        tbody.appendChild(h('tr', {}, h('td.word', { text: k }), kanaCell, h('td', { style: { whiteSpace: 'nowrap', textAlign: 'end' } }, hearB,
          btn('', 'edit', edit, 'icon sm ghost', { title: t('c.edit') }),
          btn('', 'trash', function () {
            confirmBox(t('words.delete_confirm', { word: k }), t('c.delete'), true).then(function (ok) {
              if (!ok) return;
              var next = Object.assign({}, words); delete next[k];
              saveWords(next).then(function () { paintWords(box); });
            });
          }, 'icon sm ghost danger', { title: t('c.delete') }))));
      });
    }
    q.addEventListener('input', debounce(paint, 100));
    add(box, [h('h2', {}, icon('plus'), h('span', { text: t('words.add') })),
      h('div.row', {}, h('div.grow', {}, nw), h('div.grow', {}, nk), hearNew, btn(t('c.add'), 'plus', addWord, 'primary')),
      h('p.hint', { text: t('words.kana_help') }),
      h('div', { style: { height: '8px' } }), q, h('div', { style: { height: '8px' } }),
      h('div.words-wrap', {}, h('table.table', {}, h('thead', {}, h('tr', {}, h('th', { text: t('words.word') }), h('th', { text: t('words.kana') }), h('th'))), tbody))]);
    paint();
  }
  function saveWords(next) {
    return api('/api/words', { words: next }).then(function (r) { S.words = r; toast(t('words.saved')); if (S.editor) runPlan(); return r; }).catch(function (e) { failToast(e); throw e; });
  }
  function paintWordTest() {
    var box = $('#wtest');
    if (!box) return;
    var inp = h('input', { type: 'text', placeholder: t('words.test_ph'), dir: 'ltr', value: store('wtest') || "Hello! I'm testing my new words." });
    var out = h('div', { style: { marginTop: '10px' } });
    var hearB = btn(t('c.hear'), 'play', function () { if (inp.value.trim()) hearText(inp.value.trim(), hearB); }, 'primary');
    function run() {
      store('wtest', inp.value);
      api('/api/words/test', { text: inp.value }).then(function (r) {
        clear(out);
        var tb = h('tbody');
        r.words.forEach(function (w) {
          tb.appendChild(h('tr', {}, h('td.word', { text: w.word }), h('td.kana', { text: w.kana }),
            h('td', {}, h('span.chip.src-' + w.source, { text: t('src.' + w.source) })),
            h('td', {}, w.source !== 'dict' ? btn(t('words.pin'), 'plus', function () { fixWord(w.word.toLowerCase(), w.kana); }, 'sm ghost') : null)));
        });
        out.appendChild(h('table.table', {}, h('thead', {}, h('tr', {}, h('th', { text: t('words.word') }), h('th', { text: t('words.kana') }), h('th', { text: t('words.source') }), h('th'))), tb));
      }).catch(failToast);
    }
    inp.addEventListener('input', debounce(run, 300));
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') hearB.click(); });
    add(clear(box), [h('h2', {}, icon('mic'), h('span', { text: t('words.test') })), h('div.row', {}, h('div.grow', {}, inp), hearB), out]);
    run();
  }
  function paintWordReview() {
    var box = $('#wreview');
    if (!box) return;
    clear(box);
    var rv = (S.plan && S.plan.review) || [];
    if (!rv.length) { box.classList.add('hidden'); return; }
    box.classList.remove('hidden');
    var r = h('div.review');
    rv.slice(0, 120).forEach(function (x) {
      var hb = btn('', 'play', function () { hearText(x.word, hb); }, 'icon sm ghost', { title: t('c.hear') });
      r.appendChild(h('span.rw', {}, h('span.ltr', { text: x.word }), h('span.k', { text: x.kana }), hb, btn(t('script.review_add'), '', function () { fixWord(x.word, x.kana); }, 'sm ghost')));
    });
    add(box, [h('h2', {}, icon('warn'), h('span', { text: t('script.review') + (S.script.name ? ' — ' + S.script.name : '') })), h('p.hint', { text: t('script.review_hint') }), r]);
  }

  // ==================================================================
  // Moods
  // ==================================================================
  var PARAMS = [['pitch', -12, 12, 0.5], ['speed', 0.5, 1.5, 0.01], ['intonation', 0, 2, 0.05], ['volume', 0, 3, 0.05], ['bounce', 0, 4, 0.1],
    ['end_rise', -12, 12, 0.5], ['exclaim_rise', -12, 12, 0.5], ['end_stretch', 0.3, 3, 0.05], ['pauses', 0, 3, 0.05]];
  function loadMoods() { return api('/api/moods').then(function (m) { S.moods = m; return m; }); }
  var saveMoodsSoon = debounce(function () { saveMoodsNow(); }, 500);
  var moodSave = Promise.resolve();
  function saveMoodsNow() {
    moodSave = api('/api/moods', { moods: S.moods.moods }).then(function (m) { S.moods = m; toast(t('moods.saved'), null, 1500); }).catch(failToast);
    return moodSave;
  }
  function viewMoods(v, arg) {
    add(v, [h('div.view-head', {}, h('h1', { text: t('nav.moods') }), h('div.grow'),
      btn(t('moods.new'), 'plus', newMood, 'sm'),
      btn(t('moods.reset_all'), 'refresh', function () {
        confirmBox(t('moods.reset_all_confirm'), t('c.reset'), true).then(function (ok) { if (ok) api('/api/moods/reset', {}).then(function (m) { S.moods = m; route(); }).catch(failToast); });
      }, 'sm danger')), h('p.lead', { text: t('moods.intro') })]);
    var box = h('div');
    v.appendChild(box);
    Promise.all([loadMoods(), engineOn() ? loadVoices().catch(function () { return null; }) : Promise.resolve(null)]).then(function () { if (document.contains(box)) paintMoods(box, decodeURIComponent(arg || '') || 'normal'); }).catch(failToast);
  }
  function newMood() {
    dialog({ title: t('moods.new'), prompt: '', inputDir: 'ltr', content: h('p.hint', { text: t('moods.new_prompt') }), buttons: [{ label: t('c.cancel'), value: null }, { label: t('c.add'), value: true, primary: true }] }).then(function (name) {
      name = (name || '').trim().toLowerCase();
      if (!name) return;
      if (!/^[a-z0-9_\-]{1,30}$/.test(name)) { toast(t('moods.bad_name'), 'bad'); return; }
      if (S.moods.moods[name]) { toast(t('moods.exists'), 'bad'); return; }
      S.moods.moods[name] = { style: 'ノーマル' };
      saveMoodsNow().then(function () { go('moods/' + name); });
    });
  }
  function paintMoods(box, sel) {
    clear(box);
    var moods = S.moods.moods;
    if (!moods[sel]) sel = 'normal';
    var list = h('div.mood-list');
    Object.keys(moods).forEach(function (m) {
      list.appendChild(h('button' + (S.moods.defaults.indexOf(m) < 0 ? '.custom' : ''), { type: 'button', 'aria-pressed': m === sel ? 'true' : 'false', onclick: function () { history.replaceState(null, '', '#moods/' + m); paintMoods(box, m); }, text: m, title: S.moods.defaults.indexOf(m) < 0 ? t('moods.custom') : '' }));
    });
    var mood = moods[sel];
    var normal = moods.normal || {};
    var tones = Array.isArray(mood.tone) ? mood.tone : (mood.tone ? [mood.tone] : []);
    var toneSel = h('select', { style: { maxWidth: '260px' } }, h('option', { value: '', text: t('moods.tone_none') }),
      S.moods.families.map(function (f) { return h('option', { value: f, selected: tones[0] === f, text: t('tone.' + f) + ' (' + f + ')' }); }));
    toneSel.addEventListener('change', function () {
      if (toneSel.value) mood.tone = [toneSel.value].concat(tones.slice(1).filter(function (x) { return x !== toneSel.value; })); else delete mood.tone;
      saveMoodsSoon();
    });
    var styleIn = h('input', { type: 'text', value: mood.style || '', dir: 'auto', placeholder: normal.style || 'ノーマル', style: { maxWidth: '200px' } });
    styleIn.addEventListener('change', function () { if (styleIn.value.trim()) mood.style = styleIn.value.trim(); else delete mood.style; saveMoodsSoon(); });
    var params = h('div');
    PARAMS.forEach(function (p) {
      var key = p[0], set = mood[key] !== undefined;
      var val = set ? mood[key] : (normal[key] !== undefined ? normal[key] : ({ speed: 1, intonation: 1.3, volume: 1, bounce: 0.8, end_stretch: 1, pauses: 0.8 }[key] || 0));
      var range = h('input', { type: 'range', min: p[1], max: p[2], step: p[3], value: val, 'aria-label': t('param.' + key) });
      var num = h('input', { type: 'number', min: p[1], max: p[2], step: p[3], value: val, dir: 'ltr' });
      var row = h('div.param' + (set || sel === 'normal' ? '' : '.unset'), {},
        h('label', { text: t('param.' + key) }), range, num,
        h('div.hint', { text: t('param.' + key + '.h') + (set || sel === 'normal' ? '' : ' · ' + t('moods.inherits')) }));
      function setVal(v) {
        v = Math.min(p[2], Math.max(p[1], +v));
        if (!isFinite(v)) return;
        range.value = v; num.value = v;
        mood[key] = v;
        row.classList.remove('unset');
        saveMoodsSoon();
      }
      range.addEventListener('input', function () { num.value = range.value; });
      range.addEventListener('change', function () { setVal(range.value); });
      num.addEventListener('change', function () { setVal(num.value); });
      params.appendChild(row);
    });
    var testIn = h('input', { type: 'text', value: store('moodtest') || t('moods.test_line'), dir: 'ltr' });
    var chars = (S.voices && S.voices.characters) || [];
    var charSel = h('select', { style: { maxWidth: '220px' } }, chars.map(function (c) { return h('option', { value: c.name, selected: c.name === (store('moodchar') || S.moods.speaker), text: c.name }); }));
    var hearB = btn(t('c.hear'), 'play', function () {
      store('moodtest', testIn.value); store('moodchar', charSel.value);
      moodSave.then(function () { return saveMoodsNow(); }).then(function () { hearLine('ME [' + sel + ']: ' + testIn.value, charSel.value || null, hearB); });
    }, 'primary');
    var isDefault = S.moods.defaults.indexOf(sel) >= 0;
    var card = h('div.card', {},
      h('h2', {}, icon('moods'), h('span.ltr', { text: sel })),
      h('div.row', {}, h('label.field', {}, h('span', { text: t('moods.tone') }), toneSel), h('label.field', {}, h('span', { text: t('moods.style') }), styleIn)),
      h('div', { style: { height: '8px' } }), params,
      h('div.row', { style: { marginTop: '12px' } }, h('label.field.grow', {}, h('span', { text: t('moods.test') }), testIn),
        chars.length ? h('label.field', {}, h('span', { text: t('moods.character') }), charSel) : null, h('div', { style: { alignSelf: 'end' } }, hearB)),
      h('div.btn-row', { style: { marginTop: '12px' } },
        isDefault ? btn(t('moods.reset'), 'refresh', function () { api('/api/moods/reset', { name: sel }).then(function (m) { S.moods = m; paintMoods(box, sel); }).catch(failToast); }, 'sm') : null,
        sel !== 'normal' ? btn(t('moods.delete'), 'trash', function () {
          confirmBox(t('moods.delete_confirm', { name: sel }), t('c.delete'), true).then(function (ok) {
            if (!ok) return;
            delete S.moods.moods[sel];
            saveMoodsNow().then(function () { history.replaceState(null, '', '#moods'); paintMoods(box, 'normal'); });
          });
        }, 'sm danger') : null));
    add(box, [h('div.card', {}, list), card]);
  }

  // ==================================================================
  // Settings
  // ==================================================================
  function viewSettings(v) {
    add(v, h('div.view-head', {}, h('h1', { text: t('nav.settings') })));
    var grid = h('div.settings-grid');
    v.appendChild(grid);
    Promise.all([api('/api/settings'), loadStatus(), loadMoods()]).then(function (r) {
      S.settings = r[0];
      if (!document.contains(grid)) return;
      var st = r[1], s = S.settings, e = st.engine;
      // appearance
      function segBtns(key, opts) {
        var seg = h('div.seg', { role: 'group' });
        opts.forEach(function (o) {
          seg.appendChild(h('button', { type: 'button', 'aria-pressed': s[key] === o[0] ? 'true' : 'false', text: o[1], onclick: function () { var x = {}; x[key] = o[0]; saveSettings(x).then(rebuild); } }));
        });
        return seg;
      }
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('settings'), h('span', { text: t('settings.language') + ' · ' + t('settings.theme') })),
        h('div.label', { text: t('settings.language') }), segBtns('lang', [['auto', t('lang.auto')], ['fa', 'فارسی'], ['en', 'English'], ['ja', '日本語']]),
        h('div', { style: { height: '12px' } }),
        h('div.label', { text: t('settings.theme') }), segBtns('theme', [['auto', t('theme.auto')], ['light', t('theme.light')], ['dark', t('theme.dark')]]),
        h('div', { style: { height: '12px' } }),
        h('label.field', {}, h('span', { text: t('settings.editor_size') }), (function () {
          var r2 = h('input', { type: 'range', min: 12, max: 22, step: 1, value: s.editor_size });
          r2.addEventListener('change', function () { saveSettings({ editor_size: +r2.value }); });
          return r2;
        })())));
      // engine
      var urlIn = h('input', { type: 'url', value: S.moods.engine || e.url, dir: 'ltr' });
      var urlMsg = h('div.hint');
      var testB = btn(t('settings.test'), 'refresh', function () {
        busyBtn(testB, true);
        api('/api/engine/url', { url: urlIn.value }).then(function (es) {
          urlIn.value = es.url;
          urlMsg.textContent = es.version ? t('settings.engine_ok', { v: es.version }) : t('settings.engine_fail');
          urlMsg.style.color = es.version ? 'var(--ok)' : 'var(--bad)';
          return loadStatus();
        }).catch(failToast).then(function () { busyBtn(testB, false); });
      }, 'sm');
      var asSel = h('select', { onchange: function () { saveSettings({ engine_start: asSel.value }); } },
        [['auto', t('settings.as_auto')], ['engine', t('settings.as_engine')], ['app', t('settings.as_app')], ['off', t('settings.as_off')]].map(function (o) { return h('option', { value: o[0], selected: s.engine_start === o[0], text: o[1] }); }));
      var pathIn = h('input', { type: 'text', value: s.voicevox_path || '', dir: 'ltr', placeholder: 'C:\\Users\\…\\VOICEVOX\\VOICEVOX.exe' });
      pathIn.addEventListener('change', function () { saveSettings({ voicevox_path: pathIn.value.trim() }).then(function () { return loadStatus(); }).then(function () { route(); }); });
      var found = (e.found && (e.found.engine || e.found.app));
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('mic'), h('span', { text: t('settings.engine') })),
        h('div.banner.' + (e.version ? 'ok' : 'warn'), {}, icon(e.version ? 'check' : 'warn'), h('div.grow', { text: e.version ? t('settings.engine_ok', { v: e.version }) : t('engine.off') }),
          e.version ? null : btn(t('engine.start'), 'power', function () { startEngine(this); }, 'sm primary')),
        h('label.field', {}, h('span', { text: t('settings.engine_url') }), h('div.row', {}, h('div.grow', {}, urlIn), testB)), urlMsg,
        h('div', { style: { height: '10px' } }),
        h('label.field', {}, h('span', { text: t('settings.autostart') }), asSel),
        h('div', { style: { height: '10px' } }),
        h('label.field', {}, h('span', { text: t('settings.vv_path') }), pathIn),
        h('div.hint', { text: t('settings.vv_path_hint') }),
        h('div.hint.ltr', { text: found ? t('settings.found', { p: found }) : t('settings.found_none'), style: { color: found ? 'var(--ok)' : 'var(--warn)' } })));
      // studio
      function sw(key, label) {
        return h('label.switch', {}, h('input', { type: 'checkbox', checked: s[key], onchange: function () { var x = {}; x[key] = this.checked; saveSettings(x).then(function () { toast(t('settings.saved'), null, 1500); }); } }), h('span', { text: label }));
      }
      var upMsg = h('div.hint');
      var upB = btn(t('settings.check_now'), 'refresh', function () {
        busyBtn(upB, true);
        api('/api/update', {}).then(function () { return new Promise(function (r) { setTimeout(r, 2500); }); }).then(function () { return api('/api/update'); }).then(function (u) {
          upMsg.textContent = u.available ? t('update.available', { v: u.version }) : (u.version ? t('settings.up_to_date') : '');
          return loadStatus();
        }).catch(failToast).then(function () { busyBtn(upB, false); });
      }, 'sm');
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('sparkle'), h('span', { text: t('settings.studio') })),
        h('div', { style: { display: 'grid', gap: '10px' } }, sw('app_window', t('settings.app_window')), h('div.row', {}, sw('check_updates', t('settings.updates')), upB), upMsg,
          h('div.hint.ltr', { text: t('settings.port') + ': ' + location.host }))));
      // files
      var lay = st.layout;
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('folder'), h('span', { text: t('settings.files') })),
        h('p', { text: lay.fallback ? t('settings.mode_fallback') : lay.installed ? t('settings.mode_installed') : t('settings.mode_portable') }),
        h('dl.kv', {}, h('dt', { text: t('install.data') }), h('dd.ltr', { text: lay.data })),
        h('div.btn-row', { style: { marginTop: '10px' } }, btn(t('settings.open_data'), 'folder', function () { api('/api/open', { what: 'data' }).catch(failToast); }, 'sm'),
          btn(t('settings.open_logs'), 'script', function () { api('/api/open', { what: 'logs' }).catch(failToast); }, 'sm')),
        BOOT.windows && !lay.installed ? h('div.banner.info', { style: { marginTop: '12px' } }, icon('install'), h('div.grow', {}, h('b', { text: t('settings.install') }), h('div.small', { text: t('settings.install_hint') })), btn(t('nav.install'), 'install', function () { go('install'); }, 'sm primary')) : null,
        lay.installed ? h('div.btn-row', { style: { marginTop: '12px' } }, btn(t('settings.uninstall'), 'trash', function () {
          confirmBox(t('settings.uninstall_confirm'), t('settings.uninstall'), true).then(function (ok) {
            if (!ok) return;
            api('/api/install/uninstall', {}).then(function () { S.lostToken = true; showLost(); $('#lost h2').textContent = t('settings.uninstalled'); }).catch(failToast);
          });
        }, 'sm danger')) : null));
      // doctor
      var doc = h('div.doctor');
      var docB = btn(t('settings.doctor_run'), 'refresh', function () { runDoctor(doc, docB); }, 'sm');
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('check'), h('span', { text: t('settings.doctor') })), docB, doc));
      // about
      grid.appendChild(h('div.card', {}, h('h2', {}, icon('info'), h('span', { text: t('about.title') })),
        h('div.row', {}, h('img', { src: '/brand/vocana-128.png', alt: '', width: 64, height: 64, style: { borderRadius: '50%' } }),
          h('div', {}, h('b', { text: 'Vocana' }), h('div.small.muted', { text: t('about.version', { v: BOOT.version, d: BOOT.date }) }), h('div.small', { text: t('about.made') }))),
        h('p.small', { text: t('about.voicevox') }),
        h('div.btn-row', {}, h('a.btn.sm', { href: BOOT.homepage, target: '_blank', rel: 'noopener' }, icon('open'), h('span', { text: t('about.homepage') })),
          h('a.btn.sm', { href: '/guide#license', target: '_blank' }, icon('script'), h('span', { text: t('about.license') })),
          h('a.btn.sm', { href: '/guide#notices', target: '_blank' }, icon('script'), h('span', { text: t('about.notices') }))),
        h('div.btn-row', { style: { marginTop: '12px' } }, btn(t('about.quit'), 'power', function () {
          confirmBox(t('about.quit_confirm'), t('about.quit'), true).then(function (ok) {
            if (!ok) return;
            if (S.editor && dirty()) store('draft', { name: S.script.name, text: S.editor.get(), base: S.script.saved, at: Date.now() });
            api('/api/quit', {}).then(function () { S.lostToken = true; showLost(); $('#lost h2').textContent = t('about.quit_done'); $('#lost p').textContent = ''; });
          });
        }, 'sm danger'))));
    }).catch(failToast);
  }
  function runDoctor(box, b) {
    busyBtn(b, true);
    api('/api/doctor').then(function (r) {
      clear(box);
      r.rows.forEach(function (row) {
        var sym = { ok: '✔', warn: '!', fail: '✖' }[row.status];
        box.appendChild(h('div.r', {}, h('b.st-' + row.status, { text: sym }), h('span', { text: I18N.en['doc.' + row.code] ? t('doc.' + row.code) : row.label }), h('span.d.ltr', { text: row.detail })));
      });
    }).catch(failToast).then(function () { busyBtn(b, false); });
  }

  // ==================================================================
  // Install
  // ==================================================================
  function viewInstall(v) {
    var box = h('div.card');
    v.appendChild(box);
    api('/api/install').then(function (info) {
      if (!document.contains(box)) return;
      clear(box);
      var hero = h('div.install-hero', {}, h('img', { src: '/brand/vocana-256.png', alt: '' }), h('div', {}, h('h1', { text: t('install.title'), style: { margin: '0 0 6px', fontSize: '22px' } }), h('p.muted', { text: t('install.intro'), style: { margin: 0 } })));
      box.appendChild(hero);
      if (!info.windows) { box.appendChild(h('div.banner.info', { style: { marginTop: '14px' } }, icon('info'), h('div.grow', { text: t('install.not_windows') }))); return; }
      if (info.installed) { box.appendChild(h('div.banner.ok', { style: { marginTop: '14px' } }, icon('check'), h('div.grow', { text: t('install.already') }))); return; }
      var sm = h('input', { type: 'checkbox', checked: true }), dt = h('input', { type: 'checkbox', checked: true });
      var steps = h('div.steps');
      var goB = btn(t('install.go'), 'install', function () { run(); }, 'primary big');
      add(box, [h('dl.kv', { style: { marginTop: '16px' } }, h('dt', { text: t('install.where') }), h('dd.ltr', { text: info.target }), h('dt', { text: t('install.data') }), h('dd.ltr', { text: info.data })),
        info.existing ? h('div.banner.info', { style: { marginTop: '10px' } }, icon('info'), h('div.grow', { text: t('install.replaces') })) : null,
        h('div', { style: { display: 'grid', gap: '8px', margin: '14px 0' } }, h('label.switch', {}, sm, h('span', { text: t('install.startmenu') })), h('label.switch', {}, dt, h('span', { text: t('install.desktop') }))),
        h('div.row', {}, goB, h('span.hint', { text: t('install.no_admin') })), steps]);
      function run() {
        goB.disabled = true;
        api('/api/install/run', { start_menu: sm.checked, desktop: dt.checked, lang: S.lang }).then(function (job) { poll(job.id); }).catch(function (e) { goB.disabled = false; failToast(e); });
      }
      var order = ['stop', 'copy', 'files', 'shortcuts', 'register', 'done'];
      function paintSteps(stage, ok) {
        clear(steps);
        var idx = order.indexOf(stage);
        order.forEach(function (s, i) {
          steps.appendChild(h('div' + (i < idx || ok ? '.ok' : i === idx ? '.on' : ''), {}, icon(i < idx || ok ? 'check' : i === idx ? 'loader' : 'info', i === idx && !ok ? 'spin' : ''), h('span', { text: t('install.step.' + s) })));
        });
      }
      function poll(id) {
        api('/api/jobs/' + id).then(function (job) {
          paintSteps((job.progress && job.progress.stage) || 'stop', job.status === 'done');
          if (job.status === 'running') return setTimeout(function () { poll(id); }, 400);
          if (job.status === 'error') { goB.disabled = false; toast(job.error.message, 'bad', 12000); return; }
          if (job.status === 'done') {
            var res = job.result;
            add(box, [h('div.banner.ok', { style: { marginTop: '14px' } }, icon('check'), h('div.grow', {}, h('b', { text: t('install.done') }), h('div.small', { text: t('install.portable_note') }))),
              res.shortcut_problem ? h('div.banner.warn', {}, icon('warn'), h('div.grow', { text: t('install.shortcut_problem', { p: res.shortcut_problem }) })) : null,
              btn(t('install.open'), 'open', function () {
                if (S.editor && dirty()) store('draft', { name: S.script.name, text: S.editor.get(), base: S.script.saved, at: Date.now() });
                api('/api/install/launch', { job: id }).then(function () { S.lostToken = true; showLost(); $('#lost h2').textContent = t('install.done'); $('#lost p').textContent = t('install.portable_note'); }).catch(failToast);
              }, 'primary big')]);
          }
        }).catch(failToast);
      }
    }).catch(failToast);
  }

  var VIEWS = { script: viewScript, cast: viewCast, renders: viewRenders, words: viewWords, moods: viewMoods, settings: viewSettings, install: viewInstall };

  // ==================================================================
  // Keyboard, drafts, start-up
  // ==================================================================
  document.addEventListener('keydown', function (e) {
    var mod = e.ctrlKey || e.metaKey;
    if (mod && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      if (S.view === 'script') saveScript($('.script-bar .name') ? $('.script-bar .name').value : '');
    } else if (mod && e.key === 'Enter') {
      if (S.view === 'script' && S.editor) {
        e.preventDefault();
        if (e.shiftKey) doRender();
        else {
          var n = S.editor.line();
          var line = S.plan && S.plan.lines.filter(function (l) { return l.kind === 'line' && l.n === n; })[0];
          if (line) previewLine(n); else if (S.plan) {
            var after = S.plan.lines.filter(function (l) { return l.kind === 'line' && l.n >= n; })[0];
            if (after) previewLine(after.n);
          }
        }
      }
    } else if (e.key === '?' && !/INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || '')) {
      showKeys();
    } else if (e.key === 'Escape') {
      stopAudio();
    }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty() && !S.lostToken) {
      store('draft', { name: S.script.name, text: S.editor.get(), base: S.script.saved, at: Date.now() });
      e.preventDefault();
      e.returnValue = '';
    }
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) heartbeat(); });
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    if (mq.addEventListener) mq.addEventListener('change', function () { if (S.theme === 'auto') { applyTheme(); if (S.editor) S.editor.repaint(); } });
  }

  function restoreOrOpen() {
    var draft = store('draft');
    var want = S.pendingScript || BOOT.script;
    var last = (S.settings && S.settings.last_script) || '';
    var pick = Promise.resolve();
    if (want) {
      pick = openScriptByName(want);
    } else if (last) {
      pick = api('/api/scripts/' + encodeURIComponent(last)).then(function (r) { setScript(r.name, r.text, { mtime: r.mtime }); }).catch(function () { return openFirst(); });
    } else {
      pick = openFirst();
    }
    return pick.then(function () {
      if (draft && draft.text && draft.text !== S.script.saved && (draft.name || '') === (S.script.name || '') && Date.now() - draft.at < 14 * 864e5) {
        S.script.text = draft.text;
        if (S.editor && S.view === 'script') { S.editor.set(draft.text); updateDirty(); runPlan(); }
        toast(t('c.unsaved') + ' · ' + (draft.name || t('c.untitled')));
      }
    });
  }
  function openFirst() {
    return api('/api/scripts').then(function (r) {
      var first = r.scripts.filter(function (s) { return s.name === 'Sample'; })[0] || r.scripts[0];
      if (first) return api('/api/scripts/' + encodeURIComponent(first.name)).then(function (x) { setScript(x.name, x.text, { mtime: x.mtime }); });
    });
  }

  function start() {
    S.showKana = store('kana') !== false;
    applyLang();
    applyTheme();
    loadStatus().catch(function () { return null; }).then(function () {
      buildShell();
      if (!location.hash && BOOT.page) location.hash = '#' + BOOT.page;
      var hash = decodeURIComponent((location.hash || '').slice(1));
      if (hash.indexOf('script=') === 0) S.pendingScript = hash.slice(7);
      return loadMoods().catch(function () { return null; });
    }).then(function () {
      // The script first, then the page: Cast and Dictionary read it too.
      return restoreOrOpen().catch(function () { return null; });
    }).then(function () {
      route();
    }).then(function () {
      S.started = true;
      if (engineOn()) loadVoices().catch(function () { return null; });
      setTimeout(pollStatus, 2500);
      heartbeat();
      setInterval(heartbeat, 15000);
    });
  }
  start();
})();
