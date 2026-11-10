#!/usr/bin/env python3
# 場面シートに、別の目が一度でも指摘した場面の印をつける（作業AI 10/20：AI の判定は揺れるので、作業AIが最後に印の場面を目で見て決める）
#   場面の並びは me_shot.py と同じ（work/kata_v13.json の切り替わり）。1枚12場面・4×3・1マス 640×430
#   python3 bamen_shirushi.py <作業フォルダ> <mp4 の名前（拡張子なし）> <me-ruiseki.json>
#   出力 check/bamen-<名前>-shirushi-<n>.jpg（元のシートは触らない）
import os, sys, json
from PIL import Image, ImageDraw, ImageFont
P, name, rp = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3]
K = json.load(open(os.path.join(P, 'work', 'kata_v13.json')))
ids = [x['id'] for x in K['kirikae'] if x.get('id')]
RU = {b['id']: b for b in json.load(open(rp))['bamen']}
F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 22)
per = 12; out = []; n_mark = 0
for s in range(0, len(ids), per):
    src = os.path.join(P, 'check', 'bamen-%s-%d.jpg' % (name, s // per + 1))
    if not os.path.exists(src): sys.exit('🔴 場面シートが無い：%s' % src)
    sh = Image.open(src).convert('RGB'); dr = ImageDraw.Draw(sh)
    for k, sid in enumerate(ids[s:s + per]):
        b = RU.get(sid)
        if not b: continue
        x, y = (k % 4) * 640, (k // 4) * 430
        dr.rectangle((x + 2, y + 2, x + 637, y + 427), outline=(230, 0, 0), width=7)
        shu = sorted({t['shurui'] for t in b['shiteki']})
        lab = '印 %s（%d回：%s）' % ('・'.join(shu), len(b['deta_kai']), '・'.join(b['deta_kai']))
        tw = dr.textlength(lab, font=F); dr.rectangle((x + 8, y + 392, x + 16 + tw, y + 422), fill=(230, 0, 0)); dr.text((x + 12, y + 394), lab, fill='white', font=F)
        n_mark += 1
    fp = os.path.join(P, 'check', 'bamen-%s-shirushi-%d.jpg' % (name, s // per + 1)); sh.save(fp, quality=88); out.append(fp)
miss = [i for i in RU if i not in ids]
print('印 %d場面 / 全 %d場面 → %s' % (n_mark, len(ids), ' '.join(out)))
if miss: print('🟡 一覧にあるがシートに無い場面：%s' % miss)
