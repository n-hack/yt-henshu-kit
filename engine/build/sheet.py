#!/usr/bin/env python3
# 静止画を一覧画像にする: sheet.py <out.png> <cols> <label_offset_sec> <step_sec> files...
import sys
from PIL import Image, ImageDraw, ImageFont
out, cols, off, step = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
fs = sys.argv[5:]
ims = [Image.open(f).convert('RGB') for f in fs]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
S = Image.new('RGB', (w * cols, h * rows), 'black')
font = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 22)
d = ImageDraw.Draw(S)
for i, im in enumerate(ims):
    x, y = (i % cols) * w, (i // cols) * h
    S.paste(im, (x, y))
    t = off + i * step
    lab = '%d:%02d' % (t // 60, t % 60)
    d.rectangle([x, y, x + 70, y + 28], fill='black'); d.text((x + 4, y + 2), lab, fill='yellow', font=font)
S.save(out)
