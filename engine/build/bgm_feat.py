#!/usr/bin/env python3
# BGM の性格（速さ・明るさ・音の厚み・打楽器の強さ）を数字にして、見本の BGM に近い曲を選ぶ。
#   python3 build/bgm_feat.py <見本.wav> <開始> <終わり> 候補.mp3 ...
import sys, subprocess, numpy as np
SR = 22050
def dec(p, ss=None, t=None):
    cmd = ['ffmpeg', '-v', 'error'] + (['-ss', str(ss)] if ss is not None else []) + ['-i', p] + (['-t', str(t)] if t else []) + ['-ac', '1', '-ar', str(SR), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)
def feat(a):
    n = 2048; hop = 512; fr = np.fft.rfftfreq(n, 1 / SR)
    fr_ = np.lib.stride_tricks.sliding_window_view(a, n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fr_, axis=1))
    edges = np.geomspace(40, 10000, 13); B = np.array([S[:, (fr >= edges[i]) & (fr < edges[i + 1])].sum(1) for i in range(12)]).T
    prof = np.log10(B.mean(0) + 1e-9); prof -= prof.mean()
    flux = np.maximum(np.diff(np.log1p(S), axis=0), 0).sum(1); f = flux - flux.mean()
    ac = np.correlate(f, f, 'full')[len(f) - 1:]; lo, hi = int(0.25 * SR / hop), int(1.2 * SR / hop)
    lag = lo + int(np.argmax(ac[lo:hi])); bpm = 60 / (lag * hop / SR); perc = float(ac[lag] / ac[0])
    cen = float((S * fr).sum() / S.sum()); rms = np.sqrt((a[:len(a) // 1024 * 1024].reshape(-1, 1024) ** 2).mean(1))
    return dict(bpm=round(bpm, 1), perc=round(perc, 3), cen=int(cen), dyn=round(float(np.std(20 * np.log10(rms + 1e-6))), 2), prof=prof)
ref = dec(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]) - float(sys.argv[2])); R = feat(ref)
print('REF', {k: v for k, v in R.items() if k != 'prof'})
out = []
for p in sys.argv[4:]:
    a = dec(p); F = feat(a[:SR * 90])
    bpmd = min(abs(np.log2(F['bpm'] / R['bpm'])), abs(np.log2(F['bpm'] * 2 / R['bpm'])), abs(np.log2(F['bpm'] / 2 / R['bpm'])))
    d = np.linalg.norm(F['prof'] - R['prof']) + 3 * bpmd + abs(F['perc'] - R['perc']) * 3 + abs(np.log2(F['cen'] / R['cen']))
    out.append((d, p, F))
for d, p, F in sorted(out, key=lambda x: x[0]):
    print('%.2f' % d, p.split('/')[-1], {k: v for k, v in F.items() if k != 'prof'})
