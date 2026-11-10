#!/usr/bin/env python3
# 映像の変化を数える: measure.py <video> <t0> <t1> <out.json>
# 10fps・160x90 で読み、前のコマとの差（平均絶対差）を出す。大きい差＝場面転換、小さい差＝要素の出入り
import sys, json, subprocess, numpy as np
v, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
w, h, fps = 160, 90, 10
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', v, '-t', str(t1 - t0), '-vf', f'fps={fps},scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
ev = []
i = 0
while i < len(d):
    if d[i] > 0.6:
        j = i
        while j + 1 < len(d) and d[j + 1] > 0.6: j += 1
        ev.append({'t': round(t0 + (i + 1) / fps, 2), 'dur': round((j - i + 1) / fps, 2), 'peak': round(float(d[i:j + 1].max()), 1), 'sum': round(float(d[i:j + 1].sum()), 1)})
        i = j + 1
    else: i += 1
json.dump({'diff': [round(float(x), 2) for x in d], 'events': ev}, open(out, 'w'))
big = [e for e in ev if e['sum'] > 25]
print('events', len(ev), 'big(scene)', len(big), 'per-min events %.1f scenes %.1f' % (len(ev) / ((t1 - t0) / 60), len(big) / ((t1 - t0) / 60)))
gaps = np.diff([0] + [e['t'] for e in ev])
print('median gap between any change %.2fs' % np.median(gaps))
print('trans dur median %.2fs' % np.median([e['dur'] for e in ev]))
