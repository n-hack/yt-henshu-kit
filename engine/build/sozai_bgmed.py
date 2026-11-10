#!/usr/bin/env python3
# 文字が入れ替わる区間のコマを何枚も取り、画素ごとの中央値で「文字の無い背景」を作る
#   python3 build/sozai_bgmed.py <名前> <種類> <動画id> <始め秒> <終わり秒> [枚数] [--note 説明]
import sys, os, glob, subprocess, numpy as np
from PIL import Image
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
name, kind, vid, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
n = int(sys.argv[6]) if len(sys.argv) > 6 and not sys.argv[6].startswith('--') else 41
note = sys.argv[sys.argv.index('--note') + 1] if '--note' in sys.argv else ''
v = glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % vid))[0]; ch = v.split('/')[-2]
fr = []
for t in np.linspace(t0, t1, n):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % t, '-i', v, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    if len(r) == 1920 * 1080 * 3: fr.append(np.frombuffer(r, np.uint8).reshape(1080, 1920, 3))
med = np.median(np.stack(fr), 0).astype(np.uint8)
os.makedirs(os.path.join(BASE, 'sozai', kind), exist_ok=True)
p = os.path.join(BASE, 'sozai', kind, name + '.png'); Image.fromarray(med).save(p)
idx = os.path.join(BASE, 'sozai/index.tsv')
lines = [l for l in open(idx).read().splitlines() if not l.startswith('%s\t%s\t' % (kind, name))]
lines.append('\t'.join([kind, name, vid, ch, '%.2f〜%.2f（%d枚の中央値）' % (t0, t1, len(fr)), '0,0,1920,1080', 'いいえ', note]))
open(idx, 'w').write('\n'.join(lines) + '\n'); print(p, len(fr))
