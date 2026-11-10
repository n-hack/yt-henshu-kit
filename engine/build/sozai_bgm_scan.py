#!/usr/bin/env python3
# 見本のBGMを探す：声を抜いた音（bg.wav）を 4秒の塊に切り、効果音の立ち上がりが無く BGM が鳴っている塊だけ「音の色（クロマ）＋音色」で特徴にする
# → sozai/work/bgm_blocks.npz。同じ曲は複数の動画で同じ特徴になる
import json, glob, os, wave, numpy as np
from concurrent.futures import ProcessPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100; BL = 4.0
def rd(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
def feats(y):
    n = 4096; hop = 2048; fr = np.fft.rfftfreq(n, 1 / SR)
    fs = np.lib.stride_tricks.sliding_window_view(y, n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fs, axis=1)) ** 2
    ok = (fr > 80) & (fr < 4000); midi = 69 + 12 * np.log2(fr[ok] / 440); pc = np.round(midi).astype(int) % 12
    C = np.stack([S[:, ok][:, pc == k].sum(1) for k in range(12)], 1); C = C / (C.sum(1, keepdims=True) + 1e-12)
    edges = np.geomspace(60, 16000, 17)
    B = np.stack([S[:, (fr >= a) & (fr < b)].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1); B = np.log10(B + 1e-12)
    return np.concatenate([C.mean(0) * 4, (B.mean(0) - B.mean()) / 4, [np.std(np.diff(np.log10(S.sum(1) + 1e-12)))]])
def one(f):
    d = json.load(open(f)); out = []
    for w in d['windows']:
        wd = os.path.join(os.path.dirname(f), 'w' + w['name'])
        if not os.path.exists(os.path.join(wd, 'bg.wav')): continue
        bg = rd(os.path.join(wd, 'bg.wav')); vo = rd(os.path.join(wd, 'vocals.wav'))
        ons = [o['t'] - w['t0'] for o in w['onsets'] if o['over_local_db'] >= 6]
        fl = w['bgm']['bg_floor_db']
        for k in range(int((len(bg) / SR) // BL)):
            a = k * BL; b = a + BL; y = bg[int(a * SR):int(b * SR)]
            lv = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9)
            if lv < -45: continue          # BGM が聞こえない
            n_on = sum(a - 0.3 <= t < b for t in ons)
            v = 20 * np.log10(np.sqrt(np.mean(vo[int(a * SR):int(b * SR)] ** 2)) + 1e-9)
            out.append(dict(vid=d['id'], ch=d['channel'], win=w['name'], a=round(a, 1), t=round(w['t0'] + a, 1), lv=round(float(lv), 1), on=n_on, voice=round(float(v), 1),
                            vmb=w['bgm']['voice_minus_bg_db'], f=feats(y).tolist()))
    return out
if __name__ == '__main__':
    fs = sorted(glob.glob(os.path.join(BASE, 'kata/raw/*/data.json'))); allb = []
    with ProcessPoolExecutor(12) as ex:
        for r in ex.map(one, fs): allb += r
    F = np.array([b.pop('f') for b in allb], np.float32)
    np.savez_compressed(os.path.join(BASE, 'sozai/work/bgm_blocks.npz'), f=F, meta=np.array(json.dumps(allb, ensure_ascii=False)))
    print(len(allb), '塊')
