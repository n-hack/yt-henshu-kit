#!/usr/bin/env python3
# 見本の動画を同じ式で測って「質の基準」kijun.json を作る（区間＝冒頭90秒・真ん中60秒・最後45秒、冒頭30秒も別に）
#   .venv/bin/python build/kijun_make.py [本数]
import json, glob, os, sys, wave, numpy as np
from concurrent.futures import ProcessPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(BASE, 'build'))
import hensyu_metrics as HM
def rd(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, w.getframerate()
def one(f):
    d = json.load(open(f)); vp = glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % d['id']))[0]; out = []
    for w in d['windows']:
        wd = os.path.join(os.path.dirname(f), 'w' + w['name'])
        if not os.path.exists(os.path.join(wd, 'vocals.wav')): continue
        y, sr = rd(os.path.join(wd, 'vocals.wav'))
        sfx = [o['t'] for o in w['onsets'] if o['over_local_db'] >= 8]
        m = HM.window_metrics(vp, w['t0'], w['t1'], y, sr, w['t0'], sfx); m['win'] = w['name']; m['id'] = d['id']; m['ch'] = d['channel']; out.append(m)
        if w['name'] == 'hook':
            m30 = HM.window_metrics(vp, w['t0'], w['t0'] + 30, y, sr, w['t0'], sfx); m30['win'] = 'hook30'; m30['id'] = d['id']; m30['ch'] = d['channel']; out.append(m30)
    return out
def q(a, ps=(10, 25, 50, 75, 90)): a = np.array(a); return {('p%d' % p): round(float(np.percentile(a, p)), 3) for p in ps} if len(a) else {}
if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    fs = sorted(glob.glob(os.path.join(BASE, 'kata/raw/*/data.json'))); fs = fs[::max(1, len(fs) // n)][:n]
    with ProcessPoolExecutor(10) as ex: R = [m for r in ex.map(one, fs) for m in r]
    json.dump(R, open(os.path.join(BASE, 'kata/kijun_raw.json'), 'w'), ensure_ascii=False)
    K = {'_説明': '見本（委託の編集者さん）の動画 %d 本を同じ式（build/hensyu_metrics.py）で測った分布。区間ごと。check.py はこの値と許すずれ幅で合否を決める' % len(fs), 'by_win': {}}
    for win in ('hook30', 'hook', 'mid', 'end'):
        ms = [m for m in R if m['win'] == win]
        tv = [x for m in ms for x in m.get('telop_offsets', [])]; sv = [x for m in ms for x in m.get('sfx_offsets', [])]; pz = [x for m in ms for x in m.get('pauses', [])]
        K['by_win'][win] = {'n': len(ms), 'changes_pm': q([m['changes_pm'] for m in ms]), 'longest_static': q([m['longest_static'] for m in ms]),
                            'motion_share': q([m['motion_share'] for m in ms]), 'sfx_pm': q([m['sfx_pm'] for m in ms]),
                            'telop_offset': q(tv), 'sfx_offset': q(sv), 'pause_len': q(pz), 'pauses_pm': q([len(m['pauses']) / m['dur'] * 60 for m in ms])}
    json.dump(K, open(os.path.join(BASE, 'kata/kijun_measured.json'), 'w'), ensure_ascii=False, indent=1); print(json.dumps(K, ensure_ascii=False, indent=1))
