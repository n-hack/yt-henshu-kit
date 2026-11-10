"""理想2本（youtube.tehon 2Dgoti3GYAE・yNDrlmlh_fQ）の字の形（10/18 頭3分を1コマずつ見て写した）

  from riso_kata import *
  dai('YouTube運用の全てを')      明朝の極太・白→赤のグラデ・赤い光の縁（題）
  kin('完全攻略')                 金の明朝斜体・暗い影（金の筆文字）
  aka('3年間運用している')         白地にそのまま置く赤のゴシック極太（箱なし）
  obi('このチャンネルの凄いところ') 黄の帯の見出し（黒字・帯は字の下半分）
  hako('新たな運用スタイルで', 'aka'|'kon')  角丸の赤・紺の箱（白字・影）
  sen('売上もしっかり上がる')       赤字＋赤い下線（白い縁）
  kazu('1本目の動画', '80万再生')  黒の小見出し＋赤い大きな数字
"""
import os, sys
_LIB = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _LIB)
import paths
sys.path.insert(0, paths.BUILD)
import kit
from PIL import Image, ImageDraw, ImageFilter

MINCHO = '/System/Library/AssetsV2/com_apple_MobileAsset_Font8/36a81f2dad2ef266c50802d85839e0201fcf4e57.asset/AssetData/ToppanBunkyuMidashiMinchoStdN-ExtraBold.otf'
GOTH = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
if not os.path.exists(MINCHO): MINCHO = 'noto'

DAI_FILL = ('v', [(0, '#ffffff'), (0.45, '#ffe6e6'), (0.7, '#e43a3a'), (1, '#a80000')])
KIN_FILL = ('v', [(0, '#fff3c4'), (0.4, '#e8c46a'), (0.6, '#b98a2a'), (1, '#f2dc98')])

def dai(text, size=120):
    return kit.deco(text, size, name=MINCHO, fill=DAI_FILL, strokes=[(3, '#7a0000')], glow=(16, '#ff1a1a', 2.4), shadow=(0, 6, 8, 0.45))

def kin(text, size=110):
    return kit.deco(text, size, name=MINCHO, fill=KIN_FILL, shadow=(4, 6, 10, 0.6), glow=(10, '#fff2b0', 1.2), italic=0.16)

def aka(text, size=96, color='#c80000'):
    return kit.deco(text, size, name=GOTH, fill=kit.C(color), shadow=(0, 3, 4, 0.18))

def obi(text, size=58):
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#111111'), pad=4)
    w, h = t.width + 30, t.height + 6
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle([0, int(h * 0.55), w - 1, h - 1], fill=kit.C('#f5e100'))
    im.alpha_composite(t, (15, 0)); return im

def hako(text, kind='aka', size=60):
    bg = {'aka': ('v', [(0, '#e04848'), (1, '#b81e1e')]), 'kon': ('v', [(0, '#3f78c8'), (1, '#1f4f9a')])}[kind]
    b = kit.box(text, size, bg=bg, fg='#ffffff', radius=int(size * 0.28), padx=int(size * 0.6), pady=int(size * 0.3), name=GOTH, tagfill={'y': kit.C('#fff200')})
    import anim as _a
    return _a.shadowed(b, off=(0, 8), blur=12, alpha=0.35)[0]

def sen(text, size=62):
    t = kit.deco(text, size, name=GOTH, fill=kit.C('#c80000'), strokes=[(5, '#ffffff')], pad=8)
    im = Image.new('RGBA', (t.width, t.height + 10), (0, 0, 0, 0)); im.alpha_composite(t, (0, 0))
    ImageDraw.Draw(im).rectangle([8, t.height - 4, t.width - 8, t.height + 2], fill=kit.C('#c80000')); return im

def kazu(label, num, size=96):
    a = kit.deco(label, int(size * 0.42), name=GOTH, fill=kit.C('#222222'), pad=4)
    b = kit.deco(num, size, name=GOTH, fill=kit.C('#c80000'), pad=4)
    im = Image.new('RGBA', (a.width + b.width + 12, max(a.height, b.height)), (0, 0, 0, 0))
    im.alpha_composite(a, (0, im.height - a.height - int(size * 0.12))); im.alpha_composite(b, (a.width + 12, im.height - b.height)); return im

# ---- 出方（理想2本で見たもの）。henshu の R(..., anim_='type') などで使う ----
import anim as _anim
from anim import paste_safe as _ps, with_alpha as _wa, ease_out as _eo, clamp as _cl
_old = _anim.Elem.animate
def _animate(self, cv, im, x, y, p, a_out):
    a = self.anim
    if a == 'type':      # 1字ずつ出る（左から字の幅ずつ）。n は字数の目安
        n = max(1, getattr(self, 'nchar', 10)); k = int(_cl(p) * n + 0.999) / n
        w = int(im.width * k)
        if w > 0: _ps(cv, _wa(im.crop((0, 0, w, im.height)), a_out), x, y)
    elif a == 'fly':     # 画面いっぱいの大きさ・半透明から縮んで止まる（題の飛び込み）
        s = 1.0 + 2.2 * (1 - _eo(p)) ** 2
        im2 = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
        _ps(cv, _wa(im2, (0.35 + 0.65 * _eo(p)) * a_out), x + (im.width - im2.width) // 2, y + (im.height - im2.height) // 2)
    elif a == 'slidel':  # 右から滑り込む
        dx = int(700 * (1 - _eo(p))); _ps(cv, _wa(im, _cl(p * 2) * a_out), x + dx, y)
    else:
        _old(self, cv, im, x, y, p, a_out)
_anim.Elem.animate = _animate

def blue(text, size=110):
    """白い縁の青グラデの太ゴシック（『80万再生』『平均再生数10万再生超』）"""
    return kit.deco(text, size, name=GOTH, fill=('v', [(0, '#7fd0ff'), (0.5, '#2b8de8'), (1, '#1858c8')]), strokes=[(8, '#ffffff')], shadow=(0, 6, 8, 0.5))

def shiro(text, size=72):
    """暗い地の上の白い太ゴシック（影）"""
    return kit.deco(text, size, name=GOTH, fill=kit.C('#ffffff'), shadow=(0, 4, 8, 0.7))

def kuro(text, size=64):
    """白地の上の黒の太ゴシック（『今回YouTube運用完全版ということで』）"""
    return kit.deco(text, size, name=GOTH, fill=kit.C('#222222'))

# ---- 10/18 追加の出方（vsl-yt-1 も使う）----
#   kira    ぼかしからくっきり＋光の粒が左から右へ流れる（金の筆文字・数字の強調）
#   xdraw   赤い×が1画目→2画目の順に描かれる（R(t, batsu(200), x, y, 'cc', 'xdraw', dur=0.35)）
#   slidel  右から滑り込む（スマホ枠 phone_waku() と使う）
#   fly     画面いっぱいから縮んで止まる（1字ずつは fly_chars() で要素のリストを作る）
import math as _m, random as _rnd
from PIL import ImageFilter as _IF
_old2 = _anim.Elem.animate
def _animate2(self, cv, im, x, y, p, a_out):
    a = self.anim
    if a == 'kira':
        r = 14 * (1 - _eo(p)); im2 = im.filter(_IF.GaussianBlur(r)) if r > 0.5 else im
        _ps(cv, _wa(im2, _eo(p) * a_out), x, y)
        if p < 1.0:   # 光の粒：字の高さの帯を左から右へ。粒の位置は要素ごとに固定（毎コマ同じ乱数）
            rng = _rnd.Random(id(self) % 9973); lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
            head = p * (im.width + 200) - 100
            for _ in range(60):
                px = head - rng.random() * 260; py = rng.random() * im.height; s = 2 + rng.random() * 5
                if 0 <= px < im.width: d.ellipse([px - s, py - s, px + s, py + s], fill=(255, 245, 200, int(230 * (1 - p * 0.6))))
            lay = lay.filter(_IF.GaussianBlur(1.2)); _ps(cv, _wa(lay, a_out), x, y)
    elif a == 'xdraw':
        w, h = im.size; lay = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); lw = max(8, int(w * 0.16)); m = lw
        p1 = _cl(p * 2); p2 = _cl(p * 2 - 1)
        if p1 > 0: d.line([(m, m), (m + (w - 2 * m) * p1, m + (h - 2 * m) * p1)], fill=(232, 32, 32, 255), width=lw)
        if p2 > 0: d.line([(w - m, m), (w - m - (w - 2 * m) * p2, m + (h - 2 * m) * p2)], fill=(232, 32, 32, 255), width=lw)
        _ps(cv, _wa(lay, a_out), x, y)
    else:
        _old2(self, cv, im, x, y, p, a_out)
_anim.Elem.animate = _animate2

def batsu(d=200):
    """赤い×の大きさの入れ物（xdraw で描く。静止のときは kit.big_x を使う）"""
    return kit.big_x(d)

def phone_waku(screen, h=520):
    """スマホの黒い枠に画面（サムネ・チャンネル画面）をはめる。横向き（理想2本の『インスタ完全攻略』の形）"""
    if screen.height > screen.width:   # 縦の画面は縦向きのスマホに入れる（横の枠に押し込むと画面がつぶれる・10/23 KMXS 手本は縦のスマホ）
        w = int(h * 0.5); im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], int(w * 0.14), fill=(18, 18, 18, 255))
        sw, sh = w - int(w * 0.08), h - int(w * 0.28); sc = screen.convert('RGBA').resize((sw, sh))
        m = Image.new('L', (sw, sh), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], int(w * 0.07), fill=255)
        im.paste(sc, ((w - sw) // 2, (h - sh) // 2), m)
        d.rounded_rectangle([w // 2 - int(w * 0.12), int(w * 0.04), w // 2 + int(w * 0.12), int(w * 0.07)], 4, outline=(90, 90, 90, 255), width=3)
        import anim as _a
        return _a.shadowed(im, off=(0, 10), blur=14, alpha=0.45)[0]
    w = int(h * 1.95); im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], int(h * 0.14), fill=(18, 18, 18, 255))
    sw, sh = w - int(h * 0.28), h - int(h * 0.12); sc = screen.convert('RGBA').resize((sw, sh))
    m = Image.new('L', (sw, sh), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], int(h * 0.05), fill=255)
    im.paste(sc, ((w - sw) // 2, (h - sh) // 2), m)
    d.rounded_rectangle([int(h * 0.04), h // 2 - int(h * 0.12), int(h * 0.07), h // 2 + int(h * 0.12)], 4, outline=(90, 90, 90, 255), width=3)
    import anim as _a
    return _a.shadowed(im, off=(0, 10), blur=14, alpha=0.45)[0]

def fly_chars(R, t, text, x, y, size=165, step=0.07, dur=0.35, maker=None):
    """題を1字ずつ飛び込ませる。R は henshu.R。中央 (x, y) にそろえた要素のリストを返す（Sc の elems に足す）"""
    maker = maker or dai
    ims = [maker(ch, size) if ch.strip() else Image.new('RGBA', (int(size * 0.35), 10), (0, 0, 0, 0)) for ch in text]
    pad = int(size * 0.32)   # deco の余白の分だけ重ねて並べる
    total = sum(im.width - 2 * pad for im in ims) + 2 * pad; cx = x - total // 2; out = []
    for k, im in enumerate(ims):
        e = R(t + k * step, im, cx + im.width // 2, y, 'cc', 'fly', dur=dur); out.append(e); cx += im.width - 2 * pad
    return out
