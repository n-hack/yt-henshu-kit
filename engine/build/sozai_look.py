#!/usr/bin/env python3
# 候補のコマを並べて見る：python3 build/sozai_look.py 出力名 動画id 秒 [秒...]（座標の目盛りつき・1枚 960x540）
import sys, os, glob, subprocess
from PIL import Image, ImageDraw, ImageFont
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 18)
name, vid, ts = sys.argv[1], sys.argv[2], [float(x) for x in sys.argv[3:]]
v = glob.glob(os.path.join(BASE, 'channels/dl/*/%s.mp4' % vid))[0]
ims = []
for t in ts:
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.2f' % t, '-i', v, '-frames:v', '1', '-vf', 'scale=960:540', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    im = Image.frombytes('RGB', (960, 540), r); d = ImageDraw.Draw(im)
    for x in range(0, 1920, 200): d.line([(x / 2, 0), (x / 2, 8)], fill='red'); d.text((x / 2 + 2, 8), str(x), fill='red', font=F)
    for y in range(0, 1080, 200): d.line([(0, y / 2), (8, y / 2)], fill='red'); d.text((10, y / 2), str(y), fill='red', font=F)
    d.rectangle([0, 515, 160, 540], fill='black'); d.text((4, 517), '%s %.2f' % (vid[:6], t), fill='yellow', font=F); ims.append(im)
cols = 2; rows = (len(ims) + 1) // 2; S = Image.new('RGB', (960 * cols, 540 * rows))
for i, im in enumerate(ims): S.paste(im, ((i % cols) * 960, (i // cols) * 540))
p = os.path.join(BASE, 'sozai/work/look', name + '.jpg'); S.save(p, quality=85); print(p)
