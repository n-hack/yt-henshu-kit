#!/usr/bin/env python3
# 動きの型・見せ方・全画面挿絵の門（依頼主 10/22 20:35「アニメーションのバリエーション少ない・見てて飽きる」・20:36「表現の仕方？」・20:37「全画面挿絵の頻度」）
#   python3 hyougen-mon.py <動画.mp4> [--out kekka.json] [--raw 控え.json] [--ocr 見やすさの控え raw-*.json] [--mon]
#   手本15本と自作を【同じ式】で測る（手本の per_full は人が書いた言葉なので、数の比べには使わない）。10コマ/秒・480x270 で1回だけ読む。
#   動きの型   前のコマとの差が出た所を「動きの出来事」にまとめ（最長6秒）、出来事ごとに型を1つ付ける：
#                出し（1コマで出る）／スライド（同じ向きに動く）／揺れ（向きが行き来）／ポップ・ズーム（真ん中から広がる）／
#                描き出し・打ち出し（片側から増える）／フェード（全体が少しずつ濃くなる）／その他の変化／動き続け（6秒を超える）
#              ① 型の種類（3回以上出た型の数）② 同じ型の連続の最長 ③ 型が切り替わる平均の秒数 ④ 1分ごとの型の種類の平均
#   見せ方     画面が丸ごと替わる所で区切った場面ごとに、場面の終わりのコマを1枚見て1つ付ける：
#                全画面の絵・写真・画面／大きな絵（人物・たとえ）／図・アイコン並べ／小さな絵＋字／文字だけ
#              ① 見せ方の種類 ② 同じ見せ方の連続の最長 ③「文字だけ」の場面の割合（時間）
#   全画面挿絵 1秒1コマ：外周が1色で埋まらない（地が見えない）コマ＝全画面の絵・写真。出た回数/分・時間の割合
import os, sys, json, argparse, subprocess, statistics as st
import numpy as np
from scipy import ndimage

W, H, FPS = 480, 270, 10
CUT = 0.45          # 画面の45%以上が一度に替わる＝場面の切り替わり
D_PX = 24           # 画素の差（0〜255）
MIN_FRAC = 0.0015   # これより小さい変化は揺らぎ
RUN_MAX = 60        # 6秒を超えて続く変化は「動き続け」

def koma(mp4):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', mp4, '-vf', 'fps=%d,scale=%d:%d' % (FPS, W, H), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    p.wait()

def bbox(m):
    ys, xs = np.where(m)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else None

def shift(a, b):
    """a→b の平行移動（位相相関・画素）"""
    if a.shape[0] < 8 or a.shape[1] < 8: return 0.0, 0.0
    A = np.fft.fft2(a - a.mean()); B = np.fft.fft2(b - b.mean()); R = A * np.conj(B); R /= np.abs(R) + 1e-9
    r = np.abs(np.fft.ifft2(R)); y, x = np.unravel_index(np.argmax(r), r.shape)
    if y > a.shape[0] // 2: y -= a.shape[0]
    if x > a.shape[1] // 2: x -= a.shape[1]
    return float(-x), float(-y)

def kata(run):
    """run = 灰色のコマの並び（変化の前の1コマ＋変化したコマ）→ 型"""
    n = len(run) - 1
    if n <= 1: return '出し'
    if n > RUN_MAX: return '動き続け'
    G = [r.astype(np.float32) for r in run]; first, last = G[0], G[-1]
    elem = np.abs(last - first) > D_PX
    um = np.zeros_like(elem)
    for i in range(1, len(G)): um |= np.abs(G[i] - G[i - 1]) > D_PX
    bb = bbox(um)
    if bb is None: return 'その他の変化'
    x0, y0, x1, y1 = bb
    # 平行移動：変化のあった枠の中で前後のコマのずれ
    sh = [shift(G[i - 1][y0:y1, x0:x1], G[i][y0:y1, x0:x1]) for i in range(1, len(G))]
    mag = [np.hypot(*s) for s in sh]; big = [s for s, m in zip(sh, mag) if 1.5 <= m <= 60]
    if len(big) >= max(2, n // 3):
        vx, vy = sum(s[0] for s in big), sum(s[1] for s in big); tot = sum(np.hypot(*s) for s in big)
        return 'スライド' if np.hypot(vx, vy) / max(tot, 1e-6) > 0.6 else '揺れ'
    if elem.sum() < 30: return '揺れ' if n >= 4 else 'その他の変化'
    # 最後のコマに近づいていく画素の広がり方
    ey, ex = np.where(elem); cx0, cy0 = ex.mean(), ey.mean(); ew = max(8.0, ex.max() - ex.min()); eh = max(8.0, ey.max() - ey.min())
    fr, cx, cy, rad, md = [], [], [], [], []
    for g in G[1:-1]:
        d = np.abs(g - last); ok = elem & (d < 20); fr.append(ok.sum() / elem.sum()); md.append(float(d[elem].mean()))
        if ok.sum() >= 10:
            oy, ox = np.where(ok); cx.append(ox.mean()); cy.append(oy.mean()); rad.append(float(np.hypot(ox - cx0, oy - cy0).mean()))
    if not fr: return '出し'
    if max(fr[:-1] or [0]) < 0.3 and len(md) >= 2 and md[0] > md[-1] * 1.3: return 'フェード'
    if len(cx) >= 2:
        mv = max(abs(cx[-1] - cx[0]) / ew, abs(cy[-1] - cy[0]) / eh)
        if mv > 0.2: return '描き出し・打ち出し'
        if rad[-1] > rad[0] * 1.25: return 'ポップ・ズーム'
    return 'その他の変化'

def misekata(f, boxes=None):
    """場面の終わりのコマ1枚 → 見せ方・全画面か"""
    a = f.astype(np.int16); b = max(4, int(W * 0.06))
    edge = np.concatenate([a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)])
    q = (edge // 32); key = q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]; cnt = np.bincount(key, minlength=512); m = int(cnt.argmax()); ji_frac = cnt[m] / len(key)
    if ji_frac < 0.35: return '全画面の絵・写真・画面', True, round(float(ji_frac), 2)
    bg = edge[key == m].mean(axis=0)
    fg = np.abs(a - bg).max(axis=2) > 40
    fg = ndimage.binary_opening(fg, iterations=1)
    for bx in boxes or []:   # 読めた字の箱（見やすさの控えの ocr）は絵から外す
        x0, y0 = int(bx[0] * W) - 3, int(bx[1] * H) - 3; x1, y1 = int((bx[0] + bx[2]) * W) + 3, int((bx[1] + bx[3]) * H) + 3
        fg[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = False
    # 字の形は細い線の集まり：細かく閉じると字と絵が混ざるので、塊の大きさと詰まり具合で分ける
    lab, n = ndimage.label(ndimage.binary_closing(fg, iterations=3))
    if n == 0: return '文字だけ', False, round(float(ji_frac), 2)
    sizes = ndimage.sum(fg, lab, range(1, n + 1)); boxes = ndimage.find_objects(lab)
    big, mid = 0, 0; area = W * H; tot = 0
    for s, bx in zip(sizes, boxes):
        hh = bx[0].stop - bx[0].start; ww = bx[1].stop - bx[1].start; fill = s / max(1, hh * ww)
        if hh < 0.09 * H and ww > 2.5 * hh: continue          # 横に長く低い＝字の行
        if fill < 0.18: continue                               # すかすか＝字や細い線
        tot += s
        if s > 0.06 * area: big += 1
        elif s > 0.004 * area: mid += 1
    if tot < 0.02 * area: return '文字だけ', False, round(float(ji_frac), 2)
    if big >= 1: return '大きな絵（人物・たとえ）', False, round(float(ji_frac), 2)
    if mid >= 3: return '図・アイコン並べ', False, round(float(ji_frac), 2)
    return '小さな絵＋字', False, round(float(ji_frac), 2)

def hakaru(mp4, ocr=None, sheet=None):
    OK = sorted((k['t'], [r['box'] for r in k['r']]) for k in (ocr or {}).get('koma', []))
    OT = [k[0] for k in OK]
    def boxes_at(t):
        if not OT: return None
        import bisect
        i = bisect.bisect_right(OT, t) - 1
        return OK[i][1] if i >= 0 and t - OT[i] <= 0.6 else []
    shots = []
    prev = None; prevg = None; t = 0; run = None; runs = []; cuts = []; scene_last = None; scenes = []; s0 = 0.0; zen = []
    for i, f in enumerate(koma(mp4)):
        t = i / FPS; g = f.astype(np.float32).mean(axis=2).astype(np.uint8)
        if i % FPS == 0: zen.append((round(t, 1), misekata(f)[1]))
        if prevg is not None:
            dm = np.abs(g.astype(np.int16) - prevg.astype(np.int16)) > D_PX; fr = dm.mean()
            if fr > CUT:
                if run is not None and len(run[1]) > 1: runs.append((run[0], '動き続け' if run[2] > RUN_MAX else kata(run[1])))
                run = None; cuts.append(round(t, 2))
                if scene_last is not None:
                    mm = misekata(scene_last, boxes_at(t - 1.0 / FPS)); scenes.append((s0, t, mm))
                    if sheet is not None: shots.append((t - 1.0 / FPS, scene_last.copy(), mm[0]))
                s0 = t
            elif fr > MIN_FRAC:
                if run is None: run = [t, [prevg], 0]
                run[2] += 1
                if len(run[1]) <= RUN_MAX + 1: run[1].append(g)
            else:
                if run is not None:
                    runs.append((run[0], '動き続け' if run[2] > RUN_MAX else kata(run[1]))); run = None
        prevg = g; scene_last = f
    if run is not None: runs.append((run[0], '動き続け' if run[2] > RUN_MAX else kata(run[1])))
    if scene_last is not None:
        mm = misekata(scene_last, boxes_at(t)); scenes.append((s0, t, mm))
        if sheet is not None: shots.append((t, scene_last.copy(), mm[0]))
    if sheet is not None: narabe(shots, sheet)
    return {'sec': round(t, 1), 'runs': [[round(a, 2), b] for a, b in runs], 'cuts': cuts,
            'scenes': [[round(a, 2), round(b, 2), m[0], m[2]] for a, b, m in scenes], 'zen': zen}

def narabe(shots, sheet):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(sheet, exist_ok=True)
    try: F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 22)
    except Exception: F = ImageFont.load_default()
    for s in range(0, len(shots), 24):
        ch = shots[s:s + 24]; sh = Image.new('RGB', (W * 4, (H + 30) * ((len(ch) + 3) // 4)), (30, 30, 30)); d = ImageDraw.Draw(sh)
        for i, (t, f, m) in enumerate(ch):
            x, y = (i % 4) * W, (i // 4) * (H + 30); sh.paste(Image.fromarray(f), (x, y + 30)); d.text((x + 6, y + 3), '%d:%04.1f %s' % (t // 60, t % 60, m), fill=(255, 255, 0), font=F)
        sh.save(os.path.join(sheet, 'misekata-%02d.jpg' % (s // 24)), quality=85)

def matome(raw):
    sec = raw['sec']; mn = sec / 60
    K = [k for _, k in raw['runs'] if k != '動き続け']
    from collections import Counter
    c = Counter(K)
    shurui = sum(1 for k, v in c.items() if v >= 3)
    def renzoku(xs):
        best = cur = 0; prev = None
        for x in xs:
            cur = cur + 1 if x == prev else 1; prev = x; best = max(best, cur)
        return best
    ts = [t for t, k in raw['runs'] if k != '動き続け']
    kirikae = [ts[i] for i in range(1, len(K)) if K[i] != K[i - 1]]
    kk = np.diff(kirikae).tolist() if len(kirikae) >= 2 else []
    per_min = []
    for m in range(int(sec // 60) + 1):
        ks = {k for t, k in raw['runs'] if m * 60 <= t < (m + 1) * 60 and k != '動き続け'}
        if (m + 1) * 60 <= sec + 1: per_min.append(len(ks))
    S = raw['scenes']; M = [s[2] for s in S]; dur = [s[1] - s[0] for s in S]
    mk = Counter(M)
    moji = sum(d for d, m in zip(dur, M) if m == '文字だけ') / max(1e-6, sum(dur))
    Z = raw['zen']; zn = [z for _, z in Z]
    zen_runs = sum(1 for i in range(len(zn)) if zn[i] and (i == 0 or not zn[i - 1]))
    return {'秒': sec,
            '動きの型': {'出来事の数': len(K), '型ごと': dict(c.most_common()), '①型の種類（3回以上）': shurui, '②同じ型の連続の最長': renzoku(K),
                     '③型が切り替わる平均の秒数': round(float(np.mean(kk)), 2) if kk else None, '④1分ごとの型の種類（平均）': round(float(np.mean(per_min)), 2) if per_min else None,
                     '動きの出来事/分': round(len(K) / mn, 1)},
            '見せ方': {'場面の数': len(S), '見せ方ごと（場面）': dict(mk.most_common()), '①見せ方の種類（2場面以上）': sum(1 for v in mk.values() if v >= 2), '②同じ見せ方の連続の最長': renzoku(M),
                    '③文字だけの時間の割合': round(moji, 3), '場面/分': round(len(S) / mn, 2)},
            '全画面挿絵': {'出た回数/分': round(zen_runs / mn, 2), '時間の割合': round(sum(zn) / max(1, len(zn)), 3), '回数': zen_runs}}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mp4'); ap.add_argument('--out'); ap.add_argument('--raw'); ap.add_argument('--mon', action='store_true'); ap.add_argument('--ocr'); ap.add_argument('--sheet')
    a = ap.parse_args()
    if a.raw and os.path.exists(a.raw): raw = json.load(open(a.raw))
    else:
        raw = hakaru(a.mp4, json.load(open(a.ocr)) if a.ocr else None, a.sheet)
        if a.raw: json.dump(raw, open(a.raw, 'w'), ensure_ascii=False)
    r = matome(raw); r['動画'] = a.mp4
    if a.out: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(r, ensure_ascii=False, indent=1))
