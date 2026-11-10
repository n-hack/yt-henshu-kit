#!/usr/bin/env python3
# BGMの塊を「同じ曲」ごとにまとめる（別の動画どうしで特徴がとても近い塊をつなぐ＋同じ窓の隣の塊をつなぐ）→ sozai/work/bgm_songs.json
import json, os, sys, numpy as np
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/bgm_blocks.npz'), allow_pickle=True); F = Z['f']; M = json.loads(str(Z['meta']))
X = (F - F.mean(0)) / (F.std(0) + 1e-9); X /= np.linalg.norm(X, axis=1, keepdims=True)
TH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.93
par = list(range(len(M)))
def find(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
def uni(a, b): par[find(a)] = find(b)
S = X @ X.T
vid = np.array([m['vid'] for m in M])
for i in range(len(M)):
    j = np.where((S[i] >= TH) & (vid != vid[i]))[0]
    for k in j: uni(i, int(k))
    if i + 1 < len(M) and M[i + 1]['vid'] == M[i]['vid'] and M[i + 1]['win'] == M[i]['win'] and abs(M[i + 1]['a'] - M[i]['a'] - 4) < 0.1 and S[i, i + 1] >= TH - 0.08:
        uni(i, i + 1)
comp = {}
for i in range(len(M)): comp.setdefault(find(i), []).append(i)
songs = []
for c, ms in comp.items():
    vs = sorted({M[i]['vid'] for i in ms})
    if len(vs) < 2: continue
    wins = {}
    for i in ms: wins[M[i]['win']] = wins.get(M[i]['win'], 0) + 1
    clean = [i for i in ms if M[i]['on'] == 0]
    songs.append({'blocks': len(ms), 'videos': len(vs), 'channels': sorted({M[i]['ch'] for i in ms}), 'wins': wins, 'clean': len(clean),
                  'members': sorted(ms, key=lambda i: (M[i]['vid'], M[i]['win'], M[i]['a']))})
songs.sort(key=lambda s: -s['videos'])
json.dump(songs, open(os.path.join(BASE, 'sozai/work/bgm_songs.json'), 'w'))
print('曲（2本以上）', len(songs))
for k, s in enumerate(songs[:30]): print(k, s['videos'], '本', s['blocks'], '塊 clean', s['clean'], s['wins'], s['channels'])
