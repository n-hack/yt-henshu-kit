#!/usr/bin/env python3
# 作業フォルダの素材の出どころ台帳 sozai-deguchi.json を作る（説明書の試し 11/01 で穴として見つかった手順を1本にした）
#   python3 ~/rin6/tools/yt-henshu/pipe/soco_deguchi.py <作業フォルダ>
#   ① <作業フォルダ>/sozai/daichou.tsv（soco.py g が書くソコストの台帳）→ soco_<id> を「素材サイト・イラスト」で
#   ② 写真の地（sozai/shashin の px*・pb*）と LINE の公式ロゴ → 本物の台帳（DAICHOU_MOTO）から写す。写真は shurui＝全画面挿絵（ルール7で数える）
#   すでにある行は消さない（足すだけ）。sozai_auto.py と zettai-mon.py（ルール3・7）がこの台帳を読む
import sys, os, json, csv
P = os.path.abspath(sys.argv[1])
DAICHOU_MOTO = os.path.expanduser('~/rin6/state/yt-anime-1014/renshu-onsei-2min/sozai-deguchi.json')   # 写真と公式ロゴの出どころが揃っている台帳（10/28〜）
out = os.path.join(P, 'sozai-deguchi.json')
D = json.load(open(out)) if os.path.exists(out) else {}
n0 = len(D)
tsv = os.path.join(P, 'sozai', 'daichou.tsv')
if os.path.exists(tsv):
    for r in csv.DictReader(open(tsv), delimiter='\t'):
        D.setdefault(r['name'], {'deguchi': '素材サイト', 'moto': 'ソコスト %s「%s」%s' % (r['id'], r['題名'], r['URL']),
                                 'license': '無料・商用可・表示不要・YouTube可（soco-st-guide-20261020.html）', 'kakin': False,
                                 'file': os.path.join(P, 'sozai', r['name'] + '.png'), 'shurui': 'イラスト', 'nyuushu': r['取った日時']})
M = json.load(open(DAICHOU_MOTO))
for k, v in M.items():
    if k.startswith(('px', 'pb')) or v.get('deguchi') == '公式':
        D.setdefault(k, v)
json.dump(D, open(out, 'w'), ensure_ascii=False, indent=1)
print('%d 行 → %s（足した %d）' % (len(D), out, len(D) - n0))
