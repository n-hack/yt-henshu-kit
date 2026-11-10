#!/usr/bin/env python3
# 元と試作の同じ秒を左右に並べる: compare.py <試作mp4 または stills> <秒...>
#   1枚目＝左：元／右：試作（各960x540）。check/hikaku_<秒>.png と、全部をまとめた check/hikaku_all.png
import sys, os, subprocess
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
src = sys.argv[1]; ts = [float(x) for x in sys.argv[2:]]
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 30)
def grab(v, t, out):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '%.3f' % t, '-i', v, '-frames:v', '1', out], check=True)
    return Image.open(out).convert('RGB')
rows = []
for t in ts:
    o = grab(os.path.join(BASE, 'src', 'orig.mp4'), t, '/tmp/_o.png').resize((960, 540))
    if src == 'stills':
        sys.path.insert(0, HERE); import anim, importlib; m = importlib.import_module(os.environ.get('SPEC', 'scenes_3min'))
        mi = anim.frame_at(m.SCENES, m.SUBS, t).resize((960, 540))
    else:
        mi = grab(src, t, '/tmp/_m.png').resize((960, 540))
    c = Image.new('RGB', (1940, 590), (20, 20, 20)); c.paste(o, (0, 50)); c.paste(mi, (980, 50))
    d = ImageDraw.Draw(c); lab = '%d:%04.1f' % (t // 60, t % 60)
    d.text((10, 8), '元  ' + lab, font=F, fill='yellow'); d.text((990, 8), '試作  ' + lab, font=F, fill='cyan')
    p = os.path.join(BASE, 'check', 'hikaku_%06.2f.png' % t); c.save(p); rows.append(c)
if len(rows) > 1:
    A = Image.new('RGB', (1940, 590 * len(rows))); [A.paste(r, (0, 590 * i)) for i, r in enumerate(rows)]
    A.resize((970, 295 * len(rows))).save(os.path.join(BASE, 'check', 'hikaku_all.png'))
print('ok', len(rows))
