#!/usr/bin/env python3
"""soundgen.py — generate a game's sound effects and a music loop from code.

Standard library only (wave, struct, math). Used by the Android branch of the pipeline so
a game ships with original audio and no licensed files: every effect is a formula, every
game gets its own tones by changing the parameters below.

    python3 tools/soundgen.py out/            # writes click.wav hop.wav bank.wav crash.wav rev.wav music.wav

Output: 16-bit mono PCM, 22050 Hz — small enough for SoundPool, plenty for arcade effects.
"""
import math
import os
import random
import struct
import sys
import wave

RATE = 22050


def write(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(v * 32767))
        w.writeframes(bytes(frames))


def env(i, n, attack=0.005, release=0.15):
    """Linear attack, exponential release; i/n in samples."""
    t = i / RATE
    a = min(1.0, t / attack) if attack > 0 else 1.0
    rem = (n - i) / RATE
    r = 1.0 if rem > release else rem / release
    return a * r


def tone(freq, dur, wave_fn=math.sin, gain=0.6, slide=0.0, attack=0.005, release=0.12):
    n = int(RATE * dur)
    out = []
    phase = 0.0
    for i in range(n):
        f = freq * (1.0 + slide * i / n)
        phase += 2 * math.pi * f / RATE
        out.append(gain * wave_fn(phase) * env(i, n, attack, release))
    return out


def square(x):
    return 1.0 if math.sin(x) >= 0 else -1.0


def noise(dur, gain=0.5, lowpass=0.3, release=0.25):
    n = int(RATE * dur)
    out, last = [], 0.0
    for i in range(n):
        last += lowpass * (random.uniform(-1, 1) - last)
        out.append(gain * last * env(i, n, 0.001, release))
    return out


def mix(*layers):
    n = max(len(l) for l in layers)
    return [sum(l[i] if i < len(l) else 0.0 for l in layers) for i in range(n)]


def concat(*parts):
    out = []
    for p in parts:
        out += p
    return out


# ---------------------------------------------------------------- effects
def click():
    return tone(1800, 0.04, square, gain=0.25, release=0.03)


def hop():
    return tone(320, 0.18, math.sin, gain=0.55, slide=1.4, release=0.1)


def bank():
    # three ascending notes = "you kept it"
    return concat(tone(660, 0.09, gain=0.5), tone(880, 0.09, gain=0.5), tone(1320, 0.18, gain=0.55, release=0.15))


def crash():
    thud = tone(90, 0.35, gain=0.7, slide=-0.6, release=0.3)
    debris = noise(0.4, gain=0.45, lowpass=0.5)
    return mix(thud, debris)


def rev():
    # engine spin-up: rising square with a wobble
    n = int(RATE * 0.9)
    out, phase = [], 0.0
    for i in range(n):
        f = 60 + 220 * (i / n) ** 1.6
        f *= 1 + 0.03 * math.sin(2 * math.pi * 9 * i / RATE)
        phase += 2 * math.pi * f / RATE
        out.append(0.4 * square(phase) * env(i, n, 0.05, 0.2))
    return out


def music(seconds=10.0, bpm=112, root=220.0):
    """A cheerful workshop loop: bass on beats, a pentatonic melody, soft hats."""
    random.seed(7)
    beat = 60.0 / bpm
    n = int(RATE * seconds)
    out = [0.0] * n
    penta = [0, 2, 4, 7, 9, 12]

    def add(start, samples):
        s0 = int(start * RATE)
        for i, v in enumerate(samples):
            if s0 + i < n:
                out[s0 + i] += v

    t = 0.0
    step = 0
    while t < seconds:
        if step % 2 == 0:
            add(t, tone(root / 2, beat * 0.9, gain=0.28, release=0.2))
        add(t, tone(6000, 0.03, square, gain=0.05, release=0.02))
        if step % 4 in (0, 1, 3):
            note = root * 2 ** (random.choice(penta) / 12)
            add(t + beat * 0.5, tone(note, beat * 0.6, gain=0.22, release=0.1))
        t += beat
        step += 1
    return [max(-1.0, min(1.0, v)) for v in out]


def main(argv):
    out_dir = argv[0] if argv else "out"
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in (("click", click), ("hop", hop), ("bank", bank), ("crash", crash), ("rev", rev), ("music", music)):
        path = os.path.join(out_dir, f"{name}.wav")
        write(path, fn())
        print(f"{name:6s} {os.path.getsize(path):8d} bytes  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
