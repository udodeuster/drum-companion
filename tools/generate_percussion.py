"""Synthesise the percussion one-shots that the CC0 drum pack does not contain.

Run `python tools/generate_percussion.py` to regenerate the WAV files in
drum_companion/assets/drums. The output is original work dedicated to CC0-1.0.
"""

from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "drum_companion" / "assets" / "drums"
rng = np.random.default_rng(7)


def t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * RATE)) / RATE


def noise(n: int) -> np.ndarray:
    return rng.uniform(-1.0, 1.0, n)


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    spectrum[freqs < cutoff] = 0
    return np.fft.irfft(spectrum, len(x))


def bandpass(x: np.ndarray, low: float, high: float) -> np.ndarray:
    spectrum = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    spectrum[(freqs < low) | (freqs > high)] = 0
    return np.fft.irfft(spectrum, len(x))


def rimshot() -> np.ndarray:
    x = t(0.12)
    tone = np.sin(2 * np.pi * 1700 * x) * np.exp(-x * 70) + 0.7 * np.sin(2 * np.pi * 480 * x) * np.exp(-x * 45)
    click = bandpass(noise(len(x)), 2500, 9000) * np.exp(-x * 160)
    return tone + 0.8 * click


def clap() -> np.ndarray:
    x = t(0.3)
    out = np.zeros(len(x))
    for delay in (0.0, 0.011, 0.022, 0.034):
        start = int(delay * RATE)
        burst = np.exp(-(x[: len(x) - start]) * 220)
        out[start:] += bandpass(noise(len(x) - start), 900, 5000) * burst
    out += bandpass(noise(len(x)), 900, 4500) * np.exp(-x * 28) * 0.7
    return out


def ride() -> np.ndarray:
    x = t(1.2)
    partials = [0, 3, 7, 11, 17, 23]
    metal = sum(np.sin(2 * np.pi * (3200 + 410 * p) * x + p) for p in partials) / len(partials)
    wash = highpass(noise(len(x)), 5000)
    ping = np.sin(2 * np.pi * 5200 * x) * np.exp(-x * 25)
    return (metal * 0.5 + wash * 0.45) * np.exp(-x * 4.5) + 0.5 * ping


def shaker() -> np.ndarray:
    x = t(0.12)
    envelope = np.minimum(x / 0.012, 1.0) * np.exp(-x * 38)
    return bandpass(noise(len(x)), 5500, 12000) * envelope


def cowbell() -> np.ndarray:
    x = t(0.5)
    square = lambda f: np.sign(np.sin(2 * np.pi * f * x))
    body = bandpass(0.5 * square(560) + 0.5 * square(845), 400, 3500)
    return body * (0.7 * np.exp(-x * 9) + 0.3 * np.exp(-x * 40))


def save(name: str, audio: np.ndarray) -> None:
    peak = float(np.max(np.abs(audio)))
    audio = (audio / peak * 0.9).astype(np.float32)
    fade = min(64, len(audio) // 4)
    audio[-fade:] *= np.linspace(1.0, 0.0, fade, dtype=np.float32)
    sf.write(OUT / f"{name}.wav", audio, RATE, subtype="PCM_16")


if __name__ == "__main__":
    for name, fn in {
        "rimshot": rimshot,
        "clap": clap,
        "ride": ride,
        "shaker": shaker,
        "cowbell": cowbell,
    }.items():
        save(name, fn())
        print("wrote", name)
