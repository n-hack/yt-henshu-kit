#!/usr/bin/env python3
# 見本の「声の立ち上がり ↔ 画面の変化 ↔ 効果音」のずれを 30fps（1コマ単位）で測る
#   声の立ち上がり＝声（vocals.wav）が0.15秒以上の無音のあとに鳴り始めた瞬間（文字起こしの癖が入らない）
#   画面の変化＝30fps のコマの差が閾値を超えた最初のコマ
#   効果音＝声を抜いた音（bg.wav）の立ち上がり（kata の onsets・over_local_db>=8）
#   python3 build/timing_measure.py [本数] → kata/timing_30fps.json
import json, glob, os, sys, subprocess, wave, numpy as np
from concurrent.futures import ProcessPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30000 / 1001
def rd(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, w.getframerate()
def voice_onsets(y, sr, gap=0.15):
    hop = int(sr * 0.005); win = int(sr * 0.02)
    e = np.array([np.sqrt(np.mean(y[i:i + win] ** 2)) for i in range(0, len(y) - win, hop)]); db = 20 * np.log10(e + 1e-9)
    thr = np.percentile(db, 95) - 30; v = db > thr; out = []; g = int(gap / 0.005)
    for j in range(g, len(v)):
        if v[j] and not v[j - g:j].any() and v[j:j + 8].mean() > 0.7: out.append(j * 0.005)
    return np.array(out)
def vis_changes(v, t0, t1, w=192, h=108):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', v, '-t', str(t1 - t0), '-vf', 'scale=%d:%d' % (w, h), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    ev = []
    for i in range(1, len(d)):
        if d[i] > 0.5 and d[i - 1] <= 0.5: ev.append(t0 + (i + 1) / FPS)
    return np.array(ev)
def one(f):
    d = json.load(open(f)); vp = glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % d['id']))[0]; res = {'id': d['id'], 'ch': d['channel'], 'tv': [], 'sv': []}
    for w in d['windows']:
        wd = os.path.join(os.path.dirname(f), 'w' + w['name'])
        if not os.path.exists(os.path.join(wd, 'vocals.wav')): continue
        y, sr = rd(os.path.join(wd, 'vocals.wav')); on = voice_onsets(y, sr) + w['t0']
        ch = vis_changes(vp, w['t0'], w['t1'])
        if len(ch) == 0: continue
        for o in on:
            k = np.argmin(abs(ch - o)); dd = ch[k] - o
            if abs(dd) <= 0.5: res['tv'].append(round(float(dd), 3))
        for o in w['onsets']:
            if o['over_local_db'] < 8: continue
            k = np.argmin(abs(ch - o['t'])); dd = o['t'] - ch[k]
            if abs(dd) <= 0.3: res['sv'].append(round(float(dd), 3))
    return res
if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    fs = sorted(glob.glob(os.path.join(BASE, 'kata/raw/*/data.json')))
    fs = fs[::max(1, len(fs) // n)][:n]
    with ProcessPoolExecutor(10) as ex: R = list(ex.map(one, fs))
    tv = np.array([x for r in R for x in r['tv']]); sv = np.array([x for r in R for x in r['sv']])
    def st(a): return {'n': int(len(a)), 'median': round(float(np.median(a)), 3), 'p25': round(float(np.percentile(a, 25)), 3), 'p75': round(float(np.percentile(a, 75)), 3),
                       'within_2f(±0.067)': round(float(np.mean(abs(a - np.median(a)) <= 0.067)), 2)}
    out = {'videos': len(R), '画面の変化−声の立ち上がり（秒）': st(tv), '効果音−画面の変化（秒）': st(sv),
           'hist_tv': np.histogram(tv, bins=np.arange(-0.5, 0.51, 1 / 30))[0].tolist(), 'hist_sv': np.histogram(sv, bins=np.arange(-0.3, 0.31, 1 / 30))[0].tolist()}
    json.dump(out, open(os.path.join(BASE, 'kata/timing_30fps.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
