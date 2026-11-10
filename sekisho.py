#!/usr/bin/env python3
"""出す前の関所（依頼主 10/18：届かなければ依頼主に出さない・道具が止める）

  python3 sekisho.py --hon 本物.mp4 --mine 自分.mp4 [--t0 0 --t1 180] [--out 置き場]
  python3 sekisho.py --hon 本物.mp4                 # 測るだけ（線を決めるため）

本物と自分の同じ時刻を同じ式で測り、5つとも本物の RATIO（既定 0.9）以上なら通す。1つでも届かなければ exit 1。
  (a) 絵の差      1秒1コマ・320x180・灰色で、隣のコマとの差の平均（0〜255）＝別の作業AIの式
  (b) 埋まり方    暗い所（明るさ<100）か色の強い所（彩度>0.35）の画素の割合
  (c) 大きな切り替わり/分  10fps で隣のコマとの差が 8 を超えたコマ（0.3秒以内の続きは1回）
  (d) 動く要素/分  10fps で画面の一部（0.5〜35%）だけが変わるコマが2コマ以上続いた所（画面全部の切り替わりは数えない）
  (e) 色の種類    12色相×明暗の箱で、画面の0.3%以上を占めるコマが1割以上ある箱の数（参考。字の形そのものは測れないので、並べた画像を作業AIが目で見る項目として出力に残す）
並べた画像：同じ時刻を3秒おき60コマ、左が本物・右が自分（out/narabe-*.jpg）
"""
import argparse, json, os, subprocess, sys
import numpy as np

W, H, FPS = 320, 180, 10

def frames(f, t0, t1):
    raw = subprocess.run(['nice', '-n', '19', 'ffmpeg', '-v', 'quiet', '-ss', str(t0), '-t', str(t1 - t0), '-i', f, '-an',
                          '-vf', f'fps={FPS},scale={W}:{H},format=rgb24', '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)

def measure(a):
    n = len(a); mins = n / FPS / 60
    g = a.astype(np.float32).mean(axis=3)
    g1 = g[::FPS]; a_diff = float(np.abs(np.diff(g1, axis=0)).mean())
    d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2))
    big = []
    for i, x in enumerate(d):
        if x > 8 and (not big or i - big[-1] > 3): big.append(i)
    # (d) 動く要素：隣のコマで画素が12以上変わった面積が画面の0.5〜35%（＝一部だけが動く。画面全部の切り替わりは除く）のコマが2コマ以上続いた所を1つ
    area = (np.abs(np.diff(g, axis=0)) > 12).mean(axis=(1, 2))
    runs, k = 0, 0
    for x in area:
        if 0.005 < x < 0.35: k += 1
        else:
            if k >= 2: runs += 1
            k = 0
    if k >= 2: runs += 1
    s = a[::FPS].astype(np.float32); mx, mn = s.max(axis=3), s.min(axis=3); sat = (mx - mn) / np.maximum(mx, 1); lum = s.mean(axis=3)
    fill = float(((lum < 100) | (sat > 0.35)).mean())
    # 色の種類：彩度の強い画素を 12色相×2明暗 の箱に入れる
    hsv_h = np.zeros_like(mx); r, gg, b = s[..., 0], s[..., 1], s[..., 2]; c = mx - mn + 1e-6
    hsv_h = np.where(mx == r, ((gg - b) / c) % 6, np.where(mx == gg, (b - r) / c + 2, (r - gg) / c + 4)) / 6
    box = (np.floor(hsv_h * 12).astype(int) % 12) * 2 + (mx > 160)
    strong = sat > 0.35
    per = []
    for i in range(len(s)):
        cnt = np.bincount(box[i][strong[i]], minlength=24) / (W * H)
        per.append(cnt > 0.003)
    per = np.array(per)
    kinds = int((per.mean(axis=0) >= 0.1).sum()) if len(per) else 0
    return {'a_diff': round(a_diff, 2), 'b_fill': round(fill, 3), 'c_big_pm': round(len(big) / mins, 2), 'd_move_pm': round(runs / mins, 2), 'e_colors': kinds, 'sec': round(n / FPS, 1)}

# 線（10/18 手本2本 2Dgoti3GYAE・yNDrlmlh_fQ を 0:00〜3:00 と 2:00〜5:00 の4区間で測った最も低い値の9割）。--sen で本物なしに比べる
SEN = {'a_diff': 12.6, 'b_fill': 0.14, 'c_big_pm': 15.9, 'd_move_pm': 25.2}
SEN_SRC = '手本2本4区間の最低：a 13.98（2D 2-5分）・b 0.155（2D 2-5分）・c 17.67（2D 2-5分）・d 28.0（2D 0-3分）の9割'
NAME = {'a_diff': '(a) 絵の差', 'b_fill': '(b) 埋まり方', 'c_big_pm': '(c) 大きな切り替わり/分', 'd_move_pm': '(d) 動く要素/分', 'e_colors': '(e) 色の種類（字の形の近似）'}

def narabe(a, b, out, step=3):
    from PIL import Image
    idx = list(range(0, min(len(a), len(b)), FPS * step))[:60]
    tw, th = 320, 180
    for p in range(0, len(idx), 10):
        sheet = Image.new('RGB', (tw * 2 + 10, th * min(10, len(idx) - p)), (255, 255, 255))
        for r, i in enumerate(idx[p:p + 10]):
            sheet.paste(Image.fromarray(a[i]), (0, r * th)); sheet.paste(Image.fromarray(b[i]), (tw + 10, r * th))
        sheet.save(os.path.join(out, 'narabe-%02d.jpg' % (p // 10)), quality=80)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--hon'); ap.add_argument('--sen', action='store_true', help='本物でなく手本2本の線と比べる'); ap.add_argument('--mine'); ap.add_argument('--t0', type=float, default=0)
    ap.add_argument('--t1', type=float, default=180); ap.add_argument('--out', default=None); ap.add_argument('--ratio', type=float, default=0.9)
    x = ap.parse_args()
    if x.sen and x.mine:
        B = frames(x.mine, x.t0, x.t1); mb = measure(B); ng = [k for k in SEN if mb[k] < SEN[k]]
        out = x.out or os.path.join(os.path.dirname(os.path.abspath(x.mine)), 'sekisho'); os.makedirs(out, exist_ok=True)
        if x.hon: narabe(frames(x.hon, x.t0, x.t1), B, out)
        res = {'mine': os.path.basename(x.mine), 'mine_v': mb, 'sen': SEN, 'sen_src': SEN_SRC, 'todokanai': [NAME[k] for k in ng], 'pass': not ng,
               'me_de_miru': '(e) 字の形（フォント・縁・影・色・飾り）は機械で測れない。並べた画像を作業AIが目で見て、手本の7種と並べて確かめる', 'narabe': out if x.hon else None}
        json.dump(res, open(os.path.join(out, 'sekisho.json'), 'w'), ensure_ascii=False, indent=1)
        for k in SEN: print('%s 線 %s ／ 自分 %s %s' % (NAME[k], SEN[k], mb[k], '' if k not in ng else '← 届かない'))
        print('(e) 色の種類（参考）%s ／ 字の形は並べた画像を作業AIが目で見る' % mb['e_colors'])
        print('関所：%s' % ('通る' if not ng else '止める＝依頼主に出さない')); return 0 if not ng else 1
    A = frames(x.hon, x.t0, x.t1); ma = measure(A)
    if not x.mine:
        print(json.dumps({'hon': os.path.basename(x.hon), **ma}, ensure_ascii=False)); return 0
    B = frames(x.mine, x.t0, x.t1); mb = measure(B)
    out = x.out or os.path.join(os.path.dirname(os.path.abspath(x.mine)), 'sekisho')
    os.makedirs(out, exist_ok=True); narabe(A, B, out)
    ng = [k for k in NAME if k != 'e_colors' and mb[k] < ma[k] * x.ratio]   # (e) は参考（字の形は目で見る）
    res = {'hon': os.path.basename(x.hon), 'mine': os.path.basename(x.mine), 'hon_v': ma, 'mine_v': mb, 'ratio': x.ratio, 'todokanai': [NAME[k] for k in ng], 'pass': not ng, 'narabe': out}
    json.dump(res, open(os.path.join(out, 'sekisho.json'), 'w'), ensure_ascii=False, indent=1)
    for k in NAME: print('%s 本物 %s ／ 自分 %s %s' % (NAME[k], ma[k], mb[k], '' if k not in ng else '← 届かない'))
    print('(e) 字の形は機械で測れない：並べた画像を作業AIが目で見る（%s）' % out)
    print('関所：%s（並べた画像 %s）' % ('通る' if not ng else '止める＝依頼主に出さない', out))
    return 0 if not ng else 1

if __name__ == '__main__':
    sys.exit(main())
