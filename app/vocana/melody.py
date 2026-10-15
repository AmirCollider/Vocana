"""
Shaping a sentence's melody, and knowing when each sound happens.

VOICEVOX predicts a pitch and a length for every mora. This file edits that
prediction before synthesis:

  1. Nothing is whispered. Japanese text processing devoices the final vowel
     of many words ("...desu" -> "...des"), which in English sounds like a
     tired breath at the end of every sentence. Every vowel gets a voice.
  2. Each accent phrase is moved a little up or down - the bounce people
     have when they talk with energy.
  3. *Emphasised* words go up and get longer; stretched words ("Pleeease")
     hold their long vowel.
  4. The end of a sentence rises, falls or stretches by its punctuation and
     its mood.
  5. The mood's own pitch offset, in semitones.

Excitement comes from melody, not from speed, so the words stay clear.
These numbers are the ones the original renders were tuned with; the
regression test compares the result sample by sample.
"""

import math
import random

import numpy as np

LN2_12 = math.log(2) / 12.0          # one semitone in VOICEVOX's log-pitch units
MIN_BG = 0.09                        # seconds: the shortest b or g that is still heard
FRAME = 256 / 24000                  # the engine times every sound in whole frames of this
UPSPEAK = 0.15                       # seconds the engine adds to the end of a question


def stretch_target(ms, accent=None):
    """Which syllable to hold when a word or a line is drawn out: the long
    vowel if there is one ("pu-RII-zu", "no-OU"), else the accented
    syllable, else the last real vowel. Never a final 'zu'/'to' - in
    katakana English those are only the tail of a consonant."""
    real = [m for m in ms if m['vowel'] not in ('N', 'cl', 'pau', 'sil')]
    if not real:
        return None
    for k in range(len(ms) - 1, 0, -1):
        a, b = ms[k - 1]['vowel'].lower(), ms[k]['vowel'].lower()
        if ms[k].get('consonant') is None and ms[k] in real and (
                a == b or (a == 'o' and b == 'u') or (a == 'e' and b == 'i')):
            return ms[k]
    if accent and 1 <= accent <= len(ms) and ms[accent - 1] in real:
        return ms[accent - 1]
    # the last vowel that is really a vowel: skip trailing consonant+u/o
    k = len(real) - 1
    while k > 0 and real[k].get('consonant') and real[k]['vowel'].lower() in ('u', 'o'):
        k -= 1
    return real[k]


def all_moras(aps):
    for ap in aps:
        for m in ap['moras']:
            yield m


def shape(aps, spans, mood, seg, seed, accent_of=None):
    """Edit VOICEVOX's predicted pitches and lengths in place.
    `accent_of(word)` gives the accent position used to pick the syllable a
    stretched word holds (the loanword rule, for English words)."""
    flat = list(all_moras(aps))
    if not flat:
        return
    rng = random.Random(seed)

    # 1. Nothing whispered: give every devoiced vowel a voice and a pitch,
    #    and every b and g enough time to be heard.
    voiced = [m['pitch'] for m in flat if m['pitch'] > 0]
    mean = float(np.mean(voiced)) if voiced else 5.8
    for i, m in enumerate(flat):
        if m['vowel'] in ('A', 'I', 'U', 'E', 'O'):
            m['vowel'] = m['vowel'].lower()
        if m['pitch'] <= 0 and m['vowel'] not in ('cl', 'pau', 'sil'):
            nb = [x['pitch'] for x in flat[max(0, i - 1):i + 2] if x['pitch'] > 0]
            m['pitch'] = float(np.mean(nb)) if nb else mean
        # Inside a phrase the engine makes b and g so short they melt into the
        # vowels: "the golden" comes out "the olden", "rainbow" "rainmow".
        # (Not d: held this long, a d is heard as a t - "paddle" -> "battle".)
        if m.get('consonant') in ('b', 'g') and (m.get('consonant_length') or 0) < MIN_BG:
            m['consonant_length'] = MIN_BG

    # 2. A lively melody: each accent phrase a little higher or lower than
    #    the last, the way people bounce through a sentence.
    bounce = float(mood.get('bounce', 0.8))
    for k, ap in enumerate(aps):
        off = (rng.uniform(-1, 1) * bounce + (0.6 * bounce if k == 0 else 0)) * LN2_12
        for m in ap['moras']:
            if m['pitch'] > 0:
                m['pitch'] += off

    # 3. Emphasised (*word*) and stretched (Pleeease) words.
    for w, a, b in spans:
        ms = flat[a:b]
        if w.get('emph'):
            for m in ms:
                if m['pitch'] > 0:
                    m['pitch'] += 2.5 * LN2_12
                m['vowel_length'] *= 1.2
        if w.get('stretch'):
            m = stretch_target(ms, accent_of(w) if accent_of else None)
            if m is not None:
                m['vowel_length'] *= 2.6
                if m['pitch'] > 0:
                    m['pitch'] += 1.0 * LN2_12
        if w.get('stutter'):
            for m in ms:
                m['vowel_length'] *= 0.6

    # 4. The end of the sentence: rise, stretch or fall.
    end_rise = float(mood.get('end_rise', 0.0))
    stretch_end = float(mood.get('end_stretch', 1.0))
    if seg['tilde']:
        end_rise += 2.5
        stretch_end *= 1.7
    if seg['heart']:
        end_rise += 1.5
        stretch_end *= 1.3
    if seg['exclaim']:
        end_rise += float(mood.get('exclaim_rise', 1.5))
    if seg['trail']:
        end_rise -= 2.0
        stretch_end *= 1.4
    tail = [m for m in flat if m['vowel'] not in ('cl',)][-2:]
    if tail:
        steps = [0.5, 1.0] if len(tail) == 2 else [1.0]
        for m, s in zip(tail, steps):
            if m['pitch'] > 0:
                m['pitch'] += end_rise * s * LN2_12
        last_word = max(spans, key=lambda x: x[2]) if spans else None
        hold = stretch_target(flat[last_word[1]:last_word[2]]) if last_word else stretch_target(flat[-4:])
        if hold is not None:
            hold['vowel_length'] *= stretch_end

    # 5. Whole-sentence pitch offset of the mood, in semitones.
    st = float(mood.get('pitch', 0.0))
    if st:
        for m in flat:
            if m['pitch'] > 0:
                m['pitch'] += st * LN2_12


def mora_times(aps, q):
    """Where each mora starts and ends in the engine's output, in seconds,
    and how long the output is. The engine divides every sound by the speed
    and rounds it to whole frames; a question gets one more sound at its end."""
    speed = float(q.get('speedScale', 1.0))

    def frames(sec):
        return int(np.round(sec / speed / FRAME))

    t = frames(q.get('prePhonemeLength', 0.0))
    out = []
    for ap in aps:
        for m in ap['moras']:
            start = t
            t += frames(m.get('consonant_length') or 0.0) + frames(m['vowel_length'])
            out.append([start, t])
        if ap.get('is_interrogative') and ap['moras']:
            t += frames(UPSPEAK)
            out[-1][1] = t
        if ap.get('pause_mora'):
            pause = q.get('pauseLength')
            pause = ap['pause_mora']['vowel_length'] if pause is None else pause
            t += frames(pause * float(q.get('pauseLengthScale', 1.0)))
    t += frames(q.get('postPhonemeLength', 0.0))
    return [(a * FRAME, b * FRAME) for a, b in out], t * FRAME
