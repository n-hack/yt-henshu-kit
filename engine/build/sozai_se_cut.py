#!/usr/bin/env python3
# 見本（委託の編集者さんの動画）の効果音を切り出す：声を抜いた音（kata/raw/<id>/w<窓>/bg.wav）から、画面の変化と同時の立ち上がりを切り、
# 「直前が静か（BGMに埋もれていない）」「その間 声が小さい（vocals.wav）」ものだけ残す → sozai/work/se_cand.npz（波形・特徴・出どころ）
import json, glob, os, wave, numpy as np
from concurrent.futures import ProcessPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 44100; PRE = 0.03; LEN = 2.0
def rd(p):
    w = wave.open(p); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768; return x, w.getframerate()
def db(x): return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))
def mel_emb(y, sr=SR):
    # 0〜0.8秒の対数パワー（32帯×16コマ）＝音の形
    win = 1024; hop = int(0.05 * sr); fr = np.fft.rfftfreq(win, 1 / sr)
    edges = np.geomspace(60, 16000, 33)
    seg = y[:int(0.8 * sr) + win]; seg = np.pad(seg, (0, max(0, int(0.8 * sr) + win - len(seg))))
    fs = np.lib.stride_tricks.sliding_window_view(seg, win)[::hop][:16] * np.hanning(win)
    S = np.abs(np.fft.rfft(fs, axis=1)) ** 2
    M = np.stack([S[:, (fr >= a) & (fr < b)].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    M = 10 * np.log10(M + 1e-10); M = M - M.max(); M = np.maximum(M, -60) / 60 + 1
    return M.astype(np.float32).ravel()
def one(f):
    d = json.load(open(f)); vid = d['id']; out = []
    for w in d['windows']:
        wd = os.path.join(os.path.dirname(f), 'w' + w['name'])
        if not os.path.exists(os.path.join(wd, 'bg.wav')): continue
        bg, sr = rd(os.path.join(wd, 'bg.wav')); vo, _ = rd(os.path.join(wd, 'vocals.wav'))
        ons = sorted(w['onsets'], key=lambda o: o['t'])
        for k, o in enumerate(ons):
            if o['over_local_db'] < 8 or not o.get('near_change') or o.get('on_beat'): continue
            t = o['t'] - w['t0']; i0 = int((t - PRE) * sr)
            if i0 < int(0.3 * sr): continue
            nxt = [p['t'] - w['t0'] for p in ons[k + 1:] if p['over_local_db'] >= 6]
            L = min(LEN, (nxt[0] - t) - 0.02 if nxt else LEN)
            if L < 0.15: continue
            y = bg[i0:i0 + int((L + PRE) * sr)]
            if len(y) < int(0.15 * sr): continue
            pre = bg[i0 - int(0.25 * sr):i0]
            pk = float(20 * np.log10(np.abs(y[:int(0.15 * sr)]).max() + 1e-9))
            pre_db = db(pre); body = db(y[:int(0.3 * sr)])
            # 後ろの床（BGM）の大きさ：最後の0.15秒
            tail_db = db(y[-int(0.15 * sr):]) if len(y) > int(0.4 * sr) else pre_db
            v_db = db(vo[i0:i0 + len(y)])
            out.append(dict(vid=vid, ch=d['channel'], win=w['name'], t=o['t'], L=round(L, 2), pk=round(pk, 1), pre=round(pre_db, 1), body=round(body, 1),
                            tail=round(tail_db, 1), voice=round(v_db, 1), guess=o.get('guess'), near=o.get('near_change'), cen=o['centroid_hz'], low=o['low_ratio'],
                            emb=mel_emb(y).tolist(), wav=(y * 32767).astype(np.int16).tobytes().hex()))
    return out
if __name__ == '__main__':
    fs = sorted(glob.glob(os.path.join(BASE, 'kata/raw/*/data.json')))
    allc = []
    with ProcessPoolExecutor(12) as ex:
        for r in ex.map(one, fs): allc += r
    meta = [{k: v for k, v in c.items() if k not in ('emb', 'wav')} for c in allc]
    np.savez_compressed(os.path.join(BASE, 'sozai/work/se_cand.npz'), emb=np.array([c['emb'] for c in allc], np.float32),
                        wav=np.array([c['wav'] for c in allc], dtype=object), meta=np.array(json.dumps(meta, ensure_ascii=False)))
    print(len(allc))
