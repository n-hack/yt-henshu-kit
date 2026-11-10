#!/usr/bin/env python3
# 切り替えと差し替えの一覧（v13・yt-henshu-pipe 10/19）：動く切り替え・字だけ差し替えの所を、前・途中・後の4コマで1行に並べる
#   等間隔の一覧（me_ai.py）では切り替えの途中のコマがほとんど写らないので、作業AIが見る場面シートに足す
#   出力 <作業フォルダ>/check/kirikae-<名前>-<n>.jpg（1枚に8行）
#   python3 kirikae_sheet.py <作業フォルダ> <mp4>
import os, sys, json, io, subprocess
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
P, MP4 = os.path.abspath(sys.argv[1]), sys.argv[2]; name = os.path.splitext(os.path.basename(MP4))[0]
KV = json.load(open(os.path.join(P, 'work', 'kata_v13.json')))
rows = [x for x in KV['kirikae'] if x['kind'] in ('動く切り替え', '字・帯だけ差し替え')]
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 24)
OFF = (-0.10, 0.08, 0.17, 0.45)
def koma(t):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % max(0, t), '-i', MP4, '-frames:v', '1', '-vf', 'scale=480:270', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
    return Image.open(io.BytesIO(r)).convert('RGB')
with ThreadPoolExecutor(8) as ex: ims = list(ex.map(koma, [x['t'] + o for x in rows for o in OFF]))
os.makedirs(os.path.join(P, 'check'), exist_ok=True); out = []
per = 8
for s in range(0, len(rows), per):
    part = rows[s:s + per]; sh = Image.new('RGB', (480 * 4, 306 * len(part)), 'white'); dr = ImageDraw.Draw(sh)
    for i, x in enumerate(part):
        for k, o in enumerate(OFF):
            sh.paste(ims[(s + i) * 4 + k], (k * 480, i * 306 + 34))
        dr.text((8, i * 306 + 4), '%d:%05.2f  %s%s  章%s  （左から %s 秒）' % (int(x['t'] // 60), x['t'] % 60, x['kind'], '・' + x['tr'] if x.get('tr') else '', x.get('ch', ''), '／'.join('%+.2f' % o for o in OFF)), fill='black', font=F)
    fp = os.path.join(P, 'check', 'kirikae-%s-%d.jpg' % (name, s // per + 1)); sh.save(fp, quality=85); out.append(fp)
print('切り替え %d か所・一覧 %d 枚：%s' % (len(rows), len(out), ' '.join(out)))
