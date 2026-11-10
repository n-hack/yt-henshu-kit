#!/usr/bin/env python3
# 声に残った言い直しを探す（vsl-yt-1・10/18）：~/rin6/tools/yt-henshu/narration/.venv/bin/python iinaoshi.py <作業の場>
#   声の編集で切った所（音がちょうど0の区間・0.1秒以上）でかたまりに分け、かたまりごとに Whisper で起こす。
#   次のかたまりが同じ言葉で始まる（頭の3字以上が同じ）なら、前のかたまりは言い直しの1回目の候補。
#   work/iinaoshi.json に全かたまりと候補を書く。外すかどうかは候補を見て決める（自動では外さない）
import os, sys, json, re, subprocess, unicodedata
import numpy as np, mlx_whisper
P = sys.argv[1]
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(P, 'work', 'vocals.wav'), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True).stdout
x = np.frombuffer(raw, np.int16); sr = 16000; h = 160; n = len(x) // h
z = (np.abs(x[:n * h].reshape(n, h)).max(1) == 0)
runs = []; s = None
for i, v in enumerate(z):
    if v and s is None: s = i
    if not v and s is not None:
        if i - s >= 10: runs.append((s / 100, i / 100))
        s = None
edges = [0.0] + [b for a, b in runs] ; ends = [a for a, b in runs] + [n / 100]
N = lambda t: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】%％]', '', unicodedata.normalize('NFKC', t))
C = []
for a, b in zip(edges, ends):
    if b - a < 0.15: continue
    seg = x[int(a * sr):int(b * sr)].astype(np.float32) / 32768
    r = mlx_whisper.transcribe(seg, path_or_hf_repo='mlx-community/whisper-large-v3-mlx', language='ja', condition_on_previous_text=False)
    C.append({'s': round(a, 2), 'e': round(b, 2), 'text': N(r['text'])})
def head_same(p, q, k=3):
    m = 0
    while m < min(len(p), len(q)) and p[m] == q[m]: m += 1
    return m >= k, m
cand = []
for i in range(len(C) - 1):
    ok, m = head_same(C[i]['text'], C[i + 1]['text'])
    if ok: cand.append({'i': i, 'first': C[i], 'second': C[i + 1], 'same_head': m})
json.dump({'chunks': C, 'cands': cand}, open(os.path.join(P, 'work', 'iinaoshi.json'), 'w'), ensure_ascii=False, indent=1)
for c in C: print('%7.2f-%7.2f %s' % (c['s'], c['e'], c['text']))
print('言い直しの候補 %d' % len(cand))
for c in cand: print('  %.2f-%.2f「%s」→ %.2f「%s」（頭の%d字が同じ）' % (c['first']['s'], c['first']['e'], c['first']['text'], c['second']['s'], c['second']['text'][:20], c['same_head']))
