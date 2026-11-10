#!/usr/bin/env python3
# 声＋効果音＋BGM を混ぜる（作業AI 2026-10-15）
#   効果音は素材サイト（効果音ラボ・商用可・表記不要）の音。種類ごとに 1 つの音を決めて使う（見本と同じく音を揃える）。
#   決まり（kata/KATA.md）:
#     - 効果音は要所だけ。1分に 8〜12 回が目安。ポンは前の効果音から 1.6 秒以上あいたときだけ鳴らす
#     - 効果音の大きさは声より少し小さく（ピークで声のピーク −4〜−10dB）
#     - BGM は告知の区間だけ。声の大きさ（RMS）より約 19dB 下。入りはドンと同時、出は 1.2 秒でフェード
import os, subprocess, numpy as np, wave
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
SR = 48000
LIB = os.path.join(BASE, 'assets', 'sfxlib')
SOUNDS = {  # 種類: (ファイル, 大きさdB（ピーク基準）, 説明)
    'pop':      ('button__decision28.mp3', -11, 'ポン：文字・札が出る'),
    'check':    ('button__decision28.mp3', -10, 'カチッ：チェックが付く'),
    'pop2':     ('anime__pa1.mp3', -10, 'パッ：結論の座布団が出る'),
    'tick':     ('button__cursor1.mp3', -18, 'コッ：小さな部品（基本は鳴らさない）'),
    'don':      ('anime__don-1.mp3', -7, 'ドン：言い切り・数字・限定'),
    'don_big':  ('anime__doon1.mp3', -4, 'ドーン：告知への切り替え'),
    'kira':     ('anime__kira1.mp3', -12, 'キラーン：実績・約束・金の文字'),
    'jan':      ('anime__jajean1.mp3', -8, 'ジャジャーン：企画名'),
    'jan_s':    ('anime__jean1.mp3', -10, 'ジャン：締め'),
    'whoosh':   ('anime__hyun1.mp3', -12, 'ヒュン：場面が大きく変わる'),
    'whoosh_s': ('anime__hyun1.mp3', -17, 'ヒュン（小）：同じ地で文が替わる'),
    'batsu':    ('anime__incorrect1.mp3', -14, 'ブッブー：×が付く'),
    'zun':      ('anime__shock1.mp3', -11, 'ガーン：伸びない・失敗'),
    'alert':    ('button__warning1.mp3', -12, '注意：公開の決まり'),
    'cta':      ('button__decision1.mp3', -9, 'ピコン：参加の呼びかけ'),
    'up':       ('anime__shine1.mp3', -14, 'シャラン：伸びる・上がる'),
}
RANK = {'don_big': 0, 'jan': 0, 'jan_s': 0, 'whoosh': 0, 'cta': 0, 'alert': 0, 'don': 1, 'kira': 1, 'zun': 1, 'check': 1,
        'batsu': 2, 'pop2': 2, 'up': 3, 'whoosh_s': 3, 'pop': 4, 'tick': 9}
MINGAP = [0.12, 1.2, 1.8, 2.6, 4.0]   # 位ごとに「近くにもう音があれば鳴らさない」秒

def dec(p, ss=None, t=None):
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', str(ss)] if ss is not None else []) + ['-i', p] + (['-t', str(t)] if t else []) + ['-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).copy()

def select(events, sparse=()):
    """鳴らす効果音を選ぶ：大事な音（位が小さい）から順に置き、近くにもう音があれば後の位は鳴らさない（見本は要所だけ鳴らす）
    sparse=[(始め, 終わり, 倍率)]：その区間は位2以下の間隔を倍率ぶん広げる（本編は効果音を減らす＝見本の本編は 1分に4〜6回）"""
    acc = []
    for t, k in sorted(events, key=lambda e: (RANK.get(e[1], 9), e[0])):
        r = RANK.get(k, 9)
        if r >= len(MINGAP): continue
        g = MINGAP[r] * max([f for a, b, f in sparse if a <= t < b and r >= 2] + [1.0])
        if any(abs(t - u) < g for u, _ in acc): continue
        acc.append((t, k))
    return sorted(acc)

def mix(voice, events, bgm, t0, t1, out, sparse=()):
    v = dec(voice, t0, t1 - t0); n = int((t1 - t0) * SR) + SR; y = np.zeros(n, np.float32); y[:len(v)] += v
    vpk = np.percentile(np.abs(v), 99.9); vrms = np.sqrt(np.mean(v[np.abs(v) > 0.01] ** 2))
    ev = select([(t - t0, k) for t, k in events if t0 <= t < t1], [(a - t0, b - t0, f) for a, b, f in sparse])
    cache = {}
    for t, k in ev:
        f, g, _ = SOUNDS[k]
        if f not in cache: cache[f] = dec(os.path.join(LIB, f))
        s = cache[f]; s = s / (np.abs(s).max() + 1e-9) * vpk * 10 ** (g / 20)
        i = int(t * SR); m = min(len(s), n - i)
        if m > 0: y[i:i + m] += s[:m]
    for a, b, f, off, gdb in bgm:
        a, b = max(a, t0) - t0, min(b, t1) - t0
        if b <= a: continue
        m = dec(os.path.join(BASE, f), off, b - a + 0.1)[:int((b - a) * SR)]
        mr = np.sqrt(np.mean(m ** 2)) + 1e-9; m = m / mr * vrms * 10 ** (gdb / 20)
        fi, fo = int(0.25 * SR), int(1.2 * SR)
        env = np.ones(len(m), np.float32); env[:fi] = np.linspace(0, 1, fi); env[-fo:] = np.linspace(1, 0, fo)
        i = int(a * SR); y[i:i + len(m)] += m * env
    y = y[:int((t1 - t0) * SR)]
    pk = np.abs(y).max()
    if pk > 0.98: y = y / pk * 0.98
    tmp = out + '.raw.wav'
    with wave.open(tmp, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    # YouTube の基準（-14 LUFS 付近）に揃えて 2ch に
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', str(SR), '-ac', '2', out], check=True)
    os.remove(tmp)
    print('効果音', len(ev), '回（%.1f 回/分）' % (len(ev) / ((t1 - t0) / 60)), ' BGM 区間', len(bgm))
    return out
