#!/usr/bin/env python3
# まとまりごとに「音が鳴った瞬間の画面」を並べる（何の場面で使う音か目で決めるため）。1行＝1まとまり・3例×（鳴る0.1秒前／0.4秒後）
import json, os, glob, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/se_cand.npz'), allow_pickle=True); M = json.loads(str(Z['meta']))
CL = json.load(open(os.path.join(BASE, 'sozai/work/se_clusters.json')))
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 20)
def vpath(vid): return glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % vid))[0]
def grab(a):
    vid, t = a
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % max(0, t), '-i', vpath(vid), '-frames:v', '1', '-vf', 'scale=256:144', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    return Image.frombytes('RGB', (256, 144), r.stdout) if len(r.stdout) == 256 * 144 * 3 else Image.new('RGB', (256, 144))
def rows(ids, path):
    jobs = []
    for k in ids:
        c = CL[k]; ms = []; seen = set()
        for i in c['members']:
            if M[i]['vid'] in seen: continue
            seen.add(M[i]['vid']); ms.append(i)
            if len(ms) == 3: break
        for i in ms: jobs += [(M[i]['vid'], M[i]['t'] - 0.1), (M[i]['vid'], M[i]['t'] + 0.4)]
        jobs += [None] * (6 - 2 * len(ms))
    with ThreadPoolExecutor(12) as ex: ims = list(ex.map(lambda a: grab(a) if a else Image.new('RGB', (256, 144)), jobs))
    S = Image.new('RGB', (256 * 6 + 260, 150 * len(ids)), (30, 30, 30)); d = ImageDraw.Draw(S)
    for r, k in enumerate(ids):
        c = CL[k]
        d.text((6, r * 150 + 6), '#%d %d本 %d回\n%s\n%dHz %.2fs\nscene%.0f%%' % (k, c['videos'], c['n'], c['guess'][:9], c['cen'], c['L'], c['near_scene'] * 100), fill='yellow', font=F)
        for j in range(6): S.paste(ims[r * 6 + j], (260 + j * 256, r * 150))
    S.save(path, quality=85); print(path)
if __name__ == '__main__':
    n = min(len(CL), 48)
    for s in range(0, n, 8): rows(list(range(s, min(n, s + 8))), os.path.join(BASE, 'sozai/work/se_sheet_%02d.jpg' % (s // 8)))
