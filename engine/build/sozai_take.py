#!/usr/bin/env python3
# 見本の動画から絵・背景・画面を切り出して sozai/<種類>/<名前>.png に置き、sozai/index.tsv に「どの動画の何秒・どこから」を残す
#   python3 build/sozai_take.py <名前> <種類> <動画id> <秒> [x0 y0 x1 y1] [--cut] [--tol 28] [--seed x,y ...] [--note 説明]
#   --cut … 背景（四辺から続く地の色）を抜いて透明にする（クリーム・灰・白の地のイラスト向け）
#   座標は 1920x1080 の画素。省くと画面全体
import sys, os, glob, subprocess, argparse, numpy as np, cv2
from PIL import Image, ImageFilter
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('kind'); ap.add_argument('vid'); ap.add_argument('t', type=float)
ap.add_argument('box', nargs='*', type=int); ap.add_argument('--cut', action='store_true'); ap.add_argument('--tol', type=float, default=28)
ap.add_argument('--note', default=''); ap.add_argument('--minfrac', type=float, default=0.04, help='一番大きな塊のこの割合より小さい塊（文字の切れ端など）は消す'); ap.add_argument('--erase', nargs='*', default=[], help='塗りつぶして消す四角 x0,y0,x1,y1（地の色で）')
a = ap.parse_args()
v = glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % a.vid))[0]; ch = v.split('/')[-2]
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % a.t, '-i', v, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
im = np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3).copy()
x0, y0, x1, y1 = a.box if len(a.box) == 4 else (0, 0, 1920, 1080)
c = im[y0:y1, x0:x1].copy()
border = np.concatenate([c[0], c[-1], c[:, 0], c[:, -1]]).astype(np.float32); bgc = np.median(border, 0)
for e in a.erase:
    ex0, ey0, ex1, ey1 = map(int, e.split(',')); c[ey0 - y0:ey1 - y0, ex0 - x0:ex1 - x0] = bgc.astype(np.uint8)
out = Image.fromarray(c)
if a.cut:
    d = np.sqrt(((c.astype(np.float32) - bgc) ** 2).sum(2)); near = (d < a.tol).astype(np.uint8)
    n, lab = cv2.connectedComponents(near, connectivity=4)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(edge)) & (near > 0)
    keep = (~bg).astype(np.uint8)
    n2, lab2, st, _ = cv2.connectedComponentsWithStats(keep, connectivity=8)
    if n2 > 1:
        big = st[1:, cv2.CC_STAT_AREA].max()
        ok = [k for k in range(1, n2) if st[k, cv2.CC_STAT_AREA] >= big * a.minfrac]
        bg = ~np.isin(lab2, ok)
    alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    out = out.convert('RGBA'); out.putalpha(alpha); bb = out.getbbox(); out = out.crop(bb)
os.makedirs(os.path.join(BASE, 'sozai', a.kind), exist_ok=True)
p = os.path.join(BASE, 'sozai', a.kind, a.name + '.png'); out.save(p)
idx = os.path.join(BASE, 'sozai/index.tsv')
if not os.path.exists(idx): open(idx, 'w').write('種類\t名前\t動画\tチャンネル\t秒\t切り取り(x0,y0,x1,y1)\t背景を抜いた\t説明\n')
lines = [l for l in open(idx).read().splitlines() if not l.startswith('%s\t%s\t' % (a.kind, a.name))]
lines.append('\t'.join([a.kind, a.name, a.vid, ch, '%.2f' % a.t, '%d,%d,%d,%d' % (x0, y0, x1, y1), 'はい' if a.cut else 'いいえ', a.note]))
open(idx, 'w').write('\n'.join(lines) + '\n')
print(p, out.size)
