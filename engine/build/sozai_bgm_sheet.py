#!/usr/bin/env python3
# 曲ごとに「鳴っている場面」を並べる（1行＝1曲・別の動画6か所）
import json, os, glob, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/bgm_blocks.npz'), allow_pickle=True); M = json.loads(str(Z['meta']))
SG = json.load(open(os.path.join(BASE, 'sozai/work/bgm_songs.json')))
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 20)
def vpath(v): return glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % v))[0]
def grab(a):
    if not a: return Image.new('RGB', (256, 144))
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % a[1], '-i', vpath(a[0]), '-frames:v', '1', '-vf', 'scale=256:144', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    return Image.frombytes('RGB', (256, 144), r.stdout) if len(r.stdout) == 110592 else Image.new('RGB', (256, 144))
ids = list(range(min(24, len(SG))))
jobs = []
for k in ids:
    seen = set(); sel = []
    for i in SG[k]['members']:
        if M[i]['vid'] in seen: continue
        seen.add(M[i]['vid']); sel.append((M[i]['vid'], M[i]['t'] + 2))
        if len(sel) == 6: break
    jobs += sel + [None] * (6 - len(sel))
with ThreadPoolExecutor(12) as ex: ims = list(ex.map(grab, jobs))
for p in range(0, len(ids), 8):
    sub = ids[p:p + 8]; S = Image.new('RGB', (260 + 256 * 6, 150 * len(sub)), (30, 30, 30)); d = ImageDraw.Draw(S)
    for r, k in enumerate(sub):
        s = SG[k]; d.text((6, r * 150 + 6), '曲#%d %d本\n%d塊 clean%d\n%s' % (k, s['videos'], s['blocks'], s['clean'], ' '.join('%s%d' % kv for kv in s['wins'].items())), fill='yellow', font=F)
        for j in range(6): S.paste(ims[k * 6 + j], (260 + 256 * j, r * 150))
    S.save(os.path.join(BASE, 'sozai/work/bgm_sheet_%d.jpg' % (p // 8)), quality=85)
print('ok')
