#!/usr/bin/env python3
# v14（依頼主 10/19 19:12「アニメーションのバリエーションを最大に・手本の作者さんの図解アニメーションも・切り替えは多いほど良い」）
#   手本13本の場面記録から洗い出した表現の型（state/yt-henshu/pipe-1019/v14/kata-tehon.json・48型）のうち、v13 に無かった型を足す部品と出方
#   ① 動く図解（1つの部品の中で絵が育つ）：数字が数え上がる・棒グラフが伸びる・線グラフが描かれる・円グラフが満ちる・赤い丸で囲む・
#      チェックが付く・人が集まる・表が埋まる・階段が上がる … 部品の絵に info['pipe_dyn']（0〜1 の進み → その時の絵）を持たせ、出方 'grow' で描く
#   ② 出方：nobi（矢印・線が伸びる＝向きは部品の info['pipe_dir']）・egaku（上から描き出す）・tenmetsu（点滅）・yure（揺れ続ける）・
#      kaiten（回って出る）・hekomu（へこんで弾む）・glitch（ずれて出る）。どれも最初のコマから部品の一部が見える（言葉の頭に出る＝門のルール5）
#   ③ 地：SPOT（スポットの暗い地）・KIIRO／AKA_JI／AO_JI（色の地）・yoru(地)（地だけがゆっくり寄る。字幕と章札は動かさない）
import os, math, re, random
import anim as _anim, kit
from anim import W, H, paste_safe, with_alpha, clamp, ease_out, ease_in_out, back_out
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from riso_kata import GOTH, MINCHO
C = kit.C
def _font_img(text, size, col='#222222', stroke=None):
    return kit.deco(text, size, name=GOTH, fill=C(col), pad=2, strokes=stroke or [])
def _dyn(fn, kind):
    """最後の絵（進み1）に、進みごとの絵を作る関数を持たせる"""
    im = fn(1.0)
    im.info['pipe_dyn'] = fn; im.info['pipe_zukai'] = kind
    return im
def _shadow(im, off=(0, 6), blur=8, alpha=0.3):
    return _anim.shadowed(im, off=off, blur=blur, alpha=alpha, pad=16)[0]

# ---------------- ① 動く図解 ----------------
_NUM = re.compile(r'([0-9０-９][0-9０-９,，.]*)')
def kazu_up(label, num, size=200):
    """黒の小見出し＋赤い大きな数字が 0 から数え上がる（「1件30万円」「9割」）。num の中の最初の数字だけが動く"""
    from riso_kata import kazu as _kz
    m = _NUM.search(num)
    if not m: raise ValueError('kazu_up の num に数字が無い：%s' % num)
    raw = m.group(1).translate(str.maketrans('０１２３４５６７８９，', '0123456789,'))
    dec = len(raw.split('.')[1]) if '.' in raw else 0; val = float(raw.replace(',', '')); comma = ',' in raw
    final = _kz(label, num, size); Wf, Hf = final.size; cache = {}
    def fn(p):
        v = val * ease_out(clamp(p * 1.05))
        s = ('{:,.%df}' if comma else '{:.%df}') % dec
        txt = num[:m.start()] + s.format(v) + num[m.end():]
        if txt not in cache:
            im = _kz(label, txt, size); cv = Image.new('RGBA', (Wf, Hf), (0, 0, 0, 0))
            cv.alpha_composite(im.crop((0, 0, min(Wf, im.width), min(Hf, im.height))), (0, Hf - min(Hf, im.height)))
            cache[txt] = cv
        return cache[txt] if p < 1 else final
    out = _dyn(fn, '数字が数え上がる'); out.info['pipe_text'] = label + ' ' + num; return out

def bars_up(vals, labels, cols=None, h=420, bw=150, gap=90, nums=None):
    """棒グラフが左から順に下から伸びる（vals は 0〜1・nums は棒の上の字 例 ['10万','50万','100万']）"""
    n = len(vals); cols = cols or (['#9a9a9a'] * (n - 1) + ['#e3141b'])
    pad = 50; w = n * bw + (n - 1) * gap + 2 * pad; top = 70 if nums else 10
    lab = [_font_img(lb, 40) for lb in labels]; numi = [_font_img(x, 44, '#e3141b' if k == n - 1 else '#222222') for k, x in enumerate(nums or [])]
    def fn(p):
        im = Image.new('RGBA', (w, top + h + 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for k, (v, c) in enumerate(zip(vals, cols)):
            q = clamp(p * n * 0.75 - k * 0.6)   # 左から順に（少し重ねて）伸びる
            x0 = pad + k * (bw + gap); bh = int(h * v * ease_out(q))
            if bh > 0: d.rectangle([x0, top + h - bh, x0 + bw, top + h], fill=C(c))
            t = lab[k]; im.alpha_composite(t, (x0 + (bw - t.width) // 2, top + h + 8))
            if numi and q >= 0.85: t = numi[k]; im.alpha_composite(t, (x0 + (bw - t.width) // 2, max(0, top + h - bh - t.height - 4)))
        d.line([(0, top + h), (w, top + h)], fill=(40, 40, 40, 255), width=5)
        return im
    out = _dyn(fn, '棒グラフが伸びる'); out.info['pipe_text'] = ' '.join(labels + list(nums or [])); return out

def sen_graph(pts=None, w=760, h=440, col='#e3141b', label=None):
    """右肩上がりの線グラフが左から描かれ、先の点が走る（pts は 0〜1 の高さの並び）"""
    pts = pts or [0.05, 0.12, 0.1, 0.25, 0.22, 0.42, 0.38, 0.62, 0.7, 0.95]
    n = len(pts); P = [(40 + int((w - 80) * i / (n - 1)), int(h - 30 - (h - 70) * v)) for i, v in enumerate(pts)]
    li = _font_img(label, 48, col) if label else None
    def fn(p):
        im = Image.new('RGBA', (w, h + (li.height + 6 if li else 0)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for k in range(5): yy = int(30 + (h - 60) * k / 4); d.line([(40, yy), (w - 30, yy)], fill=(200, 200, 204, 255), width=2)
        d.line([(40, 20), (40, h - 30), (w - 20, h - 30)], fill=(60, 60, 60, 255), width=5)
        q = ease_in_out(clamp(p)) * (n - 1); k = int(q); f = q - k
        pts_ = P[:k + 1] + ([(int(P[k][0] + (P[k + 1][0] - P[k][0]) * f), int(P[k][1] + (P[k + 1][1] - P[k][1]) * f))] if k + 1 < n else [])
        if len(pts_) >= 2:
            d.polygon([(pts_[0][0], h - 30)] + pts_ + [(pts_[-1][0], h - 30)], fill=C(col)[:3] + (46,))
            d.line(pts_, fill=C(col), width=9, joint='curve')
        x, y = pts_[-1]; d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=(255, 255, 255, 255), outline=C(col), width=7)
        if li and p >= 0.9: im.alpha_composite(li, (w - li.width - 10, h + 6))
        return im
    out = _dyn(fn, '線グラフが描かれる')
    if label: out.info['pipe_text'] = label
    return out

def en_graph(ratio, label, d=380, col='#e3141b'):
    """円グラフ（ドーナツ）が上から時計回りに満ち、まん中の％が数え上がる（ratio は 0〜1）"""
    lab = _font_img(label, 44); s = d
    def fn(p):
        q = ease_out(clamp(p)); im = Image.new('RGBA', (max(s, lab.width), s + lab.height + 10), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        ox = (im.width - s) // 2; bb = [ox + 10, 10, ox + s - 10, s - 10]
        dr.ellipse(bb, outline=(215, 215, 218, 255), width=int(s * 0.16))
        if q > 0.002: dr.arc(bb, -90, -90 + 360 * ratio * q, fill=C(col), width=int(s * 0.16))
        t = kit.deco('%d%%' % round(ratio * 100 * q), int(s * 0.24), name=GOTH, fill=C(col), pad=2)
        im.alpha_composite(t, ((im.width - t.width) // 2, (s - t.height) // 2))
        im.alpha_composite(lab, ((im.width - lab.width) // 2, s + 6)); return im
    out = _dyn(fn, '円グラフが満ちる'); out.info['pipe_text'] = label; return out

def maru(w=420, h=200, col='#e3141b', lw=12):
    """赤い丸で囲む（筆で描くように一周する）。前に置いた字・絵の上に重ねて使う（重なりの検査から外す）"""
    def fn(p):
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        q = ease_in_out(clamp(p)); st = -200
        if q > 0.002: d.arc([lw, lw, w - lw, h - lw], st, st + 380 * q, fill=C(col), width=lw)
        return im
    out = _dyn(fn, '赤い丸で囲む'); out.info['pipe_kasane'] = True; return out

def shitasen(w=500, col='#e3141b', lw=14):
    """字の下に赤い下線を左から引く（字の下に重ねる）"""
    im = Image.new('RGBA', (w, lw + 8), (0, 0, 0, 0)); ImageDraw.Draw(im).rounded_rectangle([0, 4, w - 1, 4 + lw], lw // 2, fill=C(col))
    im.info['pipe_dir'] = 'right'; im.info['pipe_kasane'] = True; im.info['pipe_zukai'] = '下線を引く'; return im

def chk(text, size=56, col='#222222'):
    """青い丸が出て、チェックの線が描かれ、字が1字ずつ出る（箇条書き）"""
    sz = int(size * 1.3); t = kit.deco(text, sz, name=GOTH, fill=C(col), pad=2, tagfill={'r': C('#e01010')})
    cd = int(sz * 1.05); Wd = cd + 14 + t.width; Hd = max(cd, t.height)
    def fn(p):
        im = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0)); d = ImageDraw.Draw(im); oy = (Hd - cd) // 2
        a = clamp(p * 3); r = cd / 2 * (0.5 + 0.5 * back_out(a))
        cx, cy = cd / 2, oy + cd / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 110, 230, int(255 * a)))
        q = clamp((p - 0.15) / 0.5)
        if q > 0:
            P = [(cd * 0.26, oy + cd * 0.52), (cd * 0.44, oy + cd * 0.70), (cd * 0.76, oy + cd * 0.33)]
            L1 = math.dist(P[0], P[1]); L2 = math.dist(P[1], P[2]); s = q * (L1 + L2)
            if s <= L1: pts = [P[0], (P[0][0] + (P[1][0] - P[0][0]) * s / L1, P[0][1] + (P[1][1] - P[0][1]) * s / L1)]
            else: f = (s - L1) / L2; pts = [P[0], P[1], (P[1][0] + (P[2][0] - P[1][0]) * f, P[1][1] + (P[2][1] - P[1][1]) * f)]
            d.line(pts, fill=(255, 255, 255, 255), width=max(6, int(cd * 0.12)), joint='curve')
        n = max(1, len(re.sub(r'<[^>]+>|\s', '', text))); k = int(clamp(p * 1.25) * n + 0.999) / n; tw = int(t.width * k)
        if tw > 0: im.alpha_composite(t.crop((0, 0, tw, t.height)), (cd + 14, (Hd - t.height) // 2))
        return im
    out = _dyn(fn, 'チェックが付く'); out.info['pipe_text'] = text; return out

def atsumaru(n=10, red=0, size=110, cols=5, col='#333333', redcol='#e3141b', name='person'):
    """人（ピクトグラム）が四方から集まって並ぶ。red 人だけ赤"""
    a = kit.icon(name, int(size * 1.95), col, fill=1, wght=600); b = kit.icon(name, int(size * 1.95), redcol, fill=1, wght=600)
    rows = (n + cols - 1) // cols; Wd, Hd = a.width * cols, a.height * rows
    rng = random.Random(n * 31 + red); start = [(rng.uniform(-0.9, 0.9) * Wd, rng.uniform(-0.9, 0.9) * Hd) for _ in range(n)]
    def fn(p):
        im = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0))
        for k in range(n):
            q = ease_out(clamp(p * 1.6 - k * 0.6 / n)); src = b if k >= n - red else a
            gx, gy = (k % cols) * a.width, (k // cols) * a.height
            x = int(gx + start[k][0] * (1 - q)); y = int(gy + start[k][1] * (1 - q))
            if q > 0: paste_safe(im, with_alpha(src, clamp(q * 2.5)), x, y)
        return im
    out = _dyn(fn, '人が集まる'); return out

def hyou_umeru(rows, head=None, w=1500, col='#e3141b', size=48):
    """表が上の行から順に埋まる（rows は [['項目','中身'], …]・head は見出しの行）"""
    allr = ([head] if head else []) + rows; nc = max(len(r) for r in allr); rh = int(size * 1.9)
    hh = rh * len(allr); cw = w // nc
    cells = [[_font_img(c, size, '#ffffff' if (head and i == 0) else ('#e3141b' if j == nc - 1 else '#222222')) for j, c in enumerate(r)] for i, r in enumerate(allr)]
    def fn(p):
        im = Image.new('RGBA', (w, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, hh - 1], 16, fill=(255, 255, 255, 240), outline=(180, 180, 184, 255), width=4)
        if head: d.rounded_rectangle([0, 0, w - 1, rh], 16, fill=C(col)); d.rectangle([0, rh // 2, w - 1, rh], fill=C(col))
        for i in range(1, len(allr)): d.line([(0, i * rh), (w, i * rh)], fill=(200, 200, 204, 255), width=3)
        for j in range(1, nc): d.line([(j * cw, 0), (j * cw, hh)], fill=(200, 200, 204, 255), width=3)
        for i, r in enumerate(cells):
            q = clamp(p * len(allr) * 0.8 - i * 0.7)
            if q <= 0: continue
            for j, t in enumerate(r):
                tt = t if t.width <= cw - 20 else t.resize((cw - 20, int(t.height * (cw - 20) / t.width)), Image.LANCZOS)
                paste_safe(im, with_alpha(tt, clamp(q * 2)), j * cw + (cw - tt.width) // 2, i * rh + (rh - tt.height) // 2 + int(14 * (1 - ease_out(q))))
        return im
    out = _dyn(fn, '表が埋まる'); out.info['pipe_text'] = ' '.join(' '.join(r) for r in allr); return out

def kaidan(labels, col='#e3141b', step_w=300, step_h=110, size=46, name='directions_walk'):
    """階段が左下から1段ずつ上がり、最後の段に人が立つ（STEP・道のり）"""
    n = len(labels); Wd = step_w * n + 40; Hd = step_h * n + 220
    labs = [_font_img(lb, size, '#ffffff') for lb in labels]; man = kit.icon(name, 170, '#111111', fill=1, wght=600)
    def fn(p):
        im = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for k in range(n):
            q = ease_out(clamp(p * n * 0.8 - k * 0.7))
            if q <= 0: continue
            x0 = 20 + k * step_w; top = Hd - (k + 1) * step_h; y0 = int(top + (Hd - top) * (1 - q))
            c = C(col) if k == n - 1 else (70 + 12 * k, 70 + 12 * k, 76 + 12 * k, 255)   # 白い字が読める濃さまで（30ずつ明るくすると4段目が180で白字と差2.1・zen6 2:23）
            d.rectangle([x0, y0, x0 + step_w - 6, Hd], fill=c)
            t = labs[k]; t2 = t if t.width <= step_w - 20 else t.resize((step_w - 20, int(t.height * (step_w - 20) / t.width)), Image.LANCZOS)
            paste_safe(im, with_alpha(t2, q), x0 + (step_w - 6 - t2.width) // 2, y0 + (step_h - t2.height) // 2)
        q = clamp((p - 0.75) / 0.25)
        if q > 0:
            x0 = 20 + (n - 1) * step_w + (step_w - man.width) // 2; y0 = Hd - n * step_h - man.height
            paste_safe(im, with_alpha(man, q), x0, int(y0 - 40 * (1 - back_out(q))))
        return im
    out = _dyn(fn, '階段・道のり'); out.info['pipe_text'] = ' '.join(labels); return out

def tsunagu(length=360, direction='right', col='#555555', lw=10, dash=True):
    """2つの部品を線でつなぐ（点線が伸びる）。出方 nobi で使う"""
    horiz = direction in ('right', 'left'); w, h = (length, lw * 3) if horiz else (lw * 3, length)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); step = lw * 3
    for s in range(0, length, step if dash else length):
        e = min(length, s + (lw * 2 if dash else length))
        if horiz: d.line([(s, h // 2), (e, h // 2)], fill=C(col), width=lw)
        else: d.line([(w // 2, s), (w // 2, e)], fill=C(col), width=lw)
    d.ellipse(([w - lw * 3, 0, w, h] if horiz else [0, h - lw * 3, w, h]) if direction in ('right', 'down') else ([0, 0, lw * 3, h] if horiz else [0, 0, w, lw * 3]), fill=C(col))
    im.info['pipe_dir'] = direction; im.info['pipe_zukai'] = '線でつなぐ'; return im

def sumaho(name, h=520):
    """スマホの枠の中に、うちの実際の画面（gamen と同じ名前）を入れる"""
    from riso_kata import phone_waku
    src = Image.open(os.path.join(os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/gamen'), name + '.png')).convert('RGB')
    im = phone_waku(src, h); im.info['pipe_zukai'] = 'スマホの枠'; return im

# ---------------- ② 出方 ----------------
DYN_ANIMS = ('grow',)
NEW_ANIMS = ('nobi', 'egaku', 'tenmetsu', 'yure', 'kaiten', 'hekomu', 'glitch', 'grow')
DUR = {'grow': 0.8, 'nobi': 0.35, 'egaku': 0.45, 'tenmetsu': 0.6, 'yure': 1.2, 'kaiten': 0.4, 'hekomu': 0.4, 'glitch': 0.3}
_old = _anim.Elem.animate
def _crop_dir(im, q, d):
    w, h = im.size
    if d == 'right': c = im.crop((0, 0, max(1, int(w * q)), h)); return c, 0, 0
    if d == 'left': x0 = int(w * (1 - q)); return im.crop((x0, 0, w, h)), x0, 0
    if d == 'down': c = im.crop((0, 0, w, max(1, int(h * q)))); return c, 0, 0
    y0 = int(h * (1 - q)); return im.crop((0, y0, w, h)), 0, y0
def _animate(self, cv, im, x, y, p, a_out):
    a = self.anim
    if a == 'grow':
        fn = (im.info or {}).get('pipe_dyn')
        if fn is None: return _old(self, cv, im, x, y, p, a_out)   # 動く図解でない部品は描き出し（egaku）と同じに
        paste_safe(cv, with_alpha(fn(max(0.04, p)), a_out), x, y)
    elif a == 'nobi':     # 矢印・線が伸びる（最初のコマから先が少し見える）
        d = (im.info or {}).get('pipe_dir', 'right'); q = 0.12 + 0.88 * ease_out(p)
        c, dx, dy = _crop_dir(im, q, d); paste_safe(cv, with_alpha(c, a_out), x + dx, y + dy)
    elif a == 'egaku':    # 上から描き出す（線の先が明るい）
        q = 0.1 + 0.9 * ease_in_out(p); c, dx, dy = _crop_dir(im, q, 'down'); paste_safe(cv, with_alpha(c, a_out), x, y)
        if p < 1:
            band = Image.new('RGBA', (im.width, 10), (255, 255, 255, 0)); m = c.getchannel('A').crop((0, max(0, c.height - 10), im.width, c.height)).resize((im.width, 10))
            band.putalpha(ImageChops.multiply(m, Image.new('L', m.size, 200))); paste_safe(cv, band, x, y + c.height - 10)
    elif a == 'tenmetsu': # ぽんと出て2回点滅して残る
        if p < 0.25: s = 0.7 + 0.3 * back_out(p / 0.25); al = clamp(p * 8)
        else: s = 1.0; al = 0.25 if (0.4 < p < 0.52 or 0.67 < p < 0.79) else 1.0
        im2 = im if abs(s - 1) < 0.01 else im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
        paste_safe(cv, with_alpha(im2, al * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
    elif a == 'yure':     # 出てから左右に揺れ続け、だんだん止まる
        al = clamp(p * 10); amp = 14 * (1 - p) ** 1.5; dx = int(amp * math.sin(p * 1.2 * 2 * math.pi * 4)); ang = 2.5 * (1 - p) * math.sin(p * 2 * math.pi * 4)
        im2 = im.rotate(ang, resample=Image.BICUBIC, expand=True) if abs(ang) > 0.2 else im
        paste_safe(cv, with_alpha(im2, al * a_out), x + dx + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
    elif a == 'kaiten':   # 小さく回りながら出て止まる
        q = ease_out(p); ang = -200 * (1 - q); s = 0.35 + 0.65 * q
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR).rotate(ang, resample=Image.BICUBIC, expand=True)
        paste_safe(cv, with_alpha(im2, clamp(p * 4) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
    elif a == 'hekomu':   # 縦につぶれて、弾んで戻る
        sy = 1.0 + 0.35 * math.sin(p * math.pi * 1.5) * (1 - p) - 0.35 * (1 - p) ** 3; sx = 1.0 + (1.0 - sy) * 0.6
        im2 = im.resize((max(1, int(im.width * sx)), max(1, int(im.height * sy))), Image.BILINEAR)
        paste_safe(cv, with_alpha(im2, clamp(p * 6) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height))
    elif a == 'glitch':   # 色がずれて、横に刻まれて出る
        rng = random.Random(int(p * 30) + id(self) % 97); off = int(18 * (1 - p))
        if off > 1:
            r, g, b, al = im.split(); z = Image.new('L', im.size, 0)
            red = Image.merge('RGBA', (r, z, z, al)); cyan = Image.merge('RGBA', (z, g, b, al))
            paste_safe(cv, with_alpha(red, 0.6 * a_out), x - off, y); paste_safe(cv, with_alpha(cyan, 0.6 * a_out), x + off, y)
            for k in range(4):
                yy = rng.randint(0, max(1, im.height - 12)); hh = rng.randint(6, 24); sl = im.crop((0, yy, im.width, min(im.height, yy + hh)))
                paste_safe(cv, with_alpha(sl, a_out), x + rng.randint(-off * 2, off * 2), y + yy)
            paste_safe(cv, with_alpha(im, (0.4 + 0.6 * p) * a_out), x, y)
        else: paste_safe(cv, with_alpha(im, a_out), x, y)
    else:
        _old(self, cv, im, x, y, p, a_out)
_anim.Elem.animate = _animate

# ---------------- ③ 地 ----------------
def _spot():
    im = Image.new('RGB', (W, H), (6, 6, 9)); m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
    d.ellipse([W * 0.18, H * 0.02, W * 0.82, H * 1.05], fill=255); m = m.filter(ImageFilter.GaussianBlur(160))
    lit = Image.new('RGB', (W, H), (74, 70, 86)); im = Image.composite(lit, im, m); return im.convert('RGBA')
def _iro(a, b):
    g = Image.linear_gradient('L').resize((W, H)); im = Image.composite(Image.new('RGB', (W, H), C(b)[:3]), Image.new('RGB', (W, H), C(a)[:3]), g)
    return im.convert('RGBA')
SPOT = _spot(); SPOT_KIND = 'スポットの地'
KIIRO = _iro('#ffe45c', '#ffc21a'); AKA_JI = _iro('#e8313a', '#a8121a'); AO_JI = _iro('#2f7fe0', '#163f8f')
def yoru(bg, z=(1.0, 1.06)):
    """地だけがゆっくり寄る（字幕・章札・部品は動かさない＝見切れない）"""
    base = bg.copy() if isinstance(bg, Image.Image) else Image.new('RGBA', (W, H), (240, 240, 240, 255))
    def f(k):
        s = z[0] + (z[1] - z[0]) * k; cw, ch = int(W / s), int(H / s)
        return base.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
    f.pipe_ji = 'カメラがゆっくり寄る'; return f

# ---------------- 表現の型（手本の48型）に、うちの部品・出方・切り替え・地を当てる（数える道具 kata_v14.py が使う）----------------
ANIM_KATA = {'type': '1字ずつ出る', 'blur': 'ぼかし・ぶれから出る', 'pop': 'ポンと出る・ふくらむ', 'bounce': 'ポンと出る・ふくらむ',
             'left': '横・下から滑り込む', 'right': '横・下から滑り込む', 'up': '横・下から滑り込む', 'down': '横・下から滑り込む', 'slidel': '横・下から滑り込む',
             'wipe': '帯・字が左から伸びる', 'wipeblur': '帯・字が左から伸びる', 'kira': '光って出る・光が走る', 'stamp': '大きくから縮んで止まる（寄って出る・判子）',
             'zoom': '大きくから縮んで止まる（寄って出る・判子）', 'slam': '大きくから縮んで止まる（寄って出る・判子）', 'fly': '大きくから縮んで止まる（寄って出る・判子）',
             'drop': '落ちて弾む', 'tenmetsu': '点滅する', 'yure': '揺れる・動き続ける', 'kaiten': '回って出る', 'hekomu': 'へこむ・縮んで消える',
             'glitch': 'グリッチ', 'nobi': '矢印が伸びて流れを描く', 'egaku': '図・アイコンが線で描き出される', 'xdraw': '×で打ち消す', 'fade': 'フェード・溶けて替わる'}
PART_KATA = {'yaji': '矢印が伸びて流れを描く', 'tsunagu': '線でつなぐ（関係図）', 'waku': '箱・札が順に並ぶ（①②③・STEP）', 'bars': '棒グラフが伸びる',
             'bars_up': '棒グラフが伸びる', 'sen_graph': '線・面グラフが描かれる', 'en_graph': '円グラフが満ちる', 'card3': '比べる2列（左右）',
             'kazu': '数字を大きく出す・数え上がる', 'kazu_up': '数字を大きく出す・数え上がる', 'hito_mure': '人・アイコンが集まる／群れ', 'atsumaru': '人・アイコンが集まる／群れ',
             'hyou': '表が埋まる', 'hyou_umeru': '表が埋まる', 'check': 'チェックが付く', 'chk': 'チェックが付く', 'batsu': '×で打ち消す',
             'maru': '赤い丸で囲む・下線を引く', 'shitasen': '赤い丸で囲む・下線を引く', 'fuki': '吹き出し', 'fuki_hai': '吹き出し', 'kaidan': '階段・道のり',
             'gamen': '画面の録画・スクショ', 'jin': '人物イラスト', 'logo': 'ロゴ', 'sumaho': 'スマホ・PCの枠'}
TR_KATA = {'zoom': 'ズーム・ズームブラーで替わる', 'slide': '横ぶれ・横流れで替わる', 'yokobure': '横ぶれ・横流れで替わる', 'fade': 'フェード・溶けて替わる',
           'blur': 'フェード・溶けて替わる', 'flash': '白・光で飛ぶ', 'hosha': '放射ズームで替わる', 'glitch': 'グリッチ', 'anten': '暗転'}
