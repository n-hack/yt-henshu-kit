#!/usr/bin/env python3
# 切り出した効果音の候補を「同じ音」ごとにまとめる（音の形の近さ）。何本の動画で使われているかを数え、
# 各まとまりで一番きれいな1つ（直前が静か・声なし・大きい）を依頼主に選ぶ → sozai/work/se_clusters.json
import json, os, numpy as np, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/se_cand.npz'), allow_pickle=True)
E = Z['emb']; M = json.loads(str(Z['meta']))
snr = np.array([m['pk'] - m['pre'] for m in M]); voice = np.array([m['voice'] for m in M]); pk = np.array([m['pk'] for m in M])
ok = (snr >= 14) & (pk > -40)
print('候補', len(M), '使える', ok.sum(), '声なし(-40dB以下)', (ok & (voice < -40)).sum())
X = E - E.mean(1, keepdims=True); X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
TH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.90
qual = snr + (voice < -40) * 10 + np.minimum(pk + 20, 0)
order = [i for i in np.argsort(-qual) if ok[i]]
cent = []; mem = []
for i in order:
    if cent:
        s = np.array(cent) @ X[i]; j = int(np.argmax(s))
        if s[j] >= TH: mem[j].append(int(i)); continue
    cent.append(X[i].copy()); mem.append([int(i)])
cl = []
for c, m in zip(cent, mem):
    vids = sorted({M[i]['vid'] for i in m}); chs = sorted({M[i]['ch'] for i in m})
    if len(vids) < 3: continue
    best = m[0]
    cl.append({'n': len(m), 'videos': len(vids), 'channels': chs, 'best': best, 'members': m[:400],
               'guess': max(set(M[i]['guess'] or '' for i in m), key=lambda g: sum((M[i]['guess'] or '') == g for i in m)),
               'cen': int(np.median([M[i]['cen'] for i in m])), 'L': float(np.median([M[i]['L'] for i in m])),
               'near_scene': round(float(np.mean([M[i]['near'] == 'scene' for i in m])), 2)})
cl.sort(key=lambda c: -c['videos'])
json.dump(cl, open(os.path.join(BASE, 'sozai/work/se_clusters.json'), 'w'), ensure_ascii=False)
print('まとまり（3本以上で使用）', len(cl))
for k, c in enumerate(cl[:40]): print(k, c['videos'], '本', c['n'], '回', c['guess'], c['cen'], 'Hz', c['L'], 's', c['channels'], 'scene率', c['near_scene'])
