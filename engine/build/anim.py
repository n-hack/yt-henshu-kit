#!/usr/bin/env python3
# テロップ解説アニメの描画エンジン（作業AI・2026-10-14）
# 場面（Scene）に部品（Elem）を時刻つきで並べ、1コマずつ PIL で描いて ffmpeg に流す。
# 元の映像は使わない。音声は元の音声をそのまま重ねる（render.py）。
import os, re, math, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

W, H = 1920, 1080
FPS = 30000 / 1001
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
FD = os.path.join(HERE, 'fonts')
# ---------------- 見た目の設定（themes/*.json で差し替え） ----------------
import json as _json
DEFAULT_THEME = {
    "bg": [236, 240, 244], "ink": [34, 34, 34], "red": [240, 20, 30], "marker": [255, 250, 0], "marker2": [255, 242, 120],
    "blue": [20, 110, 230], "green": [20, 160, 80], "sub_em": [255, 230, 0], "check": [60, 130, 110], "star": [255, 196, 0],
    "grad": [[0, [254, 218, 117]], [0.25, [250, 126, 30]], [0.5, [214, 41, 118]], [0.75, [150, 47, 191]], [1, [79, 91, 213]]],
    "fonts": {"noto": "NotoSansJP-VF.ttf", "pop": "MochiyPopOne-Regular.ttf", "dela": "DelaGothicOne-Regular.ttf",
              "rock": "RocknRollOne-Regular.ttf", "maru": "MPLUSRounded1c-ExtraBold.ttf", "zen": "ZenMaruGothic-Black.ttf",
              "script": "Pacifico-Regular.ttf"},
    "logo": {"image": "~/rin6/tools/yt-henshu/pipe/sozai/chara_icon1024.png", "mode": "color", "pos": [1699, 857], "d": 400, "ring": 14},   # 10/21 線画の自社キャラ（chara_line）は禁止→3Dのアイコン
    "sub_size": 70,
}
THEME_PATH = os.environ.get('THEME', '')
THEME = dict(DEFAULT_THEME)
if THEME_PATH:
    _t = _json.load(open(THEME_PATH if os.path.isabs(THEME_PATH) else os.path.join(BASE, THEME_PATH)))
    for _k, _v in _t.items():
        if isinstance(_v, dict) and isinstance(THEME.get(_k), dict): THEME[_k] = {**THEME[_k], **_v}
        else: THEME[_k] = _v
_c = lambda k: tuple(THEME[k])
BG, INK, RED, YEL, PALE_Y = _c('bg'), _c('ink'), _c('red'), _c('marker'), _c('marker2')
WHITE = (255, 255, 255)

# ---------------- フォント ----------------
@functools.lru_cache(None)
def font(size, wght=700, name='noto'):
    path = THEME['fonts'].get(name, name)
    if not os.path.isabs(path): path = os.path.join(FD, path)
    f = ImageFont.truetype(path, size)
    try:
        if f.get_variation_axes(): f.set_variation_by_axes([wght])
    except Exception:
        pass  # 太さを変えられないフォント
    return f

# ---------------- 動きの曲線 ----------------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_in_out(x): x = clamp(x); return x * x * (3 - 2 * x)
def back_out(x, s=1.9):
    x = clamp(x); x -= 1; return x * x * ((s + 1) * x + s) + 1

# ---------------- 画像の小道具 ----------------
@functools.lru_cache(None)
def load_rgba(path):
    return Image.open(path).convert('RGBA')

def asset(name):
    p = os.path.join(BASE, 'assets', 'cut', name + '.png')
    if not os.path.exists(p): p = os.path.join(BASE, 'assets', name + '.png')
    return load_rgba(p)

def fit(im, w=None, h=None):
    if w and h:
        r = min(w / im.width, h / im.height)
    elif w: r = w / im.width
    else: r = h / im.height
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)

def with_alpha(im, a):
    if a >= 0.999: return im
    im = im.copy()
    al = im.getchannel('A').point(lambda v: int(v * a))
    im.putalpha(al); return im

def shadowed(im, off=(0, 8), blur=14, alpha=0.22, pad=30):
    """部品に柔らかい影をつけた画像を返す（位置は pad だけずれる）"""
    w, h = im.width + pad * 2, im.height + pad * 2
    sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    a = im.getchannel('A').point(lambda v: int(v * alpha))
    blk = Image.new('RGBA', im.size, (20, 30, 50, 255)); blk.putalpha(a)
    sh.alpha_composite(blk, (pad + off[0], pad + off[1]))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    sh.alpha_composite(im, (pad, pad))
    return sh, pad

def rrect(w, h, r, fill, outline=None, width=0):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=fill, outline=outline, width=width)
    return im

def lin_grad(w, h, stops, horizontal=False):
    """stops = [(pos, (r,g,b)), ...] で縦（または横）グラデーション"""
    n = w if horizontal else h
    xs = np.linspace(0, 1, n)
    ps = [s[0] for s in stops]; cs = np.array([s[1] for s in stops], np.float32)
    col = np.stack([np.interp(xs, ps, cs[:, k]) for k in range(3)], 1)
    if horizontal: arr = np.broadcast_to(col[None, :, :], (h, w, 3))
    else: arr = np.broadcast_to(col[:, None, :], (h, w, 3))
    return Image.fromarray(arr.astype(np.uint8), 'RGB').convert('RGBA')

INSTA = [(p, tuple(c)) for p, c in THEME['grad']]

def insta_grad(w, h):
    """左下→右上のインスタ風グラデーション"""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = ((xx / w) + (1 - yy / h)) / 2
    ps = [s[0] for s in INSTA]; cs = np.array([s[1] for s in INSTA], np.float32)
    arr = np.stack([np.interp(t, ps, cs[:, k]) for k in range(3)], 2)
    return Image.fromarray(arr.astype(np.uint8), 'RGB').convert('RGBA')


import unicodedata
def is_tight(ch):
    """かな・カナ・記号は字幅を詰める（漢字と英数字はそのまま）"""
    o = ord(ch)
    return (0x3040 <= o <= 0x30FF) or ch in '、。，．・：；！？!?（）「」『』…ー〜％%' or (0xFF01 <= o <= 0xFF5E)

@functools.lru_cache(200000)
def _adv(ch, fid):
    f = _FONTS[fid]
    if ch == ' ': return 0, f.getlength(' ')
    if is_tight(ch):
        m = Image.new('L', (int(f.size * 2), int(f.size * 2)), 0)
        ImageDraw.Draw(m).text((int(f.size * 0.5), 0), ch, font=f, fill=255)
        bb = m.getbbox()
        if not bb: return 0, f.getlength(ch)
        bb = (bb[0] - int(f.size * 0.5), 0, bb[2] - int(f.size * 0.5), 0)
        if bb[2] - bb[0] <= 0: return 0, f.getlength(ch)
        gap = f.size * 0.07
        return -bb[0] + gap / 2, (bb[2] - bb[0]) + gap
    return 0, f.getlength(ch)
_FONTS = {}
def layout(s, f):
    """1文字ずつの (文字, 描く位置x) と 全体の幅"""
    fid = id(f); _FONTS[fid] = f
    xs = []; x = 0.0
    for ch in s:
        off, a = _adv(ch, fid)
        xs.append((ch, x + off)); x += a
    return xs, x

# ---------------- 文字（色・マーカー・傍点を混ぜられる） ----------------
TAG = re.compile(r'<(\w+)>(.*?)</\1>', re.S)
STYLE = {
    'r': dict(color=RED), 'b': dict(color=_c('blue')), 'g': dict(color=_c('green')),
    'y': dict(marker=YEL), 'py': dict(marker=PALE_Y), 'ry': dict(color=RED, marker=YEL),
    'd': dict(marker=YEL, dots=True), 'w': dict(color=WHITE), 'k': dict(color=INK), 'big': dict(scale=1.5),
    'bigr': dict(scale=1.6, color=RED), 'sm': dict(scale=0.7), 'hugr': dict(scale=2.3, color=RED), 'xr': dict(scale=1.95, color=RED), 'yt': dict(color=_c('sub_em')),
}

def parse(text):
    out = []; i = 0
    for m in TAG.finditer(text):
        if m.start() > i: out.append((text[i:m.start()], {}))
        out.append((m.group(2), STYLE[m.group(1)]))
        i = m.end()
    if i < len(text): out.append((text[i:], {}))
    return out

def text_img(text, size=56, wght=800, color=INK, name='noto', marker=None, stroke=0, stroke_color=WHITE,
             line_gap=0.28, align='left', pad_x=10, marker_pad=6):
    """複数行・装飾つきの文字を RGBA 画像にする。戻り値: (画像, 行ごとの[x0,x1,y0,y1]＝ワイプ用)"""
    lines = text.split('\n')
    rows = []
    for ln in lines:
        runs = []
        for s, st in parse(ln):
            sc = st.get('scale', 1.0)
            f = font(int(size * sc), wght, name)
            runs.append((s, f, st.get('color', color), st.get('marker', marker), st.get('dots', False)))
        rows.append(runs)
    # 寸法
    lh = []
    lw = []
    for runs in rows:
        w = 0; h = 0
        for s, f, *_ in runs:
            w += layout(s, f)[1]
            h = max(h, f.size)
        lw.append(int(w)); lh.append(int(h * (1 + line_gap)))
    maxw = max(lw) + pad_x * 2 + stroke * 2
    toth = sum(lh) + int(size * 0.6) + stroke * 2
    im = Image.new('RGBA', (int(maxw), int(toth)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    boxes = []
    y = int(size * 0.35) + stroke
    for runs, w, h in zip(rows, lw, lh):
        x = pad_x + stroke + (0 if align == 'left' else (maxw - pad_x * 2 - stroke * 2 - w) / (2 if align == 'center' else 1))
        x0 = x
        rowmax = max(f.size for _, f, *_ in runs)
        for s, f, c, mk, dots in runs:
            xs, adv = layout(s, f)
            base_y = y + (rowmax - f.size) * 0.82
            if mk:
                top = base_y + f.size * (-0.3 if dots else 0.02)
                d.rectangle([x - marker_pad, top, x + adv + marker_pad, base_y + f.size * 1.22], fill=mk)
            if dots:
                for ch, cx0 in xs:
                    cw = f.getbbox(ch)[2]; cx = x + cx0 + cw / 2; r = f.size * 0.07; cy = base_y - f.size * 0.08
                    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
            for ch, cx0 in xs:
                d.text((x + cx0, base_y), ch, font=f, fill=c, stroke_width=stroke, stroke_fill=stroke_color)
            x += adv
        boxes.append((x0 - marker_pad - stroke, x + marker_pad + stroke, y - 6, y + h))
        y += h
    return im, boxes

def impact_img(text, size=150, top=(255, 70, 70), bottom=(150, 0, 20), name='pop', stroke_in=10, stroke_out=6,
               out_color=(40, 0, 10), angle=0, line_gap=0.05, shadow=True, align='left'):
    """太い見出し文字（上下のグラデ・白フチ・外フチ・影・傾き）"""
    f = font(size, 900, name)
    lines = text.split('\n')
    pad = stroke_in + stroke_out + 20
    lw = [int(f.getlength(l)) for l in lines]
    lhh = int(size * (1.12 + line_gap))
    w = max(lw) + pad * 2; h = lhh * len(lines) + pad * 2
    mask = Image.new('L', (w, h), 0); md = ImageDraw.Draw(mask)
    wide = Image.new('L', (w, h), 0); wd = ImageDraw.Draw(wide)
    outer = Image.new('L', (w, h), 0); od = ImageDraw.Draw(outer)
    for i, l in enumerate(lines):
        x = pad + (0 if align == 'left' else (max(lw) - lw[i]) // 2); y = pad + i * lhh
        md.text((x, y), l, font=f, fill=255)
        wd.text((x, y), l, font=f, fill=255, stroke_width=stroke_in, stroke_fill=255)
        od.text((x, y), l, font=f, fill=255, stroke_width=stroke_in + stroke_out, stroke_fill=255)
    fill = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    # 行ごとにグラデ
    g = Image.new('RGBA', (w, h), bottom + (255,))
    for i, l in enumerate(lines):
        lm = Image.new('L', (w, h), 0)
        x = pad + (0 if align == 'left' else (max(lw) - lw[i]) // 2)
        ImageDraw.Draw(lm).text((x, pad + i * lhh), l, font=f, fill=255)
        bb = lm.getbbox()
        if not bb: continue
        band = lin_grad(w, bb[3] - bb[1], [(0, top), (1, bottom)])
        g.paste(band, (0, bb[1]), lm.crop((0, bb[1], w, bb[3])))
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    oc = Image.new('RGBA', (w, h), out_color + (255,)); out.paste(oc, (0, 0), outer)
    wc = Image.new('RGBA', (w, h), (255, 255, 255, 255)); out.paste(wc, (0, 0), wide)
    out.paste(g, (0, 0), mask)
    if shadow:
        sh = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0))
        blk = Image.new('RGBA', (w, h), (0, 0, 0, 110)); sh.paste(blk, (26, 30), outer)
        sh = sh.filter(ImageFilter.GaussianBlur(7))
        sh.alpha_composite(out, (16, 16)); out = sh
    if angle:
        out = out.rotate(angle, resample=Image.BICUBIC, expand=True)
    return out

# ---------------- 部品 ----------------
class Elem:
    """ts=出る時刻, te=消える時刻(None=場面の終わりまで), anim=出方, dur=出る長さ"""
    def __init__(self, ts, te=None, anim='fade', dur=None, x=0, y=0, anchor='lt', z=0, out='fade'):
        self.ts, self.te, self.anim, self.x, self.y, self.anchor, self.z, self.out = ts, te, anim, x, y, anchor, z, out
        self.dur = dur
        self._img = None
    def image(self):
        if self._img is None: self._img = self.build()
        return self._img
    def build(self): raise NotImplementedError
    def pos(self, im):
        x, y = self.x, self.y
        if self.anchor[0] == 'c': x -= im.width // 2
        elif self.anchor[0] == 'r': x -= im.width
        if self.anchor[1] == 'c': y -= im.height // 2
        elif self.anchor[1] == 'b': y -= im.height
        return int(x), int(y)
    def default_dur(self): return 0.25
    def draw(self, cv, t):
        if t < self.ts: return
        a_out = 1.0
        if self.te is not None:
            if t >= self.te: return
            if t > self.te - 0.2 and self.out == 'fade': a_out = (self.te - t) / 0.2
        im = self.image()
        dur = self.dur or self.default_dur()
        p = (t - self.ts) / dur if dur > 0 else 1
        x, y = self.pos(im)
        if p >= 1:
            cv.alpha_composite(with_alpha(im, a_out), (x, y)) if (0 <= x and 0 <= y and x + im.width <= W and y + im.height <= H) else paste_safe(cv, with_alpha(im, a_out), x, y)
            return
        self.animate(cv, im, x, y, p, a_out)
    def animate(self, cv, im, x, y, p, a_out):
        a = self.anim
        if a == 'fade':
            paste_safe(cv, with_alpha(im, ease_out(p) * a_out), x, y)
        elif a == 'pop' or a == 'zoom' or a == 'bounce':
            if a == 'pop': s = 0.55 + 0.45 * back_out(p); al = clamp(p * 3)
            elif a == 'bounce': s = 0.3 + 0.7 * back_out(p, 3.2); al = clamp(p * 4)
            else: s = 1.0 + 0.7 * (1 - ease_out(p)); al = ease_out(p)
            if abs(s - 1) < 0.01: paste_safe(cv, with_alpha(im, al * a_out), x, y); return
            sw, sh = max(1, int(im.width * s)), max(1, int(im.height * s))
            im2 = im.resize((sw, sh), Image.BILINEAR)
            paste_safe(cv, with_alpha(im2, al * a_out), x + (im.width - sw) // 2, y + (im.height - sh) // 2)
        elif a in ('up', 'down', 'left', 'right'):
            d = 60 * (1 - ease_out(p))
            dx, dy = {'up': (0, d), 'down': (0, -d), 'left': (d, 0), 'right': (-d, 0)}[a]
            paste_safe(cv, with_alpha(im, ease_out(p) * a_out), int(x + dx), int(y + dy))
        elif a == 'wipe':
            self.wipe(cv, im, x, y, p, a_out)
        else:
            paste_safe(cv, with_alpha(im, a_out), x, y)
    def wipe(self, cv, im, x, y, p, a_out):
        w = int(im.width * ease_in_out(p))
        if w > 0: paste_safe(cv, with_alpha(im.crop((0, 0, w, im.height)), a_out), x, y)

def paste_safe(cv, im, x, y):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0: return
    cv.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))

class Text(Elem):
    """文字。anim='wipe' のときは行ごとに左から順に出る（元の動画の出し方）"""
    def __init__(self, ts, text, size=56, wght=800, color=INK, marker=None, stroke=0, stroke_color=WHITE, name='noto',
                 align='left', line_gap=0.28, anim='wipe', **kw):
        super().__init__(ts, anim=anim, **kw)
        self.args = dict(size=size, wght=wght, color=color, marker=marker, stroke=stroke, stroke_color=stroke_color,
                         name=name, align=align, line_gap=line_gap)
        self.text = text
        self.nchar = len(TAG.sub(lambda m: m.group(2), text).replace('\n', ''))
    def build(self):
        im, self.boxes = text_img(self.text, **self.args)
        return im
    def default_dur(self):
        return clamp(0.035 * self.nchar + 0.12, 0.22, 0.9) if self.anim == 'wipe' else 0.25
    def wipe(self, cv, im, x, y, p, a_out):
        # 行ごとに順に出す（文字数に比例して時間を配る）
        self.image()
        lens = [max(1, b[1] - b[0]) for b in self.boxes]
        tot = sum(lens); acc = 0
        pp = ease_in_out(p) * tot
        for i, b in enumerate(self.boxes):
            y0 = int(b[2]) if i > 0 else 0
            y1 = int(self.boxes[i + 1][2]) if i + 1 < len(self.boxes) else im.height
            vis = clamp((pp - acc) / lens[i])
            acc += lens[i]
            if vis <= 0: continue
            xr = int(b[0] + (b[1] - b[0]) * vis) if vis < 1 else im.width
            if xr > 0:
                paste_safe(cv, with_alpha(im.crop((0, y0, xr, y1)), a_out), x, y + y0)

class Img(Elem):
    def __init__(self, ts, img, w=None, h=None, anim='up', shadow=False, **kw):
        super().__init__(ts, anim=anim, **kw); self.src, self.w, self.h, self.shadow = img, w, h, shadow
    def build(self):
        im = self.src if isinstance(self.src, Image.Image) else asset(self.src)
        im = fit(im, self.w, self.h)
        if self.shadow: im, _ = shadowed(im, off=(0, 6), blur=10, alpha=0.18, pad=20)
        return im

class Raw(Elem):
    """作った画像をそのまま置く"""
    def __init__(self, ts, img, anim='fade', **kw):
        super().__init__(ts, anim=anim, **kw); self._src = img
    def build(self): return self._src

def bubble_img(text, color=(250, 150, 60), tcolor=WHITE, size=46, tail='left', pad=None, r=None, wght=800, tail_size=None,
               thought=False, align='left'):
    pad = pad or (int(size * 0.55), int(size * 0.42)); r = r or int(size * 0.4); tail_size = tail_size or int(size * 0.75)
    t, _ = text_img(text, size=size, wght=wght, color=tcolor, pad_x=0, align=align)
    bw, bh = t.width + pad[0] * 2, t.height + pad[1] * 2 - int(size * 0.25)
    ex = tail_size + 6 if not thought else int(size * 1.35)
    im = Image.new('RGBA', (bw + ex * 2, bh + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([ex, 0, ex + bw, bh], r, fill=color)
    cy = bh // 2
    if thought:
        q = size / 40
        cx = ex - 16 * q if tail == 'left' else ex + bw + 16 * q
        sgn = -1 if tail == 'left' else 1
        d.ellipse([cx - 11 * q, cy - 13 * q, cx + 11 * q, cy + 13 * q], fill=color)
        d.ellipse([cx + sgn * 26 * q - 7 * q, cy - 7 * q, cx + sgn * 26 * q + 7 * q, cy + 7 * q], fill=color)
    elif tail == 'left':
        d.polygon([(ex + 2, cy - tail_size // 2), (ex - tail_size + 4, cy + 2), (ex + 2, cy + tail_size // 2)], fill=color)
    elif tail == 'right':
        d.polygon([(ex + bw - 2, cy - tail_size // 2), (ex + bw + tail_size - 4, cy + 2), (ex + bw - 2, cy + tail_size // 2)], fill=color)
    im.alpha_composite(t, (ex + pad[0], pad[1] - int(size * 0.2)))
    return im

class Bubble(Elem):
    def __init__(self, ts, text, color=(250, 150, 60), tail='left', size=46, anim='pop', thought=False, tcolor=WHITE, **kw):
        super().__init__(ts, anim=anim, **kw); self.a = (text, color, tail, size, thought, tcolor)
    def build(self):
        text, color, tail, size, thought, tcolor = self.a
        return bubble_img(text, color=color, tail=tail, size=size, thought=thought, tcolor=tcolor)

class Card(Elem):
    """白い角丸の板（影つき）"""
    def __init__(self, ts, w, h, color=WHITE, r=18, anim='fade', border=None, **kw):
        super().__init__(ts, anim=anim, **kw); self.wh, self.color, self.r, self.border = (w, h), color, r, border
    def build(self):
        im = rrect(*self.wh, self.r, self.color, outline=self.border, width=3 if self.border else 0)
        im, pad = shadowed(im, off=(0, 6), blur=12, alpha=0.18, pad=24)
        self.x -= pad; self.y -= pad
        return im

def check_icon(size=46, color=None):
    color = color or _c('check')
    s = size * 4
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([10, 10, s - 10, s - 10], outline=color, width=int(s * 0.085))
    d.line([(s * 0.27, s * 0.5), (s * 0.45, s * 0.68), (s * 0.8, s * 0.27)], fill=color, width=int(s * 0.1), joint='curve')
    return im.resize((size, size), Image.LANCZOS)

class Icon(Elem):
    """チェック・星などの小さな印。anim='spin' でくるっと出る"""
    def __init__(self, ts, img, anim='pop', **kw):
        super().__init__(ts, anim=anim, **kw); self._src = img
    def build(self): return self._src

def star_img(size=48, color=None):
    color = color or _c('star')
    s = size * 4; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pts = []
    for k in range(10):
        r = s * 0.48 if k % 2 == 0 else s * 0.2
        a = -math.pi / 2 + k * math.pi / 5
        pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a) + s * 0.04))
    d.polygon(pts, fill=color, outline=(230, 150, 0))
    return im.resize((size, size), Image.LANCZOS)

def insta_glyph(size=60, radius_ratio=0.28, white_bg=False):
    g = insta_grad(size, size)
    m = Image.new('L', (size, size), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], int(size * radius_ratio), fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0)); out.paste(g, (0, 0), m)
    d = ImageDraw.Draw(out); lw = max(2, size // 14)
    d.rounded_rectangle([size * 0.2, size * 0.2, size * 0.8, size * 0.8], int(size * 0.17), outline=WHITE, width=lw)
    d.ellipse([size * 0.36, size * 0.36, size * 0.64, size * 0.64], outline=WHITE, width=lw)
    d.ellipse([size * 0.66, size * 0.27, size * 0.72, size * 0.33], fill=WHITE)
    return out

def share_icon(size=56, color=(40, 110, 230)):
    s = size * 4; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = [(s * 0.72, s * 0.2), (s * 0.25, s * 0.5), (s * 0.72, s * 0.8)]
    d.line([P[0], P[1], P[2]], fill=color, width=int(s * 0.08))
    for x, y in P: d.ellipse([x - s * 0.15, y - s * 0.15, x + s * 0.15, y + s * 0.15], fill=color)
    return im.resize((size, size), Image.LANCZOS)

def face_ng_icon(size=60):
    s = size * 4; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([10, 10, s - 10, s - 10], fill=(255, 214, 60), outline=(200, 150, 0), width=8)
    d.arc([s * 0.28, s * 0.35, s * 0.72, s * 0.75], 20, 160, fill=(80, 50, 0), width=12)
    d.rectangle([0, s * 0.18, s, s * 0.42], fill=(40, 40, 60))
    f = font(int(s * 0.17), 900)
    d.text((s / 2, s * 0.3), '顔出しNG', font=f, fill=WHITE, anchor='mm')
    return im.resize((size, size), Image.LANCZOS)

def label_img(text, color, size=34, pad=(18, 6)):
    t, _ = text_img(text, size=size, wght=800, color=WHITE, pad_x=0)
    t = t.crop(t.getbbox()); h = int(size * 1.45)
    im = Image.new('RGBA', (t.width + pad[0] * 2, h), color + (255,))
    im.alpha_composite(t, (pad[0], (h - t.height) // 2))
    return im

def pill_img(text, size=34, colors=((255, 92, 160), (190, 90, 255)), tcolor=WHITE, pad=(26, 8)):
    t, _ = text_img(text, size=size, wght=800, color=tcolor, pad_x=0)
    w, h = t.width + pad[0] * 2, int(size * 1.55)
    g = lin_grad(w, h, [(0, colors[0]), (1, colors[1])], horizontal=True)
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=255)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0)); out.paste(g, (0, 0), m)
    out.alpha_composite(t, (pad[0], -int(size * 0.15)))
    return out

def circle_photo(path, d=300, border=8, gray=False):
    im = Image.open(os.path.join(BASE, 'assets', path + '.png')).convert('RGB')
    im = ImageOps.fit(im, (d, d), Image.LANCZOS)
    if gray: im = ImageOps.grayscale(im).convert('RGB')
    m = Image.new('L', (d * 2, d * 2), 0); ImageDraw.Draw(m).ellipse([0, 0, d * 2 - 1, d * 2 - 1], fill=255)
    m = m.resize((d, d), Image.LANCZOS)
    out = Image.new('RGBA', (d + border * 2, d + border * 2), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse([0, 0, d + border * 2 - 1, d + border * 2 - 1], fill=WHITE)
    rgba = im.convert('RGBA'); rgba.putalpha(m)
    out.alpha_composite(rgba, (border, border))
    return out

class CirclePhoto(Elem):
    """丸く切った写真。tg を過ぎると白黒に変わる"""
    def __init__(self, ts, path, d=300, tg=None, anim='fade', **kw):
        super().__init__(ts, anim=anim, **kw); self.path, self.d, self.tg = path, d, tg
        self.gray = None
    def build(self): return circle_photo(self.path, self.d)
    def draw(self, cv, t):
        if self.tg is not None and t >= self.tg:
            if self.gray is None: self.gray = circle_photo(self.path, self.d, gray=True)
            im0 = self.image(); x, y = self.pos(im0)
            k = clamp((t - self.tg) / 0.25)
            paste_safe(cv, im0, x, y); paste_safe(cv, with_alpha(self.gray, k), x, y)
            return
        super().draw(cv, t)

class Dim(Elem):
    """画面を暗くする（反応の吹き出しを目立たせる）"""
    def __init__(self, ts, alpha=0.6, color=(30, 30, 36), **kw):
        super().__init__(ts, anim='fade', dur=0.25, **kw); self.alpha, self.color = alpha, color
    def build(self): return Image.new('RGBA', (W, H), self.color + (int(255 * self.alpha),))

class Chart(Elem):
    """右肩上がりの面グラフ（左から伸びる）"""
    def __init__(self, ts, w=520, h=430, pts=None, dur=1.6, **kw):
        super().__init__(ts, anim='grow', dur=dur, **kw)
        self.wh = (w, h); self.pts = pts or [0.04, 0.12, 0.08, 0.3, 0.22, 0.52, 0.4, 0.62, 0.55, 0.95]
    def build(self):
        w, h = self.wh
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for k in range(11):
            yy = int(h * k / 10); d.line([(0, yy), (w, yy)], fill=(190, 196, 206), width=2)
        n = len(self.pts)
        P = [(int(w * i / (n - 1)), int(h - 10 - (h - 30) * v)) for i, v in enumerate(self.pts)]
        d.polygon([(0, h)] + P + [(w, h)], fill=(255, 210, 40, 255))
        d.line(P, fill=(70, 190, 70), width=7, joint='curve')
        for x, y in P[1::2] + [P[-1]]:
            d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=WHITE, outline=(70, 190, 70), width=5)
        return im
    def animate(self, cv, im, x, y, p, a_out):
        wv = int(im.width * ease_out(p))
        if wv > 0: paste_safe(cv, im.crop((0, 0, wv, im.height)), x, y)

class Badge(Elem):
    def __init__(self, ts, lines=('半年で', '10,000', 'Follow+'), d=250, anim='bounce', **kw):
        super().__init__(ts, anim=anim, **kw); self.lines, self.d = lines, d
    def build(self):
        d = self.d; s = d * 2
        g = lin_grad(s, s, [(0, (255, 70, 140)), (1, (255, 120, 40))])
        m = Image.new('L', (s, s), 0); md = ImageDraw.Draw(m)
        md.ellipse([0, 0, s - 1, s - 1], fill=255); md.polygon([(s * 0.62, s * 0.88), (s * 0.95, s * 1.0), (s * 0.85, s * 0.7)], fill=255)
        out = Image.new('RGBA', (s, s), (0, 0, 0, 0)); out.paste(g, (0, 0), m)
        dd = ImageDraw.Draw(out)
        dd.text((s / 2, s * 0.24), self.lines[0], font=font(int(s * 0.11), 900), fill=WHITE, anchor='mm')
        dd.text((s / 2, s * 0.5), self.lines[1], font=font(int(s * 0.19), 900, 'dela'), fill=WHITE, anchor='mm', stroke_width=6, stroke_fill=(200, 30, 90))
        dd.text((s / 2, s * 0.74), self.lines[2], font=font(int(s * 0.1), 900), fill=WHITE, anchor='mm')
        return out.resize((d, d), Image.LANCZOS)

def phone_img(h=520, screen_icon=True):
    w = int(h * 0.5)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], int(w * 0.16), fill=(25, 25, 28))
    d.rounded_rectangle([12, 14, w - 13, h - 15], int(w * 0.12), fill=(250, 250, 250))
    d.rounded_rectangle([w * 0.38, 22, w * 0.62, 36], 7, fill=(25, 25, 28))
    if screen_icon:
        g = insta_glyph(int(w * 0.3)); im.alpha_composite(g, ((w - g.width) // 2, (h - g.height) // 2))
    sh, pad = shadowed(im, off=(10, 14), blur=16, alpha=0.3, pad=40)
    return sh

# ---------------- 右下のロゴ（自社キャラさんの線画を丸い枠に） ----------------
@functools.lru_cache(None)
def ring_logo(d=None, ring=None):
    d = d or THEME['logo']['d']; ring = ring or THEME['logo']['ring']
    s = d * 2; R = ring * 2
    g = insta_grad(s, s)
    m = Image.new('L', (s, s), 0); md = ImageDraw.Draw(m); md.ellipse([0, 0, s - 1, s - 1], fill=255)
    out = Image.new('RGBA', (s, s), (0, 0, 0, 0)); out.paste(g, (0, 0), m)
    inner = Image.new('L', (s, s), 0); ImageDraw.Draw(inner).ellipse([R, R, s - 1 - R, s - 1 - R], fill=255)
    wbg = Image.new('RGBA', (s, s), (250, 250, 250, 255)); out.paste(wbg, (0, 0), inner)
    L = THEME['logo']; p = os.path.join(BASE, L['image'])  # 白地のまま使う（枠の中も白なので抜かない）
    if os.path.exists(p) and L.get('mode') == 'color':   # 色のある絵（3Dの自社キャラアイコン）を丸い枠の中にそのまま入れる（10/21 線画の自社キャラは禁止・kinshi/chara-boujin）
        src = Image.open(p).convert('RGBA')
        if L.get('crop'): src = src.crop(tuple(L['crop']))
        k = s - 2 * R; src = src.resize((k, k), Image.LANCZOS)
        out.paste(src, (R, R), ImageChops.multiply(src.getchannel('A'), inner.crop((R, R, R + k, R + k))))
    elif os.path.exists(p):
        src = Image.open(p).convert('L')
        if L.get('crop'): src = src.crop(tuple(L['crop']))
        if L.get('thicken'): src = src.filter(ImageFilter.MinFilter(L['thicken']))  # 線を太く（縮めても見えるように）
        k = (s - 2 * R) * 0.98 / src.width
        src = src.resize((int(src.width * k), int(src.height * k)), Image.LANCZOS)
        lay = Image.new('L', (s, s), 255); lay.paste(src, ((s - src.width) // 2 + int(s * 0.02), int(s * 0.16)))
        ink = lay.point(lambda v: 255 - v)  # 黒い線だけを取り出す
        ink = ImageChops.multiply(ink, inner)
        blk = Image.new('RGBA', (s, s), (30, 30, 30, 255))
        out.paste(blk, (0, 0), ink)
    return out.resize((d, d), Image.LANCZOS)

# ---------------- 場面 ----------------
class Scene:
    def __init__(self, t0, t1, elems, bg=None, kb=(1.0, 1.08), dim=0.0, ring=True, trans=0.22, ring_pos=None,
                 photo_focus=(0.5, 0.5)):
        self.t0, self.t1, self.elems, self.bg, self.kb, self.dim, self.ring, self.trans = t0, t1, elems, bg, kb, dim, ring, trans
        self.ring_pos = ring_pos or tuple(THEME['logo']['pos']); self.focus = photo_focus
        self._photo = None
    def photo(self):
        if self._photo is None:
            im = Image.open(os.path.join(BASE, 'assets', self.bg + '.png')).convert('RGB')
            self._photo = ImageOps.fit(im, (int(W * 1.12), int(H * 1.12)), Image.LANCZOS, centering=self.focus)
        return self._photo
    def render(self, t):
        if self.bg:
            ph = self.photo()
            k = clamp((t - self.t0) / max(0.1, self.t1 - self.t0))
            s = self.kb[0] + (self.kb[1] - self.kb[0]) * k
            cw, ch = int(W * 1.12 / s), int(H * 1.12 / s)
            cx, cy = ph.width // 2, ph.height // 2
            crop = ph.crop((cx - cw // 2, cy - ch // 2, cx - cw // 2 + cw, cy - ch // 2 + ch)).resize((W, H), Image.BILINEAR)
            cv = crop.convert('RGBA')
            if self.dim: cv.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, int(255 * self.dim))))
        else:
            cv = Image.new('RGBA', (W, H), BG + (255,))
        for e in sorted(self.elems, key=lambda e: e.z):
            e.draw(cv, t)
        return cv

class Subs:
    """下の字幕（黒い帯に白文字・強調は黄色）"""
    def __init__(self, items):
        self.items = items  # (t0, t1, text)
        self.cache = {}
    def draw(self, cv, t, ring_on):
        for i, (a, b, s) in enumerate(self.items):
            if a <= t < b:
                if i not in self.cache:
                    im, _ = text_img(s.replace('<y>', '<yt>').replace('</y>', '</yt>'), size=THEME['sub_size'], wght=900, color=WHITE, pad_x=18,
                                     line_gap=0.08)
                    bg = Image.new('RGBA', im.size, (0, 0, 0, 255)); bg.alpha_composite(im)
                    bg = bg.crop((0, 2, bg.width, bg.height - 4))
                    self.cache[i] = bg
                im = self.cache[i]
                x = (W - im.width) // 2
                if ring_on: x = max(20, min(x, 1640 - im.width))
                paste_safe(cv, im, x, H - im.height - 30)

def build_timeline(scenes):
    return sorted(scenes, key=lambda s: s.t0)

def frame_at(scenes, subs, t, sub_off=()):
    cur = None; prev = None
    for i, s in enumerate(scenes):
        if s.t0 <= t < s.t1: cur = s; prev = scenes[i - 1] if i > 0 else None; break
    if cur is None: cur = scenes[-1]
    cv = cur.render(t)
    ring_on = cur.ring
    if prev is not None and t < cur.t0 + cur.trans and cur.trans > 0:
        a = ease_in_out((t - cur.t0) / cur.trans)
        pv = prev.render(min(t, prev.t1 - 0.001))
        cv = Image.blend(pv, cv, a)
    # 右下のロゴ
    def ring_alpha(s):
        return 1.0 if s.ring else 0.0
    ra = ring_alpha(cur)
    if prev is not None and t < cur.t0 + cur.trans:
        a = ease_in_out((t - cur.t0) / cur.trans); ra = ring_alpha(prev) * (1 - a) + ring_alpha(cur) * a
    if ra > 0:
        lg = ring_logo(); x, y = cur.ring_pos
        paste_safe(cv, with_alpha(lg, ra), x - lg.width // 2, y - lg.height // 2)
    if subs is not None and not any(a <= t < b for a, b in sub_off):
        subs.draw(cv, t, ra > 0.5)
    return cv.convert('RGB')
