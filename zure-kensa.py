#!/usr/bin/env python3
# 言葉と画面のずれの検算（vsl-yt-1・10/18 依頼主の絶対ルール）：python3 zure-kensa.py <作業の場> <書き出した mp4>
#   部品ごとに「言葉の始まりのコマ」（work/zure-plan.json の t_plan をコマ番号に直したもの＝onset.py が声に貼り直した言葉の頭で置いた所）と
#   「その字・部品そのものが画面に出た最初のコマ」の差を全件出す。1コマを超えるものが1件でもあれば exit 1
#   10/19 21:1x（作業AI：ルール5は例外にしない・その字・部品そのものが出た瞬間で測る）：
#     前は「その範囲の画素が前のコマから変わった最初のコマ」で測っていた → 動き続ける人物・揺れる部品・前の部品の残りが同じ範囲にあると
#     「早く出た」と数えていた。いまは部品の絵（work/zure-ims/NNN.png・1/4）と画面を突き合わせ、部品の画素が画面に現れた最初のコマを取る。
#     絵と画面が合わない（カメラで大きさが変わる・絵が無い）ときだけ前の測り方（差分）に戻し、どちらで測ったかを列に出す。
#     基準の位置も直した：人物は下の真ん中（cb）・効果は左上（lt）で置いているのに、cc 以外を全部左上として測っていた。
import sys, os, json, subprocess, numpy as np
from PIL import Image
P, MP4 = sys.argv[1], sys.argv[2]
FPS = 30000 / 1001; SW, SH = 480, 270; K = SW / 1920
D = json.load(open(P + '/work/zure-plan.json'))
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', MP4, '-an', '-vf', 'scale=%d:%d,format=gray' % (SW, SH), '-f', 'rawvideo', '-'], capture_output=True).stdout
V = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW).astype(np.int16)
ev = {e['frame']: e for e in D['ev']}

def box(e):
    w, h = e['w'] * K, e['h'] * K; x, y = e['x'] * K, e['y'] * K; a = (e.get('anchor') or 'lt') + 't'
    l = x - w / 2 if a[0] == 'c' else (x - w if a[0] == 'r' else x)
    t = y - h / 2 if a[1] == 'c' else (y - h if a[1] == 'b' else y)
    return l, t, w, h

def onset_e(e, f):
    """部品の絵を画面に重ねて、部品の画素が画面に現れた最初のコマ（測れなければ None）"""
    if not e.get('img') or not os.path.exists(e['img']): return None
    l, t, w, h = box(e); iw, ih = max(1, int(round(w))), max(1, int(round(h)))
    im = Image.open(e['img']).convert('RGBA').resize((iw, ih))
    a = np.asarray(im.getchannel('A')) > 200; g = np.asarray(im.convert('L')).astype(np.int16)
    x0, y0 = int(round(l)), int(round(t)); sx, sy = max(0, -x0), max(0, -y0)
    x1, y1 = min(SW, x0 + iw), min(SH, y0 + ih); x0c, y0c = max(0, x0), max(0, y0)
    if x1 <= x0c or y1 <= y0c: return None
    m = a[sy:sy + (y1 - y0c), sx:sx + (x1 - x0c)]; gg = g[sy:sy + (y1 - y0c), sx:sx + (x1 - x0c)]
    if m.sum() < 12: return None
    ks = list(range(max(0, f - 12), min(len(V), f + 13)))
    p = {k: float((np.abs(V[k, y0c:y1, x0c:x1][m] - gg[m]) < 20).mean()) for k in ks}
    b = min(p[k] for k in ks if k <= f); top = max(p[k] for k in ks if k >= f)
    if top - b < 0.15: return None
    thr = b + max(0.03, 0.15 * (top - b))
    # 10/20 r8：前は窓（f−12〜）の頭から探し、窓の頭で既に似た絵（同じ形の人物・同じ地の色）が合っていると −12 を返していた（取り違え）。
    #   → 言葉の頭の後で一番よく合うコマ kt から前へたどり、閾値を下回った直後のコマ＝部品が「現れ始めた」コマを取る。
    #   kt より前に一度も下回らない（窓の頭からずっと合っている）ときは、本当に早く出ている → 窓の頭を返す（緩めない）
    kt = max((k for k in ks if k >= f), key=lambda k: p[k])
    if p[kt] <= thr: return None
    k0 = kt
    for k in reversed([k for k in ks if k <= kt]):
        if p[k] <= thr: break
        k0 = k
    return k0

def onset_d(e, f):
    """前の測り方：その範囲の画素が前のコマから変わった最初のコマ"""
    l, t, w, h = box(e)
    x0, y0, x1, y1 = max(0, int(l)), max(0, int(t)), min(SW, int(l + w)), min(SH, int(t + h))
    if x1 <= x0 or y1 <= y0: return None
    for k in range(max(1, f - 12), min(len(V), f + 13)):
        if np.abs(V[k, y0:y1, x0:x1] - V[k - 1, y0:y1, x0:x1]).mean() > 1.5: return k
    return None

rows = []
for e in D['elems']:
    f = int(round(e['t'] * FPS))
    shown = onset_e(e, f); how_m = '部品の絵'
    if shown is None: shown = onset_d(e, f); how_m = '差分'
    E = ev.get(f, {}); w_ = E.get('what', '?')
    rows.append((w_, e['anim'], f, shown, None if shown is None else shown - f, E.get('voice', ''), E.get('whisper', ''), E.get('how', ''), how_m))
print('部品\t出方\t言葉の始まりのコマ\t画面に出た最初のコマ\tずれ（コマ）\t声の頭（秒）\tWhisperの頭（秒）\t声の頭の取り方\t画面の測り方')
for r in rows: print('\t'.join(str(x) for x in r))
z = [abs(r[4]) for r in rows if r[4] is not None]; miss = [r for r in rows if r[4] is None]
print('件数 %d ／ 測れた %d（部品の絵 %d・差分 %d）／ 最大 %d コマ ／ 中央値 %.1f コマ ／ 1コマ超 %d 件 ／ 見つからない %d 件' % (
    len(rows), len(z), sum(1 for r in rows if r[8] == '部品の絵' and r[4] is not None), sum(1 for r in rows if r[8] == '差分' and r[4] is not None),
    max(z) if z else -1, float(np.median(z)) if z else -1, sum(1 for a in z if a > 1), len(miss)))
sys.exit(1 if (miss or any(a > 1 for a in z)) else 0)
