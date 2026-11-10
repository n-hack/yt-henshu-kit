#!/usr/bin/env python3
# 編集者の「テロップ・座布団・図・SNSロゴ・スマホ画面・暗い告知の地」を作る部品集（作業AI 2026-10-15）
# anim.py の上に乗る。どれも RGBA の画像を返す（置く場所と出方は anim の Elem / Raw で決める）。
# 見本の実寸（kata/KATA.md）に合わせた既定値。色やフォントは引数で替えられる。
import os, math, functools, json, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops
import anim
from anim import W, H, font, layout, lin_grad, paste_safe, with_alpha, fit, asset, clamp, ease_out, ease_in_out, back_out

C = lambda h: tuple(int(h.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)) if isinstance(h, str) else tuple(h)

# ---------------- 文字の組み（強調のタグつき） ----------------
# <r>赤</r> <y>黄</y> <w>白</w> <k>黒</k> <b>青</b> <p>ピンク</p> <g>金</g> <s>小さく</s> <L>大きく</L> と、<c=#hex>色</c>
TAGRE = re.compile(r'<(c=#[0-9a-fA-F]{6}|[a-zA-Z]+)>(.*?)</(?:c|[a-zA-Z]+)>', re.S)
NAMED = {'r': '#e82828', 'y': '#fcff00', 'w': '#ffffff', 'k': '#2e3238', 'b': '#2a7de1', 'p': '#ff3d8b', 'o': '#ff8a00'}

def runs_of(line, base_fill, tagfill=None):
    out = []; i = 0
    for m in TAGRE.finditer(line):
        if m.start() > i: out.append((line[i:m.start()], base_fill, 1.0))
        tg = m.group(1)
        if tg.startswith('c='): out.append((m.group(2), C(tg[2:]), 1.0))
        elif tg == 's': out.append((m.group(2), base_fill, 0.72))
        elif tg == 'L': out.append((m.group(2), base_fill, 1.35))
        elif tagfill and tg in tagfill: out.append((m.group(2), tagfill[tg], 1.0))
        else: out.append((m.group(2), C(NAMED.get(tg, '#e82828')), 1.0))
        i = m.end()
    if i < len(line): out.append((line[i:], base_fill, 1.0))
    return [r for r in out if r[0]]

def _fill_img(spec, w, h):
    """塗り: (r,g,b) / ('v', [(位置,色)...]) 縦グラデ / ('h', ...) 横グラデ / ('img', 画像)"""
    if isinstance(spec, tuple) and len(spec) == 3 and all(isinstance(x, int) for x in spec):
        return Image.new('RGBA', (w, h), spec + (255,))
    kind = spec[0]
    if kind in ('v', 'h'):
        return lin_grad(max(1, w), max(1, h), [(p, C(c)) for p, c in spec[1]], horizontal=(kind == 'h'))
    if kind == 'img':
        return ImageOps.fit(spec[1].convert('RGBA'), (max(1, w), max(1, h)))
    raise ValueError(spec)

def deco(text, size=110, name='noto', wght=900, fill=(46, 50, 56), tagfill=None, strokes=(), glow=None, shadow=None,
         italic=0.0, line_gap=0.12, align='center', tight=True, pad=None, bold=0):
    """飾り文字（テロップの本体）。
    strokes = [(太さ, 色), ...] 内側から外側へ（例: [(10,'#fff'), (6,'#000')]）
    glow = (半径, 色, 強さ)    shadow = (dx, dy, ぼかし, 濃さ)    italic = 0.18 くらいで斜体
    fill の色は文字全体の塗り。<r> などのタグで一部だけ替えられる（グラデは行ごとに上から下へ）"""
    lines = text.split('\n')
    sw = sum(int(w) for w, _ in strokes) + bold
    gpad = int(glow[0] * 2.2) if glow else 0
    P = pad if pad is not None else sw + gpad + 24
    rows = []
    for ln in lines:
        rr = []
        for s, f_, sc in runs_of(ln, fill, tagfill):
            f = font(int(size * sc), wght, name)
            xs, adv = layout(s, f) if tight else ([(ch, sum(f.getlength(c) for c in s[:k])) for k, ch in enumerate(s)], f.getlength(s))
            rr.append((s, f, f_, xs, adv))
        rows.append(rr)
    lh = [int(max([r[1].size for r in rr] + [size]) * (1 + line_gap)) for rr in rows]
    lw = [sum(r[4] for r in rr) for rr in rows]
    Wc = int(max(lw) + P * 2 + size * italic * 1.2 + 4); Hc = int(sum(lh) + P * 2 + size * 0.25)
    masks_fill = []  # (mask, fill_spec, bbox)
    stroke_masks = [Image.new('L', (Wc, Hc), 0) for _ in strokes]
    body = Image.new('L', (Wc, Hc), 0)
    y = P
    for rr, w, h in zip(rows, lw, lh):
        x0 = P + (0 if align == 'left' else (max(lw) - w) * (0.5 if align == 'center' else 1.0))
        x = x0; rowmax = max(r[1].size for r in rr)
        for s, f, f_, xs, adv in rr:
            by = y + (rowmax - f.size) * 0.85
            m = Image.new('L', (Wc, Hc), 0); d = ImageDraw.Draw(m)
            for ch, cx in xs: d.text((x + cx, by), ch, font=f, fill=255, stroke_width=bold, stroke_fill=255)
            body = ImageChops.lighter(body, m)
            acc = bold
            for k, (sw_, _) in enumerate(strokes):
                acc += int(sw_)
                d2 = ImageDraw.Draw(stroke_masks[k])
                for ch, cx in xs: d2.text((x + cx, by), ch, font=f, fill=255, stroke_width=acc, stroke_fill=255)
            masks_fill.append((m, f_, (int(x), int(y), int(x + adv), int(y + h))))
            x += adv
        y += h
    out = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0))
    outer = stroke_masks[-1] if strokes else body
    if shadow:
        dx, dy, bl, al = shadow
        sh = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0)); blk = Image.new('RGBA', (Wc, Hc), (0, 0, 0, int(255 * al)))
        sh.paste(blk, (dx, dy), outer); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(bl)))
    if glow:
        r, col, k = glow
        gm = outer.filter(ImageFilter.GaussianBlur(r)).point(lambda v: min(255, int(v * k)))
        g = Image.new('RGBA', (Wc, Hc), C(col) + (255,)); g.putalpha(gm); out.alpha_composite(g)
    for k in range(len(strokes) - 1, -1, -1):
        col = strokes[k][1]
        if isinstance(col, (tuple, list)) and len(col) and isinstance(col[0], str) and col[0] in ('v', 'h'):
            lay = _fill_img(col, Wc, Hc)
        else:
            lay = Image.new('RGBA', (Wc, Hc), C(col) + (255,))
        lay.putalpha(stroke_masks[k]); out.alpha_composite(lay)
    # 塗り（行・強調ごと）
    for m, f_, (x0, y0, x1, y1) in masks_fill:
        if isinstance(f_, tuple) and len(f_) == 3 and all(isinstance(v, int) for v in f_):
            lay = Image.new('RGBA', (Wc, Hc), f_ + (255,))
        else:
            lay = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0))
            bb = m.getbbox() or (x0, y0, x1, y1)
            g = _fill_img(f_, bb[2] - bb[0], bb[3] - bb[1]); lay.paste(g, (bb[0], bb[1]))
        lay.putalpha(ImageChops.multiply(m, lay.getchannel('A')))
        out.alpha_composite(lay)
    if italic:
        out = shear(out, italic)
    bb = out.getbbox()
    if bb: out = out.crop((max(0, bb[0] - 4), max(0, bb[1] - 4), min(out.width, bb[2] + 4), min(out.height, bb[3] + 4)))
    return out

def shear(im, k):
    w, h = im.size; nw = int(w + abs(k) * h)
    return im.transform((nw, h), Image.AFFINE, (1, k, -k * h if k > 0 else 0, 0, 1, 0), resample=Image.BICUBIC)

# よく使う飾りの組（見本の実寸から）
GOLD = ('v', [(0, '#fff6c8'), (0.45, '#e9c56a'), (0.55, '#c99a2e'), (1, '#f7e3a0')])
SILVER = ('v', [(0, '#ffffff'), (0.5, '#d8d4cc'), (0.56, '#a49e92'), (1, '#efece6')])
REDG = ('v', [(0, '#ff3a3a'), (0.55, '#e80000'), (1, '#b80000')])
BLUEG = ('v', [(0, '#7fd0ff'), (0.5, '#2b8de8'), (1, '#1858c8')])
ICEG = ('v', [(0, '#e8fbff'), (0.5, '#6fd3e6'), (1, '#1e8fb0')])
FIREG = ('v', [(0, '#fff07a'), (0.45, '#ffae1a'), (1, '#ff4a00')])

def t_plain(text, size=86, color='#2e3238', **kw):
    """普通の太ゴシック（濃いグレー）"""
    return deco(text, size, fill=C(color), **kw)

def t_red_italic(text, size=150):
    """『1番大事なところ』型：赤グラデの極太斜体＋白フチ＋金の光"""
    return deco(text, size, fill=REDG, strokes=[(9, '#ffffff')], glow=(9, '#ffc93a', 2.6), italic=0.16)

def t_gold(text, size=120, italic=0.1, name='noto'):
    """『本質や押さえておくことを』型：金の金属調＋黒フチ＋影"""
    return deco(text, size, name=name, fill=GOLD, strokes=[(7, '#111111')], shadow=(6, 8, 6, 0.55), italic=italic)

def t_red_glow(text, size=110):
    """『情報発信の本質を話していきます』型：赤い太字＋黄色のやわらかい光"""
    return deco(text, size, fill=C('#c62d2e'), glow=(14, '#fff36a', 3.2))

def t_blue_big(text, size=120):
    """『情報発信』型：青グラデの斜体＋白フチ＋薄い影"""
    return deco(text, size, fill=BLUEG, strokes=[(8, '#ffffff')], shadow=(3, 5, 5, 0.3), italic=0.14)

def box(text, size=64, bg='#fe3727', fg='#fcff78', padx=None, pady=None, italic=0.0, name='noto', wght=900, tagfill=None, radius=0,
        border=None, glossy=False):
    """座布団（四角い帯の上に文字）。italic は文字だけ傾ける"""
    t = deco(text, size, name=name, wght=wght, fill=C(fg), tagfill=tagfill, italic=italic, pad=2)
    px = padx if padx is not None else int(size * 0.18); py = pady if pady is not None else int(size * 0.08)
    w, h = t.width + px * 2, t.height + py * 2
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if isinstance(bg, tuple) and bg and bg[0] in ('v', 'h'):
        g = _fill_img(bg, w, h); m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=255); im.paste(g, (0, 0), m)
    else:
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius, fill=C(bg), outline=C(border) if border else None, width=4 if border else 0)
    if glossy:
        gl = Image.new('RGBA', (w, h // 2), (255, 255, 255, 50)); m = Image.new('L', (w, h // 2), 0)
        ImageDraw.Draw(m).rounded_rectangle([3, 3, w - 4, h // 2 + radius], radius, fill=255); im.paste(gl, (0, 0), m)
    im.alpha_composite(t, (px, py))
    return im

def marker(text, size=72, fg='#2e3238', mk='#fafa80', **kw):
    """黄色いマーカーの帯（四角）＋濃い文字"""
    return box(text, size, bg=mk, fg=fg, padx=int(size * 0.14), pady=int(size * 0.02), **kw)

def navy(text, size=64, fg='#ffffff', em='#fcff00', italic=0.14):
    """紺の座布団に白い斜体（強調は黄）"""
    return box(text, size, bg='#000268', fg=fg, tagfill={'y': C(em)}, italic=italic, radius=int(size * 0.12),
               padx=int(size * 0.22), pady=int(size * 0.08))

def sub(text, size=44, em='#ff3030'):
    """下の字幕：黒い四角に白文字（強調は赤）"""
    return box(text, size, bg='#000000', fg='#ffffff', tagfill={'r': C(em), 'y': C('#fcff00')}, padx=10, pady=2, wght=800)

def pill_label(text, icon=None, size=62, h=160):
    """左上の章ラベル：紫→ピンク→紫の横グラデの角丸＋左に丸いロゴ"""
    t = deco(text, size, fill=(255, 255, 255), wght=800, pad=2)
    d = h + 20 if icon is not None else 0
    w = d // 2 + t.width + int(size * 1.6)
    im = Image.new('RGBA', (w + d // 2, h + 20), (0, 0, 0, 0))
    g = _fill_img(('h', [(0, '#9152dc'), (0.5, '#dc79e8'), (1, '#9352d9')]), w, h)
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=255)
    im.paste(g, (d // 2, 10), m)
    im.alpha_composite(t, (d // 2 + d // 2 + int(size * 0.5), 10 + (h - t.height) // 2))
    if icon is not None:
        ic = icon.resize((d, d), Image.LANCZOS); im.alpha_composite(ic, (0, 0))
    return im

# ---------------- 印・アイコン ----------------
_CP = None
def _codepoints():
    global _CP
    if _CP is None:
        _CP = {}
        for ln in open(os.path.join(anim.FD, 'MaterialSymbolsRounded.codepoints')):
            k, v = ln.split(); _CP[k] = chr(int(v, 16))
    return _CP

@functools.lru_cache(None)
def _icon_font(size, fill=1, wght=500):
    f = ImageFont.truetype(os.path.join(anim.FD, 'MaterialSymbolsRounded.ttf'), size)
    try:
        axes = f.get_variation_axes(); vals = []
        for a in axes:
            nm = a.get('name', b'')
            nm = nm.decode() if isinstance(nm, bytes) else str(nm)
            if 'Fill' in nm or nm == 'FILL': vals.append(fill)
            elif 'Weight' in nm or nm == 'wght': vals.append(wght)
            elif 'Optical' in nm or nm == 'opsz': vals.append(48)
            else: vals.append(0)
        f.set_variation_by_axes(vals)
    except Exception:
        pass
    return f

def icon(name, size=120, color='#ffffff', fill=1, wght=500):
    ch = _codepoints()[name]; f = _icon_font(int(size * 1.0), fill, wght)
    im = Image.new('RGBA', (int(size * 1.3), int(size * 1.3)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((im.width / 2, im.height / 2), ch, font=f, fill=C(color), anchor='mm')
    bb = im.getbbox(); return im.crop(bb) if bb else im

def icon_circle(name, d=150, bg='#87868d', fg='#ffffff', k=0.58, shadow=False):
    im = Image.new('RGBA', (d * 2, d * 2), (0, 0, 0, 0)); ImageDraw.Draw(im).ellipse([0, 0, d * 2 - 1, d * 2 - 1], fill=C(bg))
    ic = icon(name, int(d * 2 * k), fg); im.alpha_composite(ic, ((d * 2 - ic.width) // 2, (d * 2 - ic.height) // 2))
    im = im.resize((d, d), Image.LANCZOS)
    if shadow: im, _ = anim.shadowed(im, off=(0, 5), blur=8, alpha=0.25, pad=16)
    return im

def check_blue(d=110):
    return icon_circle('check', d, bg='#276cb3', fg='#ffffff', k=0.66)

def verified(d=300):
    """青いギザギザの認証マーク"""
    s = d * 2; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    pts = []
    for k in range(48):
        r = s * (0.5 if k % 2 == 0 else 0.44); a = k * math.pi / 24
        pts.append((s / 2 + r * math.cos(a), s / 2 + r * math.sin(a)))
    dr.polygon(pts, fill=C('#4a90e2'))
    ic = icon('check', int(s * 0.62), '#ffffff', wght=700); im.alpha_composite(ic, ((s - ic.width) // 2, (s - ic.height) // 2))
    return im.resize((d, d), Image.LANCZOS)

def arrow(direction='down', length=90, width=60, color='#e02020'):
    """太い矢印（下・右）"""
    s = 4; L, Wd = length * s, width * s
    im = Image.new('RGBA', (Wd, L), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sw = Wd * 0.42; head = L * 0.5
    d.rectangle([(Wd - sw) / 2, 0, (Wd + sw) / 2, L - head + 2], fill=C(color))
    d.polygon([(0, L - head), (Wd, L - head), (Wd / 2, L)], fill=C(color))
    im = im.resize((width, length), Image.LANCZOS)
    if direction == 'right': im = im.rotate(90, expand=True)
    elif direction == 'up': im = im.rotate(180, expand=True)
    elif direction == 'left': im = im.rotate(-90, expand=True)
    return im

def big_x(d=200, color='#e82020', w=0.2):
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im); lw = int(s * w)
    m = lw // 2 + 4
    dr.line([(m, m), (s - m, s - m)], fill=C(color), width=lw); dr.line([(s - m, m), (m, s - m)], fill=C(color), width=lw)
    for x, y in [(m, m), (s - m, s - m), (s - m, m), (m, s - m)]: dr.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=C(color))
    return im.resize((d, d), Image.LANCZOS)

def bars_up(h=260):
    """右肩上がりの赤い棒グラフ＋ピンクの矢印（『売れる人』の印）"""
    s = 3; w = int(h * 1.25)
    im = Image.new('RGBA', (w * s, h * s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    bw = w * s * 0.14; gap = w * s * 0.1; x = w * s * 0.18
    for k, fr in enumerate([0.18, 0.42, 0.64, 0.92]):
        bh = h * s * 0.78 * fr; d.rectangle([x, h * s - bh, x + bw, h * s], fill=C('#ec2027')); x += bw + gap
    d.line([(w * s * 0.02, h * s * 0.55), (w * s * 0.42, h * s * 0.08)], fill=C('#f0307a'), width=int(h * s * 0.05))
    d.polygon([(w * s * 0.47, h * s * 0.0), (w * s * 0.33, h * s * 0.07), (w * s * 0.44, h * s * 0.17)], fill=C('#f0307a'))
    im = im.resize((w, h), Image.LANCZOS)
    sh, _ = anim.shadowed(im, off=(3, 4), blur=4, alpha=0.3, pad=12); return sh

# ---------------- SNS のロゴ（自前で描く・公式素材は使わない） ----------------
def logo_instagram(d=230):
    return anim.insta_glyph(d, radius_ratio=0.27)

def logo_youtube(w=260):
    h = int(w * 0.7); s = 3
    im = Image.new('RGBA', (w * s, h * s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], int(h * s * 0.28), fill=C('#ff0000'))
    cx, cy = w * s / 2, h * s / 2; r = h * s * 0.22
    d.polygon([(cx - r * 0.8, cy - r), (cx - r * 0.8, cy + r), (cx + r * 1.0, cy)], fill=(255, 255, 255))
    return im.resize((w, h), Image.LANCZOS)

def _note(s, col):
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = int(s * 0.17)
    d.ellipse([s * 0.12, s * 0.5, s * 0.52, s * 0.9], outline=col, width=lw)
    d.rectangle([s * 0.52 - lw, s * 0.08, s * 0.52, s * 0.72], fill=col)
    d.arc([s * 0.52 - lw, s * -0.22, s * 0.92, s * 0.3], 90, 180, fill=col, width=lw)
    return im

def logo_tiktok(d=230):
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    a = _note(s, C('#25f4ee')); b = _note(s, C('#fe2c55')); k = _note(s, C('#111111'))
    o = int(s * 0.02)
    im.alpha_composite(a, (-o, -o)); im.alpha_composite(b, (o, o)); im.alpha_composite(k, (0, 0))
    return im.resize((d, d), Image.LANCZOS)

def logo_x(d=200, color='#000000'):
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    c = C(color); m = s * 0.06
    # 太い斜め（白抜きの細い線で縁取り）＋細い斜め
    t = s * 0.2
    poly = [(m, m), (m + t, m), (s - m, s - m), (s - m - t, s - m)]
    dr.polygon(poly, fill=c)
    inner = [(m + s * 0.05, m + s * 0.035), (m + t - s * 0.03, m + s * 0.035), (s - m - s * 0.05, s - m - s * 0.035), (s - m - t + s * 0.03, s - m - s * 0.035)]
    dr.polygon(inner, fill=(0, 0, 0, 0))
    dr.line([(s - m - s * 0.02, m), (m + s * 0.02, s - m)], fill=c, width=int(s * 0.06))
    return im.resize((d, d), Image.LANCZOS)

def logo_line(d=200):
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, s - 1, s - 1], int(s * 0.24), fill=C('#06c755'))
    dr.ellipse([s * 0.14, s * 0.2, s * 0.86, s * 0.72], fill=(255, 255, 255))
    dr.polygon([(s * 0.36, s * 0.66), (s * 0.5, s * 0.66), (s * 0.34, s * 0.82)], fill=(255, 255, 255))
    f = font(int(s * 0.17), 900); dr.text((s / 2, s * 0.46), 'LINE', font=f, fill=C('#06c755'), anchor='mm')
    return im.resize((d, d), Image.LANCZOS)

def tile(img, d, bg, r=0.22):
    """アイコンを角丸の板に入れる（ロゴの中の小さな SNS 印）"""
    s = d * 2; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); ImageDraw.Draw(im).rounded_rectangle([0, 0, s - 1, s - 1], int(s * r), fill=C(bg))
    ic = img.copy(); ic.thumbnail((int(s * 0.7), int(s * 0.7)), Image.LANCZOS)
    im.alpha_composite(ic, ((s - ic.width) // 2, (s - ic.height) // 2)); return im.resize((d, d), Image.LANCZOS)

# ---------------- 右下の丸いロゴ（座る男の線画＋SNSの印） ----------------
@functools.lru_cache(None)
def mascot_line(color=(30, 30, 30), width_px=None):
    """白地の線画 → 線だけ（透明背景）"""
    src = Image.open(os.path.join(anim.BASE, 'assets', 'v1_mascot_line.png')).convert('L')
    a = src.point(lambda v: 255 - v).point(lambda v: 0 if v < 40 else min(255, int(v * 1.4)))
    im = Image.new('RGBA', src.size, tuple(color) + (255,)); im.putalpha(a)
    return im.crop(im.getbbox())

@functools.lru_cache(None)
def mascot_fill():
    """線画の内側を白く塗った版（ロゴ用）"""
    src = Image.open(os.path.join(anim.BASE, 'assets', 'v1_mascot_line.png')).convert('L')
    lines = src.point(lambda v: 255 if v < 128 else 0)
    flood = lines.copy(); ImageDraw.floodfill(flood, (2, 2), 128)
    inside = flood.point(lambda v: 255 if v == 0 else 0)
    im = Image.new('RGBA', src.size, (0, 0, 0, 0))
    im.paste(Image.new('RGBA', src.size, (255, 255, 255, 255)), (0, 0), inside.filter(ImageFilter.MaxFilter(5)))
    blk = Image.new('RGBA', src.size, (25, 25, 25, 255)); im.paste(blk, (0, 0), lines.filter(ImageFilter.MaxFilter(5)))
    return im.crop(lines.getbbox())

@functools.lru_cache(None)
def ring_logo(d=360, ring=12):
    s = d * 2; R = ring * 2
    g = lin_grad(s, s, [(0, C('#f9a03f')), (0.45, C('#e1306c')), (1, C('#8a3ab9'))])
    m = Image.new('L', (s, s), 0); ImageDraw.Draw(m).ellipse([0, 0, s - 1, s - 1], fill=255)
    out = Image.new('RGBA', (s, s), (0, 0, 0, 0)); out.paste(g, (0, 0), m)
    inner = Image.new('L', (s, s), 0); ImageDraw.Draw(inner).ellipse([R, R, s - 1 - R, s - 1 - R], fill=255)
    bgc = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    bgc.paste(lin_grad(s, s, [(0, C('#a15ae8')), (0.6, C('#6a5ad8')), (1, C('#3d63c9'))]), (0, 0))
    lay = Image.new('RGBA', (s, s), (0, 0, 0, 0)); lay.paste(Image.new('RGBA', (s, s), (250, 250, 252, 255)), (0, 0))
    # 上半分は紫の斜めの帯、下は白
    band = Image.new('L', (s, s), 0); ImageDraw.Draw(band).polygon([(0, 0), (s, 0), (s, s * 0.62), (0, s * 0.9)], fill=255)
    lay.paste(bgc, (0, 0), band)
    out.paste(lay, (0, 0), inner)
    fig = mascot_fill(); fig = fit(fig, h=int(s * 0.78))
    tiles = [(tile(logo_youtube(200), int(s * 0.17), '#ffffff'), (0.12, 0.33)), (tile(logo_instagram(200), int(s * 0.17), '#ffffff'), (0.1, 0.58)),
             (tile(logo_line(200), int(s * 0.17), '#06c755', 0.5), (0.6, 0.1)), (tile(logo_tiktok(200), int(s * 0.17), '#111111'), (0.7, 0.33)),
             (tile(logo_x(200, '#ffffff'), int(s * 0.17), '#111111'), (0.72, 0.56))]
    lay2 = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    lay2.alpha_composite(fig, ((s - fig.width) // 2 + int(s * 0.02), int(s * 0.17)))
    for im, (fx, fy) in tiles:
        im2 = im.rotate(-8 if fx > 0.5 else 8, resample=Image.BICUBIC, expand=True); lay2.alpha_composite(im2, (int(s * fx), int(s * fy)))
    lay2.putalpha(ImageChops.multiply(lay2.getchannel('A'), inner))
    out.alpha_composite(lay2)
    return out.resize((d, d), Image.LANCZOS)

# ---------------- 暗い告知の地 ----------------
@functools.lru_cache(None)
def dark_bg(figure=True, fig_alpha=0.32, cx=0.42, cy=0.62, fig_h=0.74, fig_x=0.56):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * cx) / W) ** 2 + ((yy - H * cy) / H * 0.9) ** 2)
    v = np.clip(1 - r / 0.75, 0, 1) ** 1.6
    base = np.array([18, 20, 28], np.float32); hi = np.array([92, 98, 118], np.float32)
    arr = base[None, None] + (hi - base)[None, None] * v[..., None]
    im = Image.fromarray(arr.astype(np.uint8), 'RGB').convert('RGBA')
    if figure:
        f = mascot_line((150, 156, 170)); f = fit(f, h=int(H * fig_h))
        im.alpha_composite(with_alpha(f, fig_alpha), (int(W * fig_x - f.width * 0.5), int(H * 0.98 - f.height)))
    return im

def header_promo(lines=('YouTube全10ジャンル チャレンジ企画', '4月上旬開催予定'), size=64):
    return deco('\n'.join(lines), size, fill=C('#3f4a66'), wght=900, italic=0.16, line_gap=0.02, strokes=[(3, '#1a1d26')])

def neon(text, size=260, color='#ff4a4a', glow='#ff2020'):
    """『重大告知』型：赤い太字が光る"""
    return deco(text, size, fill=C(color), glow=(20, glow, 1.9))

def white_glow(text, size=96, tagfill=None, italic=0.12):
    """暗い地の白い太字（ふち光る）。強調は <y>黄</y>"""
    return deco(text, size, fill=(255, 255, 255), tagfill=tagfill or {'y': C('#fcff00')}, glow=(10, '#ffffff', 0.9),
                strokes=[(3, '#202020')], italic=italic)

def red_neon_lines(text, size=96):
    return deco(text, size, fill=(255, 255, 255), strokes=[(5, '#ff3838')], glow=(16, '#ff2020', 1.6), line_gap=0.18)

def genre_pill(text, w=380, h=74, size=44):
    t = deco(text, size, fill=(255, 255, 255), tagfill={'s': (255, 255, 255)}, pad=2, wght=900, italic=0.1, shadow=(2, 3, 2, 0.4))
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    g = _fill_img(('v', [(0, '#c94d55'), (0.5, '#ad3440'), (1, '#8f2230')]), w, h)
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], int(h * 0.32), fill=255)
    im.paste(g, (0, 0), m)
    if t.width > w - 20: t = fit(t, w=w - 24)
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
    sh, _ = anim.shadowed(im, off=(0, 6), blur=8, alpha=0.5, pad=16)
    return sh

def cloud(text, w=380, h=230, size=34, fg='#fcff00'):
    """考えごとの雲（黒地・白い縁・黄文字）"""
    s = 2; im = Image.new('RGBA', (w * s, h * s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    blobs = [(0.5, 0.5, 0.42, 0.36), (0.22, 0.45, 0.2, 0.26), (0.78, 0.45, 0.2, 0.26), (0.35, 0.22, 0.2, 0.2), (0.62, 0.2, 0.2, 0.2),
             (0.35, 0.75, 0.2, 0.2), (0.65, 0.76, 0.2, 0.2)]
    m = Image.new('L', im.size, 0); dm = ImageDraw.Draw(m)
    for cx, cy, rx, ry in blobs: dm.ellipse([(cx - rx) * w * s, (cy - ry) * h * s, (cx + rx) * w * s, (cy + ry) * h * s], fill=255)
    edge = m.filter(ImageFilter.MaxFilter(13))
    im.paste(Image.new('RGBA', im.size, (255, 255, 255, 255)), (0, 0), edge)
    im.paste(Image.new('RGBA', im.size, (12, 12, 14, 255)), (0, 0), m)
    im = im.resize((w, h), Image.LANCZOS)
    t = deco(text, size, fill=C(fg), wght=900, pad=2, line_gap=0.05)
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2))
    g = im.filter(ImageFilter.GaussianBlur(6)); out = Image.new('RGBA', im.size, (0, 0, 0, 0)); out.alpha_composite(with_alpha(g, 0.6)); out.alpha_composite(im)
    return out

def thinker(h=520, color=(255, 255, 255)):
    """白いピクトの考える人（暗い地）。assets/v1_pict_thinker.png（黒い塗り）を白に替えて光らせる"""
    src = Image.open(os.path.join(anim.BASE, 'assets', 'v1_pict_thinker.png')).convert('L')
    a = src.point(lambda v: 255 if v < 100 else 0)
    im = Image.new('RGBA', src.size, tuple(color) + (255,)); im.putalpha(a); im = im.crop(a.getbbox()); im = fit(im, h=h)
    g = im.filter(ImageFilter.GaussianBlur(16)); out = Image.new('RGBA', (im.width + 80, im.height + 80), (0, 0, 0, 0))
    out.alpha_composite(with_alpha(g, 0.8), (40, 40)); out.alpha_composite(im, (40, 40)); return out

def day_cards(n=10, w=150, h=96):
    """Day1〜Day10 の青灰色のカード（2段）"""
    cols = 5; gap = 34
    im = Image.new('RGBA', (cols * w + (cols - 1) * gap + 30, 2 * h + gap + 30), (0, 0, 0, 0))
    for k in range(n):
        x = (k % cols) * (w + gap) + 15; y = (k // cols) * (h + gap) + 10
        c = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        g = _fill_img(('v', [(0, '#c9d3e6'), (1, '#8e9bbd')]), w, h); m = Image.new('L', (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 14, fill=255); c.paste(g, (0, 0), m)
        ImageDraw.Draw(c).rectangle([0, 0, w, 30], fill=None)
        ImageDraw.Draw(c).rectangle([0, int(h * 0.3), w, int(h * 0.3) + 2], fill=(235, 240, 250))
        f = font(int(h * 0.2), 900); ImageDraw.Draw(c).text((w / 2, h * 0.16), 'Day%d' % (k + 1), font=f, fill=(255, 255, 255), anchor='mm', stroke_width=2, stroke_fill=(110, 120, 150))
        sh, _ = anim.shadowed(c, off=(0, 6), blur=6, alpha=0.45, pad=10); im.alpha_composite(sh, (x - 10, y - 10))
    return im

# ---------------- スマホと X の投稿（自前の画面） ----------------
def phone_frame(w=760, h=1500, screen=None):
    s = 1; im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], int(w * 0.14), fill=(18, 18, 20), outline=(70, 70, 76), width=6)
    sx, sy = int(w * 0.04), int(w * 0.04)
    sw, sh_ = w - sx * 2, h - sy * 2
    if screen is not None:
        scr = ImageOps.fit(screen, (sw, sh_), centering=(0.5, 0.0)) if screen.height < sh_ else screen.crop((0, 0, sw, sh_))
        m = Image.new('L', (sw, sh_), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh_ - 1], int(w * 0.11), fill=255)
        im.paste(scr, (sx, sy), m)
    d.rounded_rectangle([w * 0.33, sy, w * 0.67, sy + w * 0.07], int(w * 0.035), fill=(18, 18, 20))
    return im

def x_post(lines, w=700, name='手本の作者＠YouTube動画1億', handle='@tehon_sns', title='【SNS情報発信の本質】', size=27):
    """X の投稿画面（文字だけの白い画面）。lines は本文の行。戻り値 (画像, 行ごとの (y0,y1))"""
    pad = 34; f = font(size, 500); fb = font(size, 700)
    rowsy = []; y = 150
    im = Image.new('RGBA', (w, 2400), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.ellipse([pad, 70, pad + 60, 130], fill=(230, 230, 236)); d.text((pad + 74, 74), name, font=font(24, 700), fill=(20, 20, 20))
    d.ellipse([pad + 74 + font(24, 700).getlength(name) + 8, 78, pad + 74 + font(24, 700).getlength(name) + 30, 100], fill=(29, 155, 240))
    d.text((pad + 74, 104), handle, font=font(22, 400), fill=(110, 118, 125))
    d.text((w - pad - 90, 70), 'X.com', font=font(26, 700), fill=(20, 20, 20))
    d.text((pad, y), title, font=fb, fill=(20, 20, 20)); y += int(size * 2.1)
    for ln in lines:
        if ln == '':
            y += int(size * 0.9); rowsy.append((y, y)); continue
        # 折り返し
        cur = ''; seg = []
        for ch in ln:
            if f.getlength(cur + ch) > w - pad * 2: seg.append(cur); cur = ch
            else: cur += ch
        seg.append(cur); y0 = y
        for sgm in seg: d.text((pad, y), sgm, font=f, fill=(30, 30, 30)); y += int(size * 1.55)
        rowsy.append((y0 - 6, y - 4))
    return im.crop((0, 0, w, y + 200)), rowsy

def highlight_rows(post, rows, color=(120, 200, 240), alpha=0.55):
    im = post.copy(); ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    y0, y1 = rows[0][0], rows[-1][1]
    d.rounded_rectangle([18, y0 - 6, im.width - 18, y1 + 6], 12, fill=color + (int(255 * alpha),))
    return Image.alpha_composite(im, ov)

# ---------------- 図：中心＋まわりの印（『1番大事なところ』） ----------------
def hub(center='favorite', around=('thumb_up', 'smartphone', 'smart_display', 'settings', 'tag', 'photo_library'), D=300, d=150, R=420):
    w = int(R * 2 + d + 40); h = int(R * 1.05 + d + 40)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    cx, cy = w // 2, h // 2
    ang = [155, 180, 205, 25, 0, -25]
    pos = []
    for k, a in enumerate(ang[:len(around)]):
        r = R if a in (180, 0) else R * 0.72
        x = cx + r * math.cos(math.radians(a)); y = cy - r * math.sin(math.radians(a)) * 0.95
        pos.append((x, y))
        dr.line([(cx, cy), (x, y)], fill=(110, 110, 118), width=6)
    return im, pos, (cx, cy)

def atom_heart(d=300):
    """赤い丸に白い原子＋ハート（本質の印）"""
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, s - 1, s - 1], fill=C('#f45150'))
    lw = int(s * 0.025)
    for a in (0, 60, -60):
        e = Image.new('RGBA', (s, s), (0, 0, 0, 0)); ImageDraw.Draw(e).ellipse([s * 0.12, s * 0.36, s * 0.88, s * 0.64], outline=(255, 255, 255), width=lw)
        im.alpha_composite(e.rotate(a, resample=Image.BICUBIC))
    hi = icon('favorite', int(s * 0.3), '#ffffff'); im.alpha_composite(hi, ((s - hi.width) // 2, (s - hi.height) // 2 + int(s * 0.01)))
    return im.resize((d, d), Image.LANCZOS)

def atom_line(d=90, color='#ffffff'):
    s = d * 3; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); lw = int(s * 0.05)
    for a in (0, 60, -60):
        e = Image.new('RGBA', (s, s), (0, 0, 0, 0)); ImageDraw.Draw(e).ellipse([s * 0.05, s * 0.33, s * 0.95, s * 0.67], outline=C(color), width=lw)
        im.alpha_composite(e.rotate(a, resample=Image.BICUBIC))
    hi = icon('favorite', int(s * 0.3), color); im.alpha_composite(hi, ((s - hi.width) // 2, (s - hi.height) // 2))
    return im.resize((d, d), Image.LANCZOS)

# ---------------- 光の粒（キラキラ）：時間で動く部品 ----------------
class Sparkle(anim.Elem):
    """横に流れる光の粒。実績の数字の下に敷く"""
    def __init__(self, ts, x, y, w=1300, h=220, n=140, color=(255, 236, 190), seed=3, **kw):
        super().__init__(ts, anim='none', **kw); self.box = (x, y, w, h); self.n = n; self.color = color
        rs = np.random.RandomState(seed)
        self.p = np.c_[rs.rand(n), rs.rand(n), rs.rand(n) * 0.9 + 0.1, rs.rand(n) * 6.28, rs.rand(n)]
    def build(self): return None
    def draw(self, cv, t):
        if t < self.ts or (self.te is not None and t >= self.te): return
        x, y, w, h = self.box; k = t - self.ts
        lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        for px, py, sz, ph, sp in self.p:
            xx = ((px + k * (0.05 + 0.08 * sp)) % 1.0) * w
            yy = h * (0.5 + (py - 0.5) * (0.35 + 0.6 * abs(math.sin(px * 3.1)))) + math.sin(k * 2 + ph) * 6
            a = 0.5 + 0.5 * math.sin(k * 5 + ph)
            r = 1.5 + sz * 4.5
            d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=self.color + (int(200 * a),))
        g = lay.filter(ImageFilter.GaussianBlur(3)); lay = Image.alpha_composite(g, lay)
        fade = clamp(k / 0.4)
        if self.te is not None: fade *= clamp((self.te - t) / 0.3)
        paste_safe(cv, with_alpha(lay, fade), x, y)

class Flare(anim.Elem):
    """光の筋が横切る（題名・実績の出に合わせて）"""
    def __init__(self, ts, y, dur=0.8, color=(255, 240, 200), **kw):
        super().__init__(ts, anim='none', **kw); self.yy = y; self.d = dur; self.color = color
    def build(self): return None
    def draw(self, cv, t):
        k = (t - self.ts) / self.d
        if not (0 <= k <= 1): return
        x = int(-400 + (W + 800) * ease_in_out(k))
        lay = Image.new('RGBA', (900, 300), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        d.ellipse([0, 130, 900, 170], fill=self.color + (140,)); d.ellipse([400, 100, 500, 200], fill=(255, 255, 255, 230))
        lay = lay.filter(ImageFilter.GaussianBlur(14))
        a = math.sin(math.pi * k)
        paste_safe(cv, with_alpha(lay, a), x - 450, self.yy - 150)

# ---------------- 出方の追加：ぼかし→くっきり（告知の文字） ----------------
def install_anims():
    E = anim.Elem
    old = E.animate
    def animate(self, cv, im, x, y, p, a_out):
        a = self.anim
        if a == 'blur':      # ぼけた状態から少し大きく→くっきり
            r = 16 * (1 - ease_out(p)); s = 1.0 + 0.06 * (1 - ease_out(p))
            im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
            if r > 0.5: im2 = im2.filter(ImageFilter.GaussianBlur(r))
            paste_safe(cv, with_alpha(im2, ease_out(p) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
        elif a == 'slam':    # 大きく上から落ちて止まる（ドンの文字）
            s = 1.0 + 0.9 * (1 - ease_out(p)) ** 2
            im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
            paste_safe(cv, with_alpha(im2, clamp(p * 2.5) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
        elif a == 'wipeblur':  # 左からぼかしつきで出る
            w = int(im.width * ease_in_out(p))
            if w > 0:
                c = im.crop((0, 0, w, im.height)); m = c.getchannel('A')
                edge = Image.new('L', c.size, 255); ImageDraw.Draw(edge).rectangle([max(0, w - 60), 0, w, im.height], fill=120)
                c.putalpha(ImageChops.multiply(m, edge.filter(ImageFilter.GaussianBlur(12))))
                paste_safe(cv, with_alpha(c, a_out), x, y)
        elif a == 'drop':    # 少し上から落ちる＋弾む
            dy = -50 * (1 - back_out(p, 2.2)); paste_safe(cv, with_alpha(im, clamp(p * 3) * a_out), x, int(y + dy))
        elif a == 'stamp':   # 大きく→ぴたっと（はんこ）
            s = 1 + 0.5 * (1 - back_out(p, 1.4))
            im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
            paste_safe(cv, with_alpha(im2, clamp(p * 3) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
        elif a == 'none':
            paste_safe(cv, with_alpha(im, a_out), x, y)
        else:
            old(self, cv, im, x, y, p, a_out)
    E.animate = animate
install_anims()

def silhouette_white(name, h=300, color=(255, 255, 255)):
    """灰色のシルエット素材を白（任意の色）一色にする（暗い地で使う）"""
    im = fit(asset(name), h=h); a = im.getchannel('A')
    out = Image.new('RGBA', im.size, tuple(color) + (255,)); out.putalpha(a); return out

def wave_lines(w=300, h=200, color='#4aa8d8'):
    """音の波形のような縦線（『伸びない』の沈んだ空気）"""
    import random
    rs = random.Random(3); im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for k in range(0, w, 12):
        hh = rs.uniform(0.35, 1.0) * h; d.line([(k, 0), (k, hh)], fill=C(color), width=3)
    return im

def x_table(w=720, rows=((56, 4, 52), (61, 12, 49), (59, 6, 53), (128, 9, 119), (64, 4, 60), (53, 4, 49), (89, 5, 84), (72, 7, 66))):
    """投稿に付いた画像（日ごとの数字の表）。数字は自前の例"""
    rh = 64; im = Image.new('RGBA', (w, rh * len(rows) + 20), (248, 248, 250, 255)); d = ImageDraw.Draw(im)
    f = font(28, 600)
    for k, (a, b, c) in enumerate(rows):
        y = 10 + k * rh; d.line([(20, y + rh), (w - 20, y + rh)], fill=(225, 225, 230), width=2)
        d.text((70, y + 16), str(a), font=f, fill=(60, 60, 60)); d.text((300, y + 16), str(b), font=f, fill=(60, 60, 60))
        d.rounded_rectangle([340, y + 14, 420, y + 50], 6, outline=(170, 170, 175), width=2); d.text((352, y + 17), 'リスト', font=font(22, 600), fill=(90, 90, 90))
        d.text((w - 130, y + 16), '+ %d' % c, font=font(28, 800), fill=(30, 140, 80))
    d.line([(50, 0), (50, im.height)], fill=(220, 50, 50), width=3); d.line([(120, 0), (120, im.height)], fill=(220, 50, 50), width=2)
    return im

def x_footer(w=720):
    h = 210; im = Image.new('RGBA', (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.line([(0, 0), (w, 0)], fill=(230, 230, 235), width=2)
    d.rounded_rectangle([40, 24, w - 40, 84], 30, fill=(240, 241, 244)); d.text((70, 38), '返信をポスト', font=font(26, 500), fill=(120, 120, 125))
    for k, nm in enumerate(['home', 'search', 'cached', 'notifications', 'mail']):
        ic = icon(nm, 46, '#333333', fill=0); x = int(w * (k + 0.5) / 5) - ic.width // 2; im.alpha_composite(ic, (x, 120))
    return im
