#!/usr/bin/env python3
# 抜いた素材を色地の上に並べて確かめる：python3 build/sozai_check.py 出力.jpg png...
import sys
from PIL import Image, ImageDraw
fs = sys.argv[2:]; W = 480; H = 420
S = Image.new('RGB', (W * 4, H * ((len(fs) + 3) // 4)), (40, 40, 40))
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGBA'); im.thumbnail((W - 20, H - 40))
    bg = Image.new('RGBA', (W - 10, H - 10), (90, 160, 230, 255) if i % 2 else (230, 80, 120, 255))
    bg.alpha_composite(im, ((bg.width - im.width) // 2, (bg.height - im.height) // 2))
    S.paste(bg.convert('RGB'), ((i % 4) * W + 5, (i // 4) * H + 5)); ImageDraw.Draw(S).text(((i % 4) * W + 10, (i // 4) * H + 8), f.split('/')[-1], fill='white')
S.save(sys.argv[1], quality=85)
