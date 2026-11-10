#!/usr/bin/env python3
# 白地のイラストから背景だけ抜く: cutout.py in.png out.png
# 上・左・右の端から「白に近い色」をたどって透明にする（下の端からはたどらない＝服の白が下で切れていても抜けない）
import sys, numpy as np
from PIL import Image, ImageFilter
from collections import deque
im = Image.open(sys.argv[1]).convert('RGB'); a = np.asarray(im).astype(np.int16)
h, w, _ = a.shape
white = (a.min(axis=2) > 232) & ((a.max(axis=2) - a.min(axis=2)) < 18)
bg = np.zeros((h, w), bool); q = deque()
for x in range(w):
    if white[0, x]: q.append((0, x))
for y in range(h):
    for x in (0, w - 1):
        if white[y, x]: q.append((y, x))
while q:
    y, x = q.popleft()
    if bg[y, x] or not white[y, x]: continue
    bg[y, x] = True
    if y > 0: q.append((y - 1, x))
    if y < h - 1: q.append((y + 1, x))
    if x > 0: q.append((y, x - 1))
    if x < w - 1: q.append((y, x + 1))
alpha = Image.fromarray(np.where(bg, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
out = im.convert('RGBA'); out.putalpha(alpha)
out = out.crop(out.getbbox())
out.save(sys.argv[2]); print(sys.argv[2], out.size)
