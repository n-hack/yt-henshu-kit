# 期1（手本の作者さん 2026-06〜08 の装飾多め・eiQaTiAwLVg ほか）の字の形と部品（10/19 作業AI・エバーVSL頭3分）
#   頭3分を6秒おき・頭30秒を1秒おきに見て写した形：薄い灰の地に線画の大きな透かし／黄のマーカー見出し／緑の吹き出し（左上に丸いアイコン）／
#   赤の帯に白い斜体／白い縁の赤い明朝の大字／白い縁の青い斜体／紺の帯の小さい字幕／ピンクの丸札／青い丸のチェック／黒い人のアイコン＋灰の吹き出し／▼▼▼
import os, sys
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
from henshu import *
from riso_kata import MINCHO, GOTH, obi, kin, hako, kuro, batsu, KIN_FILL, kazu
import numpy as np

def _light():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * 0.42) / H) ** 2); v = np.clip(1 - r / 0.8, 0, 1)
    lo = np.array([214, 214, 214], np.float32); hi = np.array([243, 243, 243], np.float32)
    im = Image.fromarray((lo + (hi - lo) * v[..., None]).astype(np.uint8), 'RGB').convert('RGBA')
    f = kit.mascot_line((255, 255, 255)); f = fit(f, h=int(H * 0.95)); a = f.split()[-1].point(lambda x: int(x * 0.85)); f.putalpha(a)
    im.alpha_composite(f, (int(W * 0.5 - f.width * 0.5), int(H * 1.0 - f.height)))
    g = kit.mascot_line((150, 150, 150)); g = fit(g, h=int(H * 0.95)); a = g.split()[-1].point(lambda x: int(x * 0.16)); g.putalpha(a)
    im.alpha_composite(g, (int(W * 0.5 - g.width * 0.5) + 3, int(H * 1.0 - g.height) + 3))
    return im
LIGHT = None  # 下で作り直す
def _dark():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * 0.5) / H) ** 2); v = np.clip(1 - r / 0.75, 0, 1)
    lo = np.array([8, 8, 10], np.float32); hi = np.array([58, 58, 62], np.float32)
    im = Image.fromarray((lo + (hi - lo) * v[..., None]).astype(np.uint8), 'RGB').convert('RGBA')
    f = kit.mascot_line((255, 255, 255)); f = fit(f, h=int(H * 0.95)); a = f.split()[-1].point(lambda x: int(x * 0.10)); f.putalpha(a)
    im.alpha_composite(f, (int(W * 0.5 - f.width * 0.5), int(H * 1.0 - f.height))); return im
DARK = None
# 7版目（10/19 04:0x）：背景の座る男の線画は手本の作者さんのロゴの写し（門のルール6）→ 外して、地の明るさだけにする
def _plain(lo, hi, cy, rr):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * 0.5) / W) ** 2 + ((yy - H * cy) / H) ** 2); v = np.clip(1 - r / rr, 0, 1)
    lo = np.array(lo, np.float32); hi = np.array(hi, np.float32)
    return Image.fromarray((lo + (hi - lo) * v[..., None]).astype(np.uint8), 'RGB').convert('RGBA')
# 地の線画（自社キャラの頭＋線の体）は 10/21 に描く元ごと外した（依頼主 10/20 23:45「この棒人間みたいなやつ…一生使わないで」・kinshi/chara-boujin）
def _bg(lo, hi, cy, rr, main, ma, shadow=None, sa=0.0):
    im = _plain(lo, hi, cy, rr); hh = int(H * 0.9)
    return im   # 地の線画（自社キャラの頭＋線の体）は入れない（依頼主 10/20 23:45「この棒人間みたいなやつ…一生使わないで」・kinshi/chara-boujin）
LIGHT = _bg([214, 214, 214], [243, 243, 243], 0.42, 0.8, (255, 255, 255), 0.85, (150, 150, 150), 0.16)
DARK = _bg([8, 8, 10], [58, 58, 62], 0.5, 0.75, (255, 255, 255), 0.10)


def _shadow(im, off=(0, 6), blur=8, alpha=0.35):
    import anim as _a
    return _a.shadowed(im, off=off, blur=blur, alpha=alpha)[0]

def midashi(text, size=60):
    """黄のマーカー見出し（字は黒の太ゴシック・マーカーは字の下半分）"""
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#111111'), pad=4)
    w, h = t.width + 24, t.height + 4
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, int(h * 0.5), w - 1, h - 4], fill=kit.C('#fff200'))
    im.alpha_composite(t, (12, 0)); return im

def midashi_kurai(text, size=60):
    """暗い地の上の見出し：黄の帯を字の高さ全部にかけ、字は黒のまま（手本の黄色い札の形）。帯が下半分だけだと上半分が地に沈む（10/20 vhm8 10版目 s007・作業AI）"""
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#111111'), pad=4)
    w, h = t.width + 24, t.height + 4
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], fill=kit.C('#fff200'))
    im.alpha_composite(t, (12, 0)); return im

def avatar(d=110):
    """吹き出しの左上の丸いアイコン（白い丸・赤い縁・中に線画）"""
    s = d * 2; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse([4, 4, s - 5, s - 5], fill=(255, 255, 255, 255), outline=(220, 40, 40, 255), width=max(4, s // 26))
    f = kit.mascot_line((60, 60, 60)); f = fit(f, h=int(s * 0.62)); im.alpha_composite(f, ((s - f.width) // 2, int(s * 0.2)))
    return im.resize((d, d), Image.LANCZOS)

def fuki(text, size=52, bg='#0b8a07', fg='#ffffff', av=True, tail='lt'):
    """緑（や灰）の吹き出し。左上にしっぽ、av=True で丸いアイコンを左上に付ける"""
    t = kit.deco(text, size, name=GOTH, fill=kit.C(fg), pad=2, align='left', tagfill={'y': kit.C('#fff200'), 'r': kit.C('#e01010')})
    px, py = int(size * 0.5), int(size * 0.32)
    bw, bh = t.width + px * 2, t.height + py * 2
    ax = int(size * 2.1) if av else 0; ay = int(size * 1.0) if av else int(size * 0.4)
    im = Image.new('RGBA', (bw + ax + 10, bh + ay + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([ax, ay, ax + bw, ay + bh], fill=kit.C(bg))
    tx = ax + int(size * 0.35)
    d.polygon([(tx, ay + 2), (tx, ay - int(size * 0.42)), (tx + int(size * 0.5), ay + 2)], fill=kit.C(bg))
    im.alpha_composite(t, (ax + px, ay + py))
    if av:
        a = avatar(int(size * 1.9)); im.alpha_composite(a, (0, 0))
    return _shadow(im, (3, 5), 6, 0.35)

def fuki_hai(text, size=46):
    return fuki(text, size, bg='#5e5e5e', av=False)

def obi_aka(text, size=84, w=None):
    """赤の帯に白い斜体（黒い細い縁）"""
    t = kit.deco(text, size, name=GOTH, fill=('v', [(0, '#ffffff'), (1, '#fff3a0')]), strokes=[(4, '#5a0000')], italic=0.14, pad=6)
    bw = w or t.width + 40
    if t.width > bw - 60: r = (bw - 60) / t.width; t = t.resize((int(t.width * r), int(t.height * r)), Image.LANCZOS)   # 帯の中に字を収める
    bh = t.height + 8
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, bw - 1, bh - 1], fill=kit.C('#e3141b'))
    im.alpha_composite(t, ((bw - t.width) // 2, 4)); return _shadow(im, (0, 5), 6, 0.3)

def oaka(text, size=120):
    """白い縁の赤い明朝の大字（斜体・黒い影）＝言い切り"""
    return kit.deco(text, size, name=MINCHO, fill=('v', [(0, '#ff7a4a'), (0.55, '#f01c10'), (1, '#b00000')]),
                    strokes=[(3, '#6a0000'), (12, '#ffffff')], shadow=(0, 8, 10, 0.55), italic=0.1)

def ao(text, size=86):
    """白い縁の青グラデの斜体（太ゴシック）"""
    return kit.deco(text, size, name=GOTH, fill=('v', [(0, '#8fd8ff'), (0.5, '#2b8de8'), (1, '#1450c0')]), strokes=[(9, '#ffffff')],
                    shadow=(0, 5, 6, 0.4), italic=0.14)

def kon(text, size=46):
    """紺の帯の小さい字幕（白・強調は黄）"""
    return kit.box(text, size, bg='#0b1478', fg='#ffffff', tagfill={'y': kit.C('#fff200')}, padx=int(size * 0.35), pady=int(size * 0.1), name=GOTH, wght=800)

def aka_box(text, size=80):
    """赤い四角に白い太字（大きな言い切りの札）"""
    b = kit.box(text, size, bg='#e3141b', fg='#ffffff', tagfill={'y': kit.C('#fff200')}, padx=int(size * 0.4), pady=int(size * 0.12), name=GOTH, italic=0.08)
    return _shadow(b, (0, 8), 10, 0.35)

def pink(text, d=160):
    s = d * 2; im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, s - 1, s - 1], fill=kit.C('#e8197a'))
    t = kit.deco(text, int(s * 0.2), name=GOTH, fill=kit.C('#ffffff'), pad=2)
    im.alpha_composite(t, ((s - t.width) // 2, (s - t.height) // 2)); return im.resize((d, d), Image.LANCZOS)

def check(text, size=56, col='#222222'):
    c = kit.check_blue(int(size * 1.05)); t = kit.deco(text, size, name=GOTH, fill=kit.C(col), pad=2, tagfill={'r': kit.C('#e01010')})
    im = Image.new('RGBA', (c.width + 14 + t.width, max(c.height, t.height)), (0, 0, 0, 0))
    im.alpha_composite(c, (0, (im.height - c.height) // 2)); im.alpha_composite(t, (c.width + 14, (im.height - t.height) // 2)); return im

def sankaku(n=6, size=34):
    return kit.deco('▼' * n, size, name=GOTH, fill=kit.C('#333333'), pad=2)

def tag(text, size=44, bg='#f39a1e'):
    return _shadow(kit.box(text, size, bg=bg, fg='#ffffff', padx=int(size * 0.4), pady=int(size * 0.12), name=GOTH, wght=800), (2, 4), 5, 0.3)

def ic(name, size=150, col='#111111'):
    return kit.icon(name, int(size * 1.5), col, fill=1, wght=600)

def hito_ic(size=170, col='#111111', name='person'):
    return ic(name, size, col)

def iclab(name, text, size=150, col='#111111', tsize=48):
    a = ic(name, size, col); b = kit.deco(text, tsize, name=GOTH, fill=kit.C('#222222'), pad=2)
    im = Image.new('RGBA', (max(a.width, b.width), a.height + b.height + 4), (0, 0, 0, 0))
    im.alpha_composite(a, ((im.width - a.width) // 2, 0)); im.alpha_composite(b, ((im.width - b.width) // 2, a.height + 4)); return im

def card3(icon, head, body, col, w=520, h=430):
    """比べる3つの札（同じ形・色違い）"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 24, fill=(255, 255, 255, 255), outline=kit.C(col), width=8)
    d.rounded_rectangle([0, 0, w - 1, 96], 24, fill=kit.C(col)); d.rectangle([0, 60, w - 1, 96], fill=kit.C(col))
    t = kit.deco(head, 50, name=GOTH, fill=kit.C('#ffffff'), pad=2); im.alpha_composite(t, ((w - t.width) // 2, (96 - t.height) // 2))
    a = ic(icon, 120, col); im.alpha_composite(a, ((w - a.width) // 2, 112))
    b = kit.deco(body, 44, name=GOTH, fill=kit.C('#222222'), pad=2, line_gap=0.2); im.alpha_composite(b, ((w - b.width) // 2, h - b.height - 22))
    return _shadow(im, (0, 8), 10, 0.25)

def waku(text, size=58, col='#e3141b', w=None):
    """白い箱に色の縁・色の字（ループ図の箱）"""
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#ffffff'), pad=2)   # 5版目：白抜きの箱→色で塗った箱（期1の赤・緑・青の札）
    bw = w or t.width + 60
    if t.width > bw - 50: r = (bw - 50) / t.width; t = t.resize((int(t.width * r), int(t.height * r)), Image.LANCZOS)   # 箱の中に字を収める（STEP2 がはみ出した・10/19）
    bh = t.height + 34
    im = Image.new('RGBA', (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], 18, fill=kit.C(col))
    im.alpha_composite(t, ((bw - t.width) // 2, (bh - t.height) // 2)); return _shadow(im, (0, 6), 8, 0.25)

def yaji(direction='right', length=120, width=70, color='#e3141b'):
    return kit.arrow(direction, length, width, color)

def label_aka(text, size=int(os.environ.get('LABEL_PX', '66'))):
    """左上の章の札（赤い斜めの帯・白字）＝常に出す"""
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#ffffff'), pad=2)
    w, h = t.width + 120, t.height + 22
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(0, 0), (w - 1, 0), (w - 44, h - 1), (0, h - 1)], fill=kit.C('#d0101a'))
    im.alpha_composite(t, (26, 9)); return im

def bars(vals, labels, cols, h=420, bw=150, gap=90, pad=50):
    """階段の棒（下から伸びる）。vals は 0〜1"""
    n = len(vals); w = n * bw + (n - 1) * gap
    w += 2 * pad; im = Image.new('RGBA', (w, h + 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for k, (v, lb, c) in enumerate(zip(vals, labels, cols)):
        x0 = pad + k * (bw + gap); y0 = int(h * (1 - v))
        d.rectangle([x0, y0, x0 + bw, h], fill=kit.C(c))
        t = kit.deco(lb, 40, name=GOTH, fill=kit.C('#222222'), pad=2); im.alpha_composite(t, (x0 + (bw - t.width) // 2, h + 8))
    d.line([(0, h), (w, h)], fill=(40, 40, 40, 255), width=5); return im

# 字の大きさ：期1の主な字の高さ 中央 95.5px（kata-ki1.tsv）。上の形は 1.3 倍して使う（10/19 1枚目の一覧で本物より小さかった）
import inspect as _insp, functools as _ft2
SC = 1.3
def _scaled(fn, default):
    @_ft2.wraps(fn)
    def w(text, size=default, *a, **k): return fn(text, int(size * SC), *a, **k)
    return w
for _n in ('midashi', 'fuki', 'obi_aka', 'oaka', 'ao', 'kon', 'aka_box', 'check', 'waku'):
    _f = globals()[_n]; _d = _insp.signature(_f).parameters['size'].default; globals()[_n] = _scaled(_f, _d)
# 3版目（埋まり方を本物の範囲へ）：色の座布団（緑の吹き出し・紺の字幕）を一回り大きく、赤の帯は画面の幅いっぱい
_fk, _kn, _oa = fuki, kon, obi_aka
def fuki(text, size=52, *a, **k): return _fk(text, int(size * 1.12), *a, **k)
def kon(text, size=46, *a, **k): return _kn(text, int(size * 1.15), *a, **k)
def obi_aka(text, size=84, w=None, *a, **k): return _oa(text, size, w=w or W, *a, **k)
def fuki_hai(text, size=46): return fuki(text, size, bg='#5e5e5e', av=False)
def kin_l(text, size=110):
    """明るい地に置く金の明朝（濃い茶の縁と影で読ませる）"""
    return kit.deco(text, int(size * SC), name=MINCHO, fill=KIN_FILL, strokes=[(5, '#5a3a00')], shadow=(4, 6, 10, 0.6), glow=(8, '#fff2b0', 0.8), italic=0.16)

# ---- 10月の4本（crlz・82Lv・mu6Y・zRXb）で見た形を足す（10/19）----
def card_hai(text, size=60):
    """薄い灰の角丸の札に黒の太字＋黄のマーカー（crlz「売れるYouTubeを作りましょう」）"""
    t = midashi(text, size)
    w, h = t.width + 80, t.height + 50
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 26, fill=(222, 222, 224, 255))
    im.alpha_composite(t, ((w - t.width) // 2, (h - t.height) // 2)); return _shadow(im, (0, 6), 10, 0.3)
def card_ao(text, size=60):
    """青の角丸の札に白い太字（crlz「ほとんどの人は」）。見やすさ 10/22：水色地×白字はコントラスト比2.2〜2.9（依頼主「視認性悪い」）→濃い青で4以上"""
    b = kit.box(text, int(size * SC), bg=('v', [(0, '#2a7fd0'), (1, '#1557a6')]), fg='#ffffff', radius=26, padx=50, pady=18, name=GOTH)
    return _shadow(b, (0, 6), 10, 0.3)
def card_kuro(text, size=48):
    """黒い角丸の小札に白字（アイコンの下の名札）"""
    return kit.box(text, int(size * SC), bg='#111111', fg='#ffffff', radius=8, padx=18, pady=6, name=GOTH, wght=800)
def icl(name, text, size=170, col='#111111'):
    """黒いピクトグラム＋下に黒字（10月の4本の図解）"""
    return iclab(name, text, size, col, tsize=int(44 * SC))
def hito_mure(n=10, red=1, size=110, cols=5):
    """人の群れ（灰）のうち red 人だけ赤（9割と1割など）"""
    a = ic('person', size, '#9a9a9a'); b = ic('person', size, '#e3141b')
    rows = (n + cols - 1) // cols; im = Image.new('RGBA', (a.width * cols, a.height * rows), (0, 0, 0, 0))
    for k in range(n):
        im.alpha_composite(b if k >= n - red else a, ((k % cols) * a.width, (k // cols) * a.height))
    return im
# 3版目（埋まり方を10月の4本の範囲へ）：10月の4本は黒いピクトグラムが大きい。アイコンを1.3倍にする
_ic0 = ic
def ic(name, size=150, col='#111111'): return _ic0(name, int(size * 1.3), col)
# 5版目（10/19 03:1x）：手本15本は「写真・実際の画面」と「図解」がうちより多い（e/shirushi.json）→ うちで作った差し込み動画（seminar-canva-douga/douga）の画面を窓に入れて見せる
GAMEN = os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/gamen')
def gamen(name, w=1180, label=None, lcol='#e3141b'):
    """うちの画面録画の1コマを、白い縁と上の帯つきの窓に入れる（label は窓の上の札）"""
    src = Image.open(os.path.join(GAMEN, name + '.png')).convert('RGB')
    iw = w - 24; ih = int(src.height * iw / src.width); src = src.resize((iw, ih), Image.LANCZOS)
    im = Image.new('RGBA', (w, ih + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, ih + 59], 18, fill=(255, 255, 255, 255), outline=(40, 40, 40, 255), width=3)
    d.rounded_rectangle([0, 0, w - 1, 44], 18, fill=(235, 235, 235, 255)); d.rectangle([0, 26, w - 1, 44], fill=(235, 235, 235, 255))
    for k, c in enumerate(('#ff5f57', '#febc2e', '#28c840')): d.ellipse([18 + k * 26, 14, 34 + k * 26, 30], fill=kit.C(c))
    im.paste(src, (12, 48))
    im = _shadow(im, (0, 8), 12, 0.35)
    if label:
        t = tag(label, 52, lcol); out = Image.new('RGBA', (max(im.width, t.width), im.height + t.height - 20), (0, 0, 0, 0))
        out.alpha_composite(im, ((out.width - im.width) // 2, t.height - 20)); out.alpha_composite(t, ((out.width - t.width) // 2, 0)); return out
    return im
def ninmure(names, size=150, cols=None, gap=20):
    """手本から切った人の絵の代わり：単色のピクトグラムを横に並べる（cols は色の並び）"""
    ims = [ic(n, size, (cols or ['#111111'])[k % len(cols or ['#111111'])]) for k, n in enumerate(names)]
    W2 = sum(i.width for i in ims) + gap * (len(ims) - 1); H2 = max(i.height for i in ims)
    im = Image.new('RGBA', (W2, H2), (0, 0, 0, 0)); x = 0
    for i in ims: im.alpha_composite(i, (x, H2 - i.height)); x += i.width + gap
    return im
def hyou(w=1700, h=520, rows=2, cols=2, col='#c8c8c8'):
    """選択肢を並べる表の枠（白地＋格子）"""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 20, fill=(255, 255, 255, 235), outline=kit.C(col), width=5)
    for c in range(1, cols): d.line([(w * c // cols, 14), (w * c // cols, h - 14)], fill=kit.C(col), width=4)
    for r in range(1, rows): d.line([(14, h * r // rows), (w - 14, h * r // rows)], fill=kit.C(col), width=4)
    return _shadow(im, (0, 6), 10, 0.25)
# 6版目（10/19 03:4x・依頼主「テロップがない！」）：話した言葉を全部、画面の下の紺の帯で出す（台本の字・1行20字まで・言葉の頭のコマで出す）
import json as _jj, bisect as _bs
_BRK = set('はがをにでともてしねよかへやの、。')
def _kiru(s, mx=20, mn=9):
    out = []
    while len(s) > mx:
        k = max([i + 1 for i in range(mn, mx) if s[i] in _BRK] or [mx]); out.append(s[:k]); s = s[k:]
    if s: out.append(s)
    if len(out) > 1 and len(out[-1]) < 4: last = out.pop(); out[-1] += last
    return out
def build_jimaku(timing_path, end):
    T = _jj.load(open(timing_path)); toks = T['tokens']; offs = [0]
    for tk in toks: offs.append(offs[-1] + len(tk['text']))
    def at(c):
        i = max(0, min(len(toks) - 1, _bs.bisect_right(offs, c) - 1)); tk = toks[i]; L = max(1, len(tk['text']))
        return tk['start'] + (tk['end'] - tk['start']) * (c - offs[i]) / L
    out = []; c = 0
    for ln in T['lines']:
        for ch in _kiru(ln['text']):
            out.append([round(at(c) * FPS) / FPS, None, ch]); c += len(ch)
    for k, o in enumerate(out):
        nxt = out[k + 1][0] if k + 1 < len(out) else end
        o[1] = nxt if nxt - o[0] < 4.5 else min(nxt, o[0] + 4.2)
    return [(a, b, s) for a, b, s in out]
JIMAKU = []; _JI = {}
def _jimaku_img(s):
    if s not in _JI:
        t = kit.deco(s, int(os.environ.get('JIMAKU_PX', '56')), name=GOTH, fill=kit.C('#ffffff'), pad=2)   # 9版目：門のルール9の試しで大きさを変えられるように
        im = Image.new('RGBA', (t.width + 56, t.height + 18), (11, 20, 120, 235)); im.alpha_composite(t, (28, 9)); _JI[s] = im
    return _JI[s]
_sc_render0 = Sc.render
def _sc_render(self, t):
    cv = _sc_render0(self, t)
    if JIMAKU:
        i = _bs.bisect_right(JIMAKU, (t, 1e9, '')) - 1
        if i >= 0 and JIMAKU[i][0] <= t < JIMAKU[i][1]:
            im = _jimaku_img(JIMAKU[i][2]); cv.alpha_composite(im, ((W - im.width) // 2, H - im.height - 14))
    return cv
Sc.render = _sc_render
# 6版目（依頼主 03:3x「手本の作者さんのアイコンじゃなくて俺のアイコンに」）：吹き出しの横の丸い話し手を、自社キャラのアイコン（X のアイコン）に
CHARA_ICON = os.path.expanduser('~/rin6/state/xtep-vtuber-buzz-1017/vtuber/chara/icon1024.png')
def avatar(d=110):
    s = d * 2; src = Image.open(CHARA_ICON).convert('RGBA').resize((s, s), Image.LANCZOS)
    m = Image.new('L', (s, s), 0); ImageDraw.Draw(m).ellipse([4, 4, s - 5, s - 5], fill=255)
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); im.paste(src, (0, 0), m)
    ImageDraw.Draw(im).ellipse([4, 4, s - 5, s - 5], outline=(220, 40, 40, 255), width=max(4, s // 26))
    return im.resize((d, d), Image.LANCZOS)
# 字幕の聞き違いを台本の字に直す（Loom の声を書き起こした行のため・10/19 03:4x）。言葉の時刻は直す前の字で取り、出す字だけ直す
JIMAKU_FIX = [('丸尾', '自社キャラ'), ('得点', '特典'), ('クロードGPT図', 'Claude・GPTs'), ('チャットGPT', 'ChatGPT'), ('チャットgpt', 'ChatGPT'),
    ('クロードコード', 'Claude Code'), ('コーデックス', 'Codex'), ('aiエージェント', 'AIエージェント'), ('ai', 'AI'), ('sns', 'SNS'),
    ('スマート仕事', 'スマホで仕事'), ('スマートAIエージェント', 'スマホでAIエージェント'), ('背取り', 'せどり'), ('スマート指示', 'スマホで指示'),
    ('中上全員', '中上級者まで全員'), ('あなたの上AI', 'あなたの状況でAI'), ('高単価フィリエ', '高単価アフィリ'), ('コンテンツ販売いく', 'コンテンツ販売でいく'),
    ('ところなの壁打ち', 'ところなんです 壁打ち'), ('全然違い', '全然違う'), ('01', '0→1'), ('新規事業が手を', '新規事業に手を'), ('自分がだと', '自分が止まると'),
    ('一時対応', '一次対応'), ('賃金事業', '新規事業'), ('AIにつける', 'AIエージェント×'), ('制約', '成約'), ('月に数景色', '月の景色'), ('自分が乗りたない', ''),
    ('ノート', 'note'), ('をすれけるのを', 'で記事を'), ('1日に売上げ', '1日で売上'), ('ただ勘違いしてください', 'ただ勘違いしないでください'),
    ('投稿面にします', '投稿を目にします'), ('AIに効いている', 'AIに聞いている'), ('AIに入るのは', 'AIで手に入るのは'), ('使いこなす手に', '使いこなすと手に'),
    ('時期もあります', '時間です'), ('像を止める', '像をまとめる'), ('高単化', '高単価'), ('既存時期', '既存事業'), ('新規時期', '新規事業'), ('通路を知る', 'ツールを知る'),
    ('高単価フリエイト', '高単価アフィリエイト'), ('高単価比例', '高単価アフィリ'), ('AIエージェントの聞くだけ', 'AIエージェントに聞くだけ'), ('AIエージで', 'AIエージェントで'),
    ('時間だけが解けます', '時間だけが溶けます'), ('やろうといってほしい', 'やってきてほしい'), ('個別面で', '個別面談で'), ('本を見てくれて', '最後まで見てくれて'),
    ('gpt', 'GPT'), ('売上げ', '売上'), ('事業を作る難易度', '事業を作る難しさ')]
_bj0 = build_jimaku
def build_jimaku(timing_path, end):
    out = []
    for a, b, s in _bj0(timing_path, end):
        for x, y in JIMAKU_FIX: s = s.replace(x, y)
        if s.strip(): out.append((a, b, s))
    return out
# 切り方の直し（10/19 03:5x）：直した字で切り、言葉の頭の時刻は元の字の位置から取る。カタカナ・英数の途中と小さい字の前では切らない
import re as _re
def _okireru(s, i):
    a, b = s[i - 1], s[i]
    if b in 'ぁぃぅぇぉっゃゅょゎァィゥェォッャュョーん、。' : return False
    if _re.match(r'[ァ-ヴA-Za-z0-9→×・]', a) and _re.match(r'[ァ-ヴA-Za-z0-9→×・]', b): return False
    return True
def _kiru2(s, mx=20, mn=8):
    out = []
    while len(s) > mx:
        ks = [i for i in range(mn, mx + 1) if s[i - 1] in _BRK and _okireru(s, i)]
        if not ks: ks = [i for i in range(mn, min(len(s), mx + 4)) if _okireru(s, i)]
        k = max(ks) if ks else mx; out.append(s[:k]); s = s[k:]
    if s: out.append(s)
    if len(out) > 1 and len(out[-1]) < 4: last = out.pop(); out[-1] += last
    return out
def _naosu(s):
    """直した字と、その1字ずつの元の位置"""
    txt, idx, i = '', [], 0
    while i < len(s):
        for x, y in JIMAKU_FIX:
            if x and s.startswith(x, i):
                txt += y; idx += [i] * len(y); i += len(x); break
        else:
            txt += s[i]; idx.append(i); i += 1
    return txt, idx
def build_jimaku(timing_path, end):
    T = _jj.load(open(timing_path)); toks = T['tokens']; offs = [0]
    for tk in toks: offs.append(offs[-1] + len(tk['text']))
    def at(c):
        i = max(0, min(len(toks) - 1, _bs.bisect_right(offs, c) - 1)); tk = toks[i]; L = max(1, len(tk['text']))
        return tk['start'] + (tk['end'] - tk['start']) * (c - offs[i]) / L
    out = []; c0 = 0
    for ln in T['lines']:
        txt, idx = _naosu(ln['text']); p = 0
        for ch in _kiru2(txt):
            if ch.strip(): out.append([round(at(c0 + idx[p]) * FPS) / FPS, None, ch])
            p += len(ch)
        c0 += len(ln['text'])
    for k, o in enumerate(out):
        nxt = out[k + 1][0] if k + 1 < len(out) else end
        o[1] = nxt if nxt - o[0] < 4.5 else min(nxt, o[0] + 4.2)
    return [(a, b, s) for a, b, s in out]
# 次の版（全編v10・頭3分v11・10/19 07:5x）：字幕の聞き違いを声で聞き直して直す（e/jimaku-naoshi-v10.md に前→後と根拠）
#   「｜」は字幕の切れ目の印（出す字には残さない）。文の切れ目をまたいで1枚にしていた所を分ける
JIMAKU_FIX[:0] = JIMAKU_FIX_V10 = [
    ('ここをリサーチ一時対応運用', '投稿・リサーチ・一次対応・運用｜'),
    ('知りたいAIエージェントすごいのは分かったけど', '知りたい｜AIエージェントすごいのは分かったけど｜'),
    ('私は法人のかなりの金額でZoomを', '私は法人のかなりの金額で｜Zoomを'),
    ('上限あなたの体力と時期もあります', '上限はあなたの体力と時間で決まります'),
    ('本を見てくれて', 'ここまで見てくれて'),
    ('データを10個', 'アイデアを10個'),
    ('来週送信して', 'LINEで送信して'),
    ('先ほどのもの自体', '｜そのもの自体'),
    ('スマートフォン作業会に行ったり', 'スマートフォン作業を変えていったり'),
    ('やろうといってほしい', 'やっといてほしい'),
    ('話をと決めた', '話しようと決めた'),
    ('売上を含んで作り', '売上を副業で作り'),
]
_kiru2_0 = _kiru2
def _kiru2(s, mx=20, mn=8):
    if '｜' not in s: return _kiru2_0(s, mx, mn)
    out, parts = [], s.split('｜')
    for k, seg in enumerate(parts):
        ch = _kiru2_0(seg, mx, mn) if seg else []
        if k < len(parts) - 1:
            if ch: ch[-1] += '｜'
            elif out: out[-1] += '｜'
            else: ch = ['｜']
        out += ch
    return out
_naosu_0 = _naosu
def _naosu(s):
    """直した字の1字ずつを元の字の位置に当てる（同じ字は同じ字の位置・足した字は前の字の位置）。
    前は直した字を全部、直す前の頭の位置に当てていたので、直しの途中で字幕が切れると後ろの1枚が0秒になった（全編 519秒「AIエージェントに」が出ていなかった）"""
    import difflib as _dl
    txt, idx, i = '', [], 0
    while i < len(s):
        for x, y in JIMAKU_FIX:
            if x and s.startswith(x, i):
                if True:
                    m = [0] * len(y)   # 同じ字は同じ字の位置・入れ替えた字は入れ替える前の字に割り振る・足した字は次の字の位置
                    for op, i1, i2, j1, j2 in _dl.SequenceMatcher(None, x, y, autojunk=False).get_opcodes():
                        for j in range(j1, j2):
                            m[j] = (i1 + (j - j1)) if op == 'equal' else (i1 + (j - j1) * (i2 - i1) // (j2 - j1)) if op == 'replace' else min(i1, len(x) - 1)
                    idx += [i + v for v in m]
                else: idx += [i] * len(y)
                txt += y; i += len(x); break
        else:
            txt += s[i]; idx.append(i); i += 1
    return txt, idx
def build_jimaku(timing_path, end):
    """v10：言葉の表（tokens）と行の字が食い違う所があると、そこから後の字幕の頭が字の数だけずれていた
    （全編の447秒の行「スマートフォン」が言葉の表では「スマトフォン」→ 451秒より後が1字ぶん遅れていた）。行の字の位置を言葉の表の位置に当て直す"""
    import difflib as _dl
    T = _jj.load(open(timing_path)); toks = T['tokens']; offs = [0]
    for tk in toks: offs.append(offs[-1] + len(tk['text']))
    L = ''.join(ln['text'] for ln in T['lines']); K = ''.join(tk['text'] for tk in toks)
    mp = list(range(len(L) + 1))
    if L != K:
        mp = [None] * (len(L) + 1); mp[len(L)] = len(K)
        for a, b, n in _dl.SequenceMatcher(None, L, K, autojunk=False).get_matching_blocks():
            for d in range(n): mp[a + d] = b + d
        last = 0
        for k in range(len(L) + 1):
            if mp[k] is None: mp[k] = last
            last = mp[k]
    def at(c):
        c = mp[min(c, len(L))]
        i = max(0, min(len(toks) - 1, _bs.bisect_right(offs, c) - 1)); tk = toks[i]; n = max(1, len(tk['text']))
        return tk['start'] + (tk['end'] - tk['start']) * (c - offs[i]) / n
    out = []; c0 = 0
    for ln in T['lines']:
        txt, idx = _naosu(ln['text']); p = 0
        for ch in _kiru2(txt):
            s = ch.replace('｜', '')
            if s.strip(): out.append([round(at(c0 + idx[p]) * FPS) / FPS, None, s])
            p += len(ch)
        c0 += len(ln['text'])
    for k, o in enumerate(out):
        nxt = out[k + 1][0] if k + 1 < len(out) else end
        o[1] = nxt if nxt - o[0] < 4.5 else min(nxt, o[0] + 4.2)
    return [(a, b, s) for a, b, s in out]
# 7版目（10/19 04:0x・依頼主「公式素材を使って」）：サービス名の黒い札を公式のロゴに（形・色は変えない。OpenAI のマークの下にだけ製品名の字を足す）
_KS = os.path.expanduser('~/rin6/state/yt-anime-1014/sozai/koushiki/anthropic_press_kit/Anthropic media resources/Anthropic logos/Claude logos')
LOGO = {'claude': _KS + '/1 Claude logo/PNG/Claude logo - Slate.png', 'claude_code': _KS + '/2 Claude Code logo/PNG/Claude Code logo - Slate.png',
        'openai': os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/logo/openai_blossom.png'),
        'youtube': os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/logo/youtube_logo.png'),
        'instagram': os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/logo/instagram_glyph.png')}   # 公式 koushiki/instagram Gradient Glyph を形・色を変えずに 600px にした（10/22 KMXS）   # 公式 koushiki/youtube_logo.svg を形・色を変えずに PNG にした（magick・10/20）
def logo(name, h=100, label=None, lsize=48):
    im = Image.open(LOGO[name]).convert('RGBA'); im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
    if label:
        t = kit.deco(label, lsize, name=GOTH, fill=kit.C('#111111'), pad=2)
        out = Image.new('RGBA', (max(im.width, t.width), im.height + t.height + 10), (0, 0, 0, 0))
        out.alpha_composite(im, ((out.width - im.width) // 2, 0)); out.alpha_composite(t, ((out.width - t.width) // 2, im.height + 10)); im = out
    pad = 28; card = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], 22, fill=(255, 255, 255, 245))
    card.alpha_composite(im, (pad, pad)); return _shadow(card, (0, 6), 10, 0.25)
# 12版目（10/19 11:xx・作業AIの作業員 vsl-v12）：字幕の切れ目を「言葉の途中」に置かない
#   v11 では切れ目の4分の1ほどが言葉の途中だった（行の中「の｜で」「上が｜りました」「と｜ころ」／行の境「応｜じて」「AIエージ｜ェント」「んです｜が」）
#   表は work/jimaku_kire.json（v12/kire_heads.py が形態素で作る）：tsunagu＝次の行とつなぐ行・heads＝文節の頭・yowai＝名詞と名詞の間。
#   表に無い字が来たら止める（黙って前の切り方に戻さない）
_KIRE = None
def _kire():
    global _KIRE
    if _KIRE is None: _KIRE = _jj.load(open(os.path.join(os.environ.get('PROJ') or os.path.dirname(os.path.abspath(__file__)), 'work', 'jimaku_kire.json')))
    return _KIRE
def _kiru2_0(s, mx=20, mn=8):
    K = _kire()
    if s not in K['heads']: raise RuntimeError('字幕の切れ目の表に無い字（v12/kire_heads.py で作り直す）: ' + s)
    out, base, rest = [], 0, s
    while len(rest) > mx:
        k = None
        for H in (K['heads'][s], K['yowai'][s]):   # 文節の頭が無いときだけ名詞と名詞の間
            hs = [h - base for h in H if 0 < h - base < len(rest)]
            c = [x for x in hs if mn <= x <= mx]
            if c:
                pref = [x for x in c if rest[x - 1] in _BRK or rest[x - 1] in ' 　']
                k = max(pref) if pref else max(c); break
            big = [x for x in hs if mx < x <= mx + 6]
            if big: k = min(big); break
        if k is None:
            small = [h - base for h in K['heads'][s] if 3 <= h - base < mn]
            if small: k = max(small)
        if k is None: break
        out.append(rest[:k]); base += k; rest = rest[k:]
    if rest: out.append(rest)
    if len(out) > 1 and len(out[-1]) < 4: last = out.pop(); out[-1] += last
    return out
def _jimaku_kumi(T):
    """行を直した字にし、行の終わりが言葉の途中なら次の行とつなぐ。[(字, 1字ずつの元の位置（全部の行を並べた字の上）)]"""
    tsu = set(_kire()['tsunagu']); out, txt, idx, c0 = [], '', [], 0
    for ln in T['lines']:
        t, i = _naosu(ln['text']); txt += t; idx += [c0 + v for v in i]; c0 += len(ln['text'])
        if ln['n'] not in tsu: out.append((txt, idx)); txt, idx = '', []
    if txt: out.append((txt, idx))
    return out
def build_jimaku(timing_path, end):
    import difflib as _dl
    T = _jj.load(open(timing_path)); toks = T['tokens']; offs = [0]
    for tk in toks: offs.append(offs[-1] + len(tk['text']))
    L = ''.join(ln['text'] for ln in T['lines']); K = ''.join(tk['text'] for tk in toks)
    mp = list(range(len(L) + 1))
    if L != K:
        mp = [None] * (len(L) + 1); mp[len(L)] = len(K)
        for a, b, n in _dl.SequenceMatcher(None, L, K, autojunk=False).get_matching_blocks():
            for d in range(n): mp[a + d] = b + d
        last = 0
        for k in range(len(L) + 1):
            if mp[k] is None: mp[k] = last
            last = mp[k]
    def at(c):
        c = mp[min(c, len(L))]
        i = max(0, min(len(toks) - 1, _bs.bisect_right(offs, c) - 1)); tk = toks[i]; n = max(1, len(tk['text']))
        return tk['start'] + (tk['end'] - tk['start']) * (c - offs[i]) / n
    out = []
    for txt, idx in _jimaku_kumi(T):
        p = 0
        for ch in _kiru2(txt):
            s = ch.replace('｜', '') + ('｜' if ch.endswith('｜') else '')   # 文の終わりの札は印を残す（短い札をつなぐ所で文をまたがないため・最後に外す）
            if s.strip('｜').strip(): out.append([round(at(idx[p]) * FPS) / FPS, None, s])
            p += len(ch)
    for k, o in enumerate(out):
        nxt = out[k + 1][0] if k + 1 < len(out) else end
        o[1] = nxt if nxt - o[0] < 4.5 else min(nxt, o[0] + 4.2)
    return [(a, b, s) for a, b, s in out]
# ===== yt-henshu-pipe（10/19）：字幕に出す字は手の直し表（JIMAKU_FIX）でなく、作業フォルダの work/jimaku_disp.json（pipe/jimaku_ji.py）から取る =====
#   jimaku_disp.json＝{行の番号: {"disp": 出す字（｜は文の切れ目）, "idx": 1字ずつの話した字の位置（行の中）}}。言葉の頭の時刻は話した字の位置から取る（v12 と同じ）
#   上の JIMAKU_FIX は面談前VSL 1本ぶんの手の直し。ここでは使わない（空にする）
JIMAKU_FIX[:] = []
_DISP = None
def _disp():
    global _DISP
    if _DISP is None:
        p = os.path.join(os.environ.get('PROJ') or os.path.dirname(os.path.abspath(__file__)), 'work', 'jimaku_disp.json')
        _DISP = {int(k): v for k, v in _jj.load(open(p)).items()}
    return _DISP
def _jimaku_kumi(T):
    tsu = set(_kire()['tsunagu']); D = _disp(); out, txt, idx, c0 = [], '', [], 0
    for ln in T['lines']:
        d = D.get(ln['n'])
        if d is None: raise RuntimeError('字幕に出す字（work/jimaku_disp.json）に無い行: %d（pipe/jimaku_ji.py を走らせ直す）' % ln['n'])
        if len(d['idx']) != len(d['disp']): raise RuntimeError('字幕の字と位置の数が合わない: %d行目' % ln['n'])
        txt += d['disp']; idx += [c0 + v for v in d['idx']]; c0 += len(ln['text'])
        if ln['n'] not in tsu: out.append((txt, idx)); txt, idx = '', []
    if txt: out.append((txt, idx))
    return [(t, i) for t, i in out if t]
# 5字未満の札は前か次の札とつなぐ（20字まで・間が空いていない時だけ）。v12 は5字未満が 2枚、pipe の1回目は 8枚（「覚えても」「つまり」「目標」）で読みにくかった（10/19）
#   つないでも札の出る秒は変わらない（前とつなぐ＝前の札の頭のまま、次とつなぐ＝短い札の頭から）
_bj_pipe = build_jimaku
import re as _re_b; _re_owari = _re_b.compile(r'(?:です|ます|ました|でした|ません)$')   # 札の終わりが文の終わり（pipe/bunmatsu_re.py と同じ形）
def build_jimaku(timing_path, end):
    #   文の終わり（札の末尾の「｜」）をまたいではつながない（r14：「思います」＋「優秀な相談相手が」が1枚になり文をまたいだ・作業AI 10/20）
    J = [list(x) for x in _bj_pipe(timing_path, end)]; k = 0
    while k < len(J):
        a, b, s = J[k]; n = len(s.rstrip('｜'))
        if k > 0 and _re_owari.search(J[k - 1][2].rstrip('｜')) and not J[k - 1][2].endswith('｜'): J[k - 1][2] += '｜'   # 行の終わりの文の終わり（「すごいです」＋「本当に」）も文の切れ目として扱う
        if _re_owari.search(s.rstrip('｜')) and not s.endswith('｜'): s = s + '｜'; J[k][2] = s
        if n < 5 and len(J) > 1:
            if k > 0 and not J[k - 1][2].endswith('｜') and len(J[k - 1][2]) + n <= 20 and abs(J[k - 1][1] - a) < 1e-6:
                J[k - 1][2] += s; J[k - 1][1] = b; J.pop(k); continue
            if k + 1 < len(J) and not s.endswith('｜') and len(J[k + 1][2].rstrip('｜')) + n <= 20 and abs(b - J[k + 1][0]) < 1e-6:
                J[k + 1][2] = s + J[k + 1][2]; J[k + 1][0] = a; J.pop(k); continue
        k += 1
    # 文の途中の短い間（声の間はそのまま）は、前の札を次の札の頭まで出したままにする（10/22 zenpen-1022 4章 212秒「決まっていないので（1.3秒の間）相談しづらい」で字幕が消え、ルール5の覆い 0.82）
    #   既定は 0＝しない。JIMAKU_MA_TSUNAGU=秒 のときだけ（文の終わり「｜」の札はつながない）
    _ma = float(os.environ.get('JIMAKU_MA_TSUNAGU', '0') or 0)
    if _ma > 0:
        for k in range(len(J) - 1):
            if not J[k][2].endswith('｜') and 0 < J[k + 1][0] - J[k][1] <= _ma: J[k][1] = J[k + 1][0]
    return [(a, b, s.replace('｜', '')) for a, b, s in J]
# 自社キャラのアイコンは道具のそば（pipe/sozai/）の写しを使う。xtep-vtuber-buzz-1017 は内蔵を空ける作業で Drive へ移り、10/19 15:0x に読めなくなった（元は Drive の元ファイル）
_PIPE_ICON = os.path.expanduser('~/rin6/tools/yt-henshu/pipe/sozai/chara_icon1024.png')
if os.path.exists(_PIPE_ICON): CHARA_ICON = _PIPE_ICON
