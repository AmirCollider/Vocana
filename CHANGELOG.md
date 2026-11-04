# Changelog

## 1.0.2 — 2026-11-04

The dictionary learns 1,198 words, a word + 's is said right, and a whisper is a whisper again.

- **1,198 new words** (3,247 in all), each one a word the English-to-katakana model read wrong. First the script that was reported: undo アンドゥー (was ウンド, "oondo"), redo リドゥー (レド, "red-o"), undoing アンドゥーイング (アンドゥー — the -ing was lost), undid, undone, redid, redone — and the words around them: ctrl コントロール (クトル), hotkey ホットキー (ホッティー), paste ペースト (ペース), retry リトライ (リトリー), reboot リブート (リブー), rewind, uploads, scripts, git ギット (ジット), github ギットハブ (ジチューブ), json ジェイソン (ジョン, "John"), linux リナックス (リヌックス).
- Words that came out as other words: tokyo トーキョー (トコーヨー), sunshine サンシャイン (サンシン), sacred セイクリッド (サッカー, "soccer"), weakened ウィークンド (ウィークエンド, "weekend"), laughter ラフター (ローター), sweater スウェター (スイーター, "sweeter"), bathing ベイジング (バッシング, "bashing"), hm フーン (ミーム, "meme" — and so did every drawn-out "hmmm").
- Chat, stream and game words: lol, brb, btw, idk, tbh, afk, ggs, np, nvm, irl, omw, hp, npc, op, buffed, nerfed, giveaway, shoutout, montage, sponsored; the sounds characters make: woohoo, oof, psst, pfft, ew, duh, tsk, meow, woof, achoo, whoosh, tada, zzz; Japanese in English letters: gomen, gomenasai, sumimasen, daijoubu, yamete, oyasumi, isekai, kakkoii, oniichan, oneesan.
- Common words and names: david デイビッド (ダビード), england イングランド (エングランド), mary メアリー, steve スティーブ, peter ピーター, therefore ゼアフォー (サーフフォー), cities シティーズ (サイティーズ), greater グレーター (グリーター), ancient エインシェント (アンシエント), approximately, determined, significant, obvious, vacation, alien, aliens.
- **A word + 's is the word the dictionary knows, then its s.** The model was given "zundamons" and said ツンダモンズ — "tsundamon's", in the shipped sample itself; now ズンダモンズ. everyone's エブリワンズ (was エバリオン), today's トゥデイズ (トデース), cat's キャッツ, God's ゴッズ, boss's ボスィズ.
- **Drawn-out words keep their own double letters**: "Goood" is good (it was "god"), "Coool" cool ("col"), "Sleeepy" sleepy; "Pleeease" and "sooo" are read as before. A word written in words.json exactly as typed is read as written: "Zzz" is ズズズ, not the letter Z.
- **A hyphenated word in words.json is read whole.** Such an entry was never used, and "bye-bye" was read as a stutter ("b-… bye"); it is バイバイ now. "W-Wait" is still a stutter and "well-known" still two words.
- **`[whisper]` and `[asmr]` keep the engine's own whisper.** A whispering style (ささやき, ヒソヒソ, 囁き…) has no pitch on any syllable, and Vocana gave every syllable a made-up one — 330 Hz, a falsetto under a man's whisper. The melody is left alone for such a sentence; lengths still follow the mood.
- Tests for each of these (tests/test_core.py). The VoxTalk regression test names its one deliberate difference, Zundamon's: lines 1–7 of the VoxTalk sample are still byte-identical, and 499 of the 503 sentences give identical kana.

## 1.0.1 — 2026-11-01

The dictionary learns 617 words, and from now on every update reaches your own dictionary too.

- **617 new words** (2,049 in all), each one a word the English-to-katakana model read wrong. Most are the `shy` kind — a *y*, *i* or *igh* said like "eye" that the model read as "ee": shy シャイ (was シー), skies スカイズ (スキーズ), spies スパイズ (スピーズ), define ディファイン (デフィン), imply インプライ (インプリー), specify スペシファイ (スペシフィー), quietly クワイエットリー (クイエット), lion ライオン (リオン), diet ダイエット (ディート), python パイソン (ピソン), wifi ワイファイ (ウィーフィー), and the -ies / -ied / -ying forms of the -fy verbs. Others: exciting エキサイティング (was エキサイト — the Moods sample's "This is so exciting!" said "excite"), thousands サウザンズ (スーザンド), thoughts ソーツ (スーツ, "suits"), heroes ヒーローズ (ヘローズ), leather レザー (レーザー, "laser"), television テレビジョン (テレビー), receipt レシート (リセット), debt デット (デブ), comb コーム (コンブ), disappointed ディサポインテッド.
- Japanese words written in English letters are read as Japanese: kawaii カワイイ, desu デス, sugoi スゴイ, sensei センセイ, konnichiwa コンニチワ, itadakimasu イタダキマス, tsundere ツンデレ… — and the VOICEVOX characters' names typed in English (Kasukabe, Shikoku, Kurono Takehiro, Kyushu Sora, Tohoku…), and words videos use (livestream, thumbnail, vtubers, xbox, chatgpt, minecraft, iphone, emoji).
- **Updates reach your dictionary.** `words.json` is yours and Vocana never overwrites it — which also kept every new version's words away from it. Now each version lists the words it added (`app/vocana/defaults/new-words.json`), and its first start adds them to your file once: never over a word you already have, and a word you delete stays deleted. `"_dictionary"` in the file names the version whose words are in. A dictionary made by 1.0.0 or by VoxTalk gets the new words and nothing else.
- `sad` is low, slow and soft instead of trembling: it no longer borrows a crying style (Zundamon's なみだめ wobbles on every vowel); a character with a calm sad style (かなしい, 悲しみ…) uses it — the new `sorrow` tone. `defeated` is low and flat instead of crying. Crying stays available as the `teary` tone. `scared` is nervous instead of trembling: it no longer borrows なみだめ either, and its pitch is lower, so it is clear and no longer shrill; a character with a scared style of its own (びくびく, おどおど…) still uses it. (These reached the 1.0.0 download after it was first published; 1.0.1 brings them to every copy.)
- Every new reading is checked to be whole VOICEVOX kana, and the update of an old dictionary is tested (tests/test_core.py). The guide's dictionary section says how updates reach your words.

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
- Text: `Mr.`, `e.g.`, `2.5`, `50%`, `$5`, `1st`, `mp3`, web addresses, full-width and accented letters; Japanese sentences go to the engine's own reader; text in scripts VOICEVOX cannot read is reported.
- `vocana check` (problems without rendering), `vocana doctor`, `vocana say --interactive`; drag several files onto `render_script.bat`.
- Unchanged for VoxTalk scripts: 503 sentences give identical kana and the sample renders byte-identical audio (tests/test_regression.py).
