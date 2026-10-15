<p align="center"><img src="app/brand/vocana-256.png" width="180" alt="Vocana"></p>

<h1 align="center">Vocana</h1>

<p align="center"><b>Plain English, any VOICEVOX voice.</b><br>
انگلیسی ساده بنویسید، با هر صدای VOICEVOX بشنوید.<br>
英語を書くだけで、どの VOICEVOX ボイスでも。</p>

<p align="center"><a href="https://amircollider.com/vocana">amircollider.com/vocana</a> · Free · Windows · macOS · Linux · فارسی · English · 日本語</p>

---

Write a script in normal English. Vocana writes every word in katakana the way a Japanese voice can say it, shapes the melody for each mood, and renders the voice, captions and word-by-word timing for your video — with **every** VOICEVOX character in one script.

- **A studio in your browser** — an editor that colours your script, hear any line before rendering, a player whose captions follow every word. In Persian, English and Japanese.
- **The whole VOICEVOX cast** — `@cast METAN = 四国めたん` and each character reads its lines; a mood picks each character's own style (喜び, わーい, あまあま…).
- **Credits done right** — every render writes `credits.txt` with the exact credit line each character's terms ask for, and the studio marks characters with extra conditions.
- **Clear English** — a dictionary for the words that matter, an English-to-katakana model for the rest, loanword accents, nothing whispered.
- **Ready for video and AI** — `full.wav`, a file per line, SRT/WebVTT captions per line and per sentence, and `timing.json` with every word's time.
- **Nothing to install on Windows** — Python is inside the folder. `Setup.bat` installs it for your user (Start menu, uninstall) if you want.

## Start

1. Install [VOICEVOX](https://voicevox.hiroshiba.jp/) (Vocana starts it for you).
2. Windows: open **`Vocana.bat`** — or **`Setup.bat`** to install. macOS / Linux: run **`start.sh`** (Python 3.10+).
3. Write, press ▶, **Render**. Files go to `renders/<script name>/`.

The full guide, in three languages, is **[`Guide.html`](Guide.html)** — open it from the folder.

<div dir="rtl">

## شروع

۱. [VOICEVOX](https://voicevox.hiroshiba.jp/) را نصب کنید (Vocana خودش بازش می‌کند).
۲. ویندوز: **`Vocana.bat`** را باز کنید — یا **`Setup.bat`** را برای نصب. مک و لینوکس: **`start.sh`** را اجرا کنید (پایتون ۳٫۱۰ به بالا).
۳. بنویسید، ▶ را بزنید، **ساختن صدا**. فایل‌ها در `renders/<نام اسکریپت>/` ساخته می‌شوند.

راهنمای کامل به سه زبان در فایل **`Guide.html`** همین پوشه است.

</div>

## はじめかた

1. [VOICEVOX](https://voicevox.hiroshiba.jp/) をインストール (Vocana が自動で起動します)。
2. Windows: **`Vocana.bat`** を開く (インストールするなら **`Setup.bat`**)。macOS / Linux: **`start.sh`** を実行 (Python 3.10 以降)。
3. 書いて ▶ で試聴し、**書き出し**。ファイルは `renders/<スクリプト名>/` にできます。

3 か国語の詳しいガイドは、このフォルダーの **`Guide.html`** です。

## Script format

```
gap = 0.4
@cast ME = ずんだもん
@cast METAN = 四国めたん / ツンツン, pitch +1
ME [excited]: Hello! I'm AmirCollider!
METAN [smug]: Hmph. I make *amazing* games too~
(pause 1.0)
ME [pleading]: Pleeease? W-Wait... ♡
```

Scripts, `words.json` and `moods.json` written for VoxTalk (the earlier name of this project) work unchanged and sound exactly the same.

## Credit

Every video that uses a VOICEVOX voice must credit it — `VOICEVOX:ずんだもん`, `VOICEVOX:四国めたん`… Vocana writes the exact lines into `credits.txt`. Follow each character's terms, shown on the studio's Cast page.

## For developers

```
python vocana.py ensure-deps            # numpy + e2k into app/lib
python -m unittest discover -s tests    # regression tests need VOICEVOX 0.25.2 on :50021
python tools/build_runtime.py           # the Windows runtime for the release zip
python tools/build_guide.py             # Guide.html
python tools/make_release.py            # both zips
```

## License

Free for personal and commercial use; © 2026 AmirCollider — see [`LICENSE.txt`](LICENSE.txt) and [`THIRD-PARTY-NOTICES.txt`](THIRD-PARTY-NOTICES.txt). Vocana is an independent tool for VOICEVOX and is not affiliated with the VOICEVOX project.
