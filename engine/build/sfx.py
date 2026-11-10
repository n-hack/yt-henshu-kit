#!/usr/bin/env python3
# 効果音（自前で合成・素材の権利の心配なし）と BGM を、部品が出る時刻に合わせて重ねる。
# 元の音声に効果音・BGMがすでに入っている動画（今回の試作）では使わない。ナレーションだけの音声で作るときに使う。
import numpy as np, wave, subprocess, os
SR = 48000
def _env(n, a=0.005, d=0.12):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / d)
def pop():
    n = int(SR * 0.12); t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 500
    return 0.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.04)
def don():
    n = int(SR * 0.45); t = np.arange(n) / SR
    low = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 12)) * t) * _env(n, 0.002, 0.18)
    noise = np.random.RandomState(1).randn(n) * _env(n, 0.001, 0.03) * 0.3
    return 0.8 * low + noise
def whoosh():
    n = int(SR * 0.35); rs = np.random.RandomState(2); x = rs.randn(n)
    sp = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR); sp *= np.exp(-((fr - 2500) / 1800) ** 2)
    y = np.fft.irfft(sp, n); y /= np.abs(y).max()
    t = np.arange(n) / n; return 0.35 * y * np.sin(np.pi * t) ** 2
def tick():
    n = int(SR * 0.05); return 0.25 * np.sin(2 * np.pi * 1800 * np.arange(n) / SR) * _env(n, 0.001, 0.012)
KINDS = {'pop': pop, 'don': don, 'whoosh': whoosh, 'tick': tick}

def events_from_scenes(scenes, t0, t1):
    """部品の出る時刻と種類 → 鳴らす音。文字のワイプは小さな tick、吹き出し・絵は pop、太い見出しは don、暗転は whoosh"""
    import anim
    ev = []
    for s in scenes:
        for e in s.elems:
            if not (t0 <= e.ts < t1): continue
            if isinstance(e, anim.Dim): k = 'whoosh'
            elif e.anim == 'zoom': k = 'don'
            elif e.anim in ('pop', 'bounce', 'left'): k = 'pop'
            elif e.anim == 'wipe': k = 'tick'
            else: continue
            ev.append((e.ts - t0, k))
    ev.sort(); out = []
    for t, k in ev:  # 0.12秒以内に重なるものは1つに
        if out and t - out[-1][0] < 0.12: continue
        out.append((t, k))
    return out

def render_track(events, dur, path, gain=0.5):
    y = np.zeros(int(SR * (dur + 1)), np.float32)
    for t, k in events:
        s = KINDS[k](); i = int(t * SR); y[i:i + len(s)] += s[:len(y) - i] * gain
    y = np.clip(y, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
    return path
