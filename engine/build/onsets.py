#!/usr/bin/env python3
# 音の立ち上がり（効果音の候補）を拾う: onsets.py <wav> <out.json>
# 2〜10kHz の帯域の強さの急な増え（spectral flux）を 10ms 刻みで見て、山を拾う
import sys, json, wave, numpy as np
w = wave.open(sys.argv[1]); sr = w.getframerate(); n = w.getnframes(); ch = w.getnchannels()
a = np.frombuffer(w.readframes(n), np.int16).reshape(-1, ch).astype(np.float32).mean(1) / 32768
hop = sr // 100; win = 2048
fr = np.fft.rfftfreq(win, 1 / sr); band = (fr > 2000) & (fr < 10000)
hann = np.hanning(win)
E = []
for i in range(0, len(a) - win, hop):
    E.append(np.log1p(np.abs(np.fft.rfft(a[i:i + win] * hann))[band] * 50))
E = np.array(E)
flux = np.maximum(E[1:] - E[:-1], 0).sum(1)
flux = np.concatenate([[0], flux])
med = np.array([np.median(flux[max(0, i - 100):i + 100]) for i in range(len(flux))])
sc = flux / (med + 1e-6)
pk = []
for i in range(1, len(sc) - 1):
    if sc[i] > 4 and sc[i] >= sc[i - 1] and sc[i] >= sc[i + 1] and (not pk or i * 0.01 - pk[-1]['t'] > 0.15):
        pk.append({'t': round(i * 0.01 + win / 2 / sr, 3), 'score': round(float(sc[i]), 1)})
json.dump(pk, open(sys.argv[2], 'w'))
print(len(pk), 'onsets; strong(>8):', sum(p['score'] > 8 for p in pk))
