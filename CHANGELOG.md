# Changelog

## 1.0.0 — 2026-10-15

VoxTalk becomes **Vocana**.

- A studio in the browser (Persian, English, Japanese): script editor with highlighting, a live list of lines with their katakana, ▶ to hear any line, render progress, a player with word-by-word captions, cast, dictionary and mood editors, settings.
- Every VOICEVOX character in one script: `@cast TAG = character / style, pitch, speed, volume, intonation`; a tag that is a character's name needs no cast; a default cast in `moods.json`.
- Moods ask for a tone (happy, sweet, tsun, angry, whisper…); each character uses its own style of that tone. Six new moods: angry, serious, calm, narrator, surprised, scared.
- `credits.txt` in every render, from each character's own terms; characters with extra conditions are marked in the studio.
- New outputs: `captions.vtt`, `sentences.vtt`, `script.txt`; character, style and line number in `timing.json`; line files left from a longer earlier render are removed.
- Windows: embedded Python 3.13 (no install), `Setup.bat` per-user install with Start menu and Apps entry, VOICEVOX started (hidden) when it is closed, a single running studio per data folder, quits when its window has been closed for a few minutes.
- Robustness: no proxy for the engine (VPNs and system proxies broke it), retries when the engine drops a connection, a word the engine refuses is read a simpler way instead of stopping the render, Notepad encodings (BOM, ANSI, UTF-16) and broken JSON reported with line and column, values clamped to what the engine accepts, a file locked by a video editor is named.
- A pronunciation dictionary of more than 1,400 words: the most common English words (every form of the common verbs, numbers, days, pronouns…) now come out in their standard katakana instead of the model's guess (everyone エブリワン, says セズ, speak スピーク).
- The update check keeps only https links from the version document.
- `sad` is low, slow and soft instead of trembling: it no longer borrows a crying style (Zundamon's なみだめ wobbles on every vowel); a character with a calm sad style (かなしい, 悲しみ…) uses it — the new `sorrow` tone. `defeated` is low and flat instead of crying. Crying stays available as the `teary` tone.
- `shy` is シャイ, not シー (and spy, pie, sly, satisfy, notify, ally, magpie).
- Text: `Mr.`, `e.g.`, `2.5`, `50%`, `$5`, `1st`, `mp3`, web addresses, full-width and accented letters; Japanese sentences go to the engine's own reader; text in scripts VOICEVOX cannot read is reported.
- `vocana check` (problems without rendering), `vocana doctor`, `vocana say --interactive`; drag several files onto `render_script.bat`.
- Unchanged for VoxTalk scripts: 503 sentences give identical kana and the sample renders byte-identical audio (tests/test_regression.py).
