#!/usr/bin/env python3
# 場面表（story.py）を書くための部品。story.py の頭で:
#     import sys, os; sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib')); from henshu import *
#     CK = Clock(PROJ)      # PROJ = この story.py のあるフォルダ
#   CK.line(n)            台本 n 行目の話し始め＋見本のずれ（テロップは声の立ち上がりの約0.05秒前＝kijun）
#   CK.at('言葉', n)       n 行目以降で最初に出る「言葉」の話し始め＋同じずれ
#   CK.end_of('言葉', n)   その言葉の言い終わり
#   R(秒, 画像, x, y, 基準, 出方, s='効果音の種類')  … 部品。効果音は部品が動き出すコマに置く（見本の実測：効果音−画面の変化 中央0秒）
#   Sc(始め, 0, [部品], bg=..., zoom=(1.0, 1.04))   … 場面。zoom で場面ごとにゆっくり寄る（見本の「動いているコマ」の割合に合わせる）
import os, sys, json, math
_LIB = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _LIB)
import paths
sys.path.insert(0, paths.BUILD)
os.environ.setdefault('THEME', os.path.join(paths.ENGINE, 'themes', 'sns-cream.json'))
import anim, kit
from anim import W, H, Raw, Elem, Scene, Subs, fit, with_alpha, paste_safe, clamp, ease_out, ease_in_out
from PIL import Image, ImageDraw, ImageFilter, ImageOps
C = kit.C
KIJUN = json.load(open(paths.KIJUN))
# 画面に出した文字を部品に覚えさせる（テロップの選び方＝全文／要約／キーワード／絵だけ を後で数えるため）
import functools as _ft
def _tagged(fn):
    @_ft.wraps(fn)
    def w(text, *a, **k):
        im = fn(text, *a, **k)
        try: im.info['text'] = str(text)
        except Exception: pass
        return im
    return w
for _n in ('deco', 'box', 'marker', 'navy', 'sub', 't_plain', 't_red_italic', 't_gold', 't_red_glow', 't_blue_big', 'white_glow', 'red_neon_lines', 'neon', 'cloud'):
    if hasattr(kit, _n): setattr(kit, _n, _tagged(getattr(kit, _n)))
SOZAI = paths.sozai_dir()

class Clock:
    def __init__(self, proj):
        J = json.load(open(os.path.join(proj, 'work', 'timing.json')))
        self.J = J; self.L = J['lines']; self.REF = J['ref']; self.LINE0 = {int(k): v for k, v in J['line0'].items()}
        self.T = J['starts']; self.E = J['ends']; self.END = J['duration']
        self.OFF = KIJUN['telop']['offset_target']
        self.WOFF = KIJUN['telop'].get('word_offset_target', self.OFF)   # 言葉に合わせる字は 手本の編集者さんのテロップの出（言葉の頭の1コマ前）に合わせる
        import re
        self.N = lambda s: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】]', '', s.replace('【間】', ''))
        self.used = []      # (秒, 何に合わせたか) … 質の門で「声とのずれ」を確かめる
    def _find(self, phrase, n):
        p = self.N(phrase); i = self.REF.find(p, self.LINE0[n] if n else 0)
        if i < 0: raise KeyError('台本に無い言葉: %s（%s行目以降）' % (phrase, n))
        return i, p
    def line(self, n, off=0.0):
        t = self.T[self.LINE0[n]]; self.used.append((t, 'L%d' % n)); return max(0.0, t + self.OFF + off)
    def at(self, phrase, n=None, off=0.0):
        i, p = self._find(phrase, n); t = self.T[i]; self.used.append((t, phrase)); return max(0.0, t + self.WOFF + off)
    def kw(self, piece, n, d=None, off=0.0):
        """出す字（要約・言い換えでも）の中身が声で言われる所の頭。その行の中で、出す字といちばん長く重なる所（2字以上・同じ長さなら前）。
        行の頭に置くと、言い換えた字が言葉より何十コマも先に出ていた（10/16 Depy：-30〜-118コマが95個）。重ならなければ d（無ければ行の頭）"""
        p = self.N(piece); a = self.LINE0[n]; b = min((v for k, v in self.LINE0.items() if v > a), default=len(self.REF)); seg = self.REF[a:b]
        best = (0, None)
        for i in range(len(p)):
            for j in range(len(p), i + max(1, best[0]), -1):
                if j - i < 2: break
                k = seg.find(p[i:j])
                if k >= 0:
                    if j - i > best[0] or (j - i == best[0] and k < best[1]): best = (j - i, k)
                    break
        if best[1] is None: return d if d is not None else self.line(n, off)
        t = self.T[a + best[1]]; self.used.append((t, piece)); return max(0.0, t + self.WOFF + off)
    def end_of(self, phrase, n=None, off=0.0):
        i, p = self._find(phrase, n); return self.E[i + len(p) - 1] + 0.1 + off
    def text(self, n): return [x for x in self.L if x['n'] == n][0]['text'].replace('【間】', '')

SFX = []; INTENT = []; ELEMS = []; SEL_PLAN = []
def sfx(t, kind): SFX.append((round(t, 3), kind))
def sel(t, kind, shown, dropped=(), added=(), why='', visual='', **ctx):
    """台本の1行をテロップにどう出すかの判断（全文／要約／キーワード／言い換え／足す／出さない）とその理由。draft.py が下書きし作業AIが仕上げる
    ctx … 強調（emphasis）・間（ma）・切り替え（cut）・前後のつながり（link）・1本の流れの中の区間（flow）。質の門⑪が「前後を理由にしたか」を見る"""
    SEL_PLAN.append(dict({'t': round(t, 2), 'kind': kind, 'shown': list(shown), 'dropped': list(dropped), 'added': list(added), 'why': why, 'visual': visual}, **ctx))
def intent(t, role, what, how, why=''):
    INTENT.append((round(t, 2), role, what, how, why))
anim.ring_logo = lambda d=None, ring=None: kit.ring_logo(360)

FPS = anim.FPS
def R(t, img, x, y, anchor='lt', anim_='pop', dur=None, te=None, z=0, s=None, out='fade'):
    """部品。予定の秒 t にいちばん近いコマで「はっきり見える」ように、出方の始まりを少し前に置く
    （出方の最初のコマは薄く小さいので、そのままだと目に見えるのが 2〜4コマ遅れる＝実測）。効果音は t のまま"""
    if s: sfx(t, s)
    # 予定に一番近いコマ fr で描き始め、その1つ前のコマではまだ何も見えないように、出方の頭を 0.9コマ前に置く（実測で決めた）
    fr = round(t * FPS) / FPS
    # pop・bounce は最初の数コマが小さく薄い（透明度 p×3・p×4）ため 0.9コマ前では声の頭から2コマ遅れて見えた（10/20 試験8本の zure.tsv：pop の大半が2コマ遅れ・slam は0）。
    # 声の頭のコマで透明度が9割を超えるよう、この2つだけ出方の頭を 1.6コマ前に置く（2.3では -2〜0 と早すぎた・1.6で試す）（作業AI 10/20「5.6秒だけ直さず道具で」）
    lead = 1.6 if anim_ in ('pop', 'bounce') else 0.9
    ts = fr - lead / FPS if anim_ != 'none' else t
    e = Raw(ts, img, x=x, y=y, anchor=anchor, anim=anim_, dur=dur, te=te, z=z, out=out); e.t_plan = t; ELEMS.append(e); return e

def jin(name, h=None, w=None):
    return fit(Image.open(os.path.join(SOZAI, 'jinbutsu', name + '.png')).convert('RGBA'), w=w, h=h)

def photo(name, zoom=(1.0, 1.08), blur=0, dim=0.0, focus=(0.5, 0.5), kind='shashin'):
    src = Image.open(os.path.join(SOZAI, kind, name + '.png')).convert('RGB')
    base = ImageOps.fit(src, (int(W * 1.12), int(H * 1.12)), Image.LANCZOS, centering=focus)
    if blur: base = base.filter(ImageFilter.GaussianBlur(blur))
    if dim: base = Image.blend(base, Image.new('RGB', base.size, (0, 0, 0)), dim)
    base = base.convert('RGBA')
    def f(k):
        s = zoom[0] + (zoom[1] - zoom[0]) * k
        cw, ch = int(W * 1.12 / s), int(H * 1.12 / s); cx, cy = base.width // 2, base.height // 2
        return base.crop((cx - cw // 2, cy - ch // 2, cx - cw // 2 + cw, cy - ch // 2 + ch)).resize((W, H), Image.BILINEAR)
    return f

ZOOM = tuple(KIJUN['motion']['scene_zoom']) if KIJUN['motion'].get('scene_zoom') else None
class Sc(Scene):
    def __init__(self, t0, t1, elems, bg=None, ring=True, trans=0.22, zoom='auto'):
        super().__init__(t0, t1, elems, ring=ring, trans=trans); self.bgx = bg
        self.zoomx = ZOOM if zoom == 'auto' else zoom
    def render(self, t):
        k = clamp((t - self.t0) / max(0.1, self.t1 - self.t0))
        if self.bgx is None: cv = Image.new('RGBA', (W, H), anim.BG + (255,))
        elif callable(self.bgx): cv = self.bgx(k).copy()
        elif isinstance(self.bgx, tuple): cv = Image.new('RGBA', (W, H), self.bgx + (255,))
        else: cv = self.bgx.copy()
        for e in sorted(self.elems, key=lambda e: e.z): e.draw(cv, t)
        if self.zoomx:
            s = self.zoomx[0] + (self.zoomx[1] - self.zoomx[0]) * k
            if abs(s - 1) > 0.002:
                cw, ch = int(W / s), int(H / s)
                cv = cv.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
        return cv

SCENES = []
def add(sc): SCENES.append(sc); return sc
def finish(end):
    SCENES.sort(key=lambda s: s.t0)
    for k, s in enumerate(SCENES):
        s.t1 = SCENES[k + 1].t0 if k + 1 < len(SCENES) else end
        for e in s.elems:
            if e.te is not None and e.te > s.t1: e.te = None
    # 画面の外に出た部品を知らせる（下書きの縦並びが4つ目から画面の外に出ていた・10/16）。出来上がりは変えない
    for s in SCENES:
        for e in s.elems:
            try:
                w_, h_ = getattr(e, '_src').size; ax, ay = (e.anchor + 'lt')[:2]
                x0 = e.x - (w_ / 2 if ax == 'c' else w_ if ax == 'r' else 0); y0 = e.y - (h_ / 2 if ay == 'c' else h_ if ay == 'b' else 0)
                cut = (max(0, x0 + w_ - W) + max(0, -x0)) / w_ + (max(0, y0 + h_ - H) + max(0, -y0)) / h_
            except Exception: continue
            if cut > 0.25: print('🔴 画面の外：%.1f秒 部品の%d%%が外（x=%s y=%s）' % (s.t0, round(min(1, cut) * 100), e.x, e.y), file=sys.stderr)
def frame_at(t, subs=Subs([])):
    return anim.frame_at(SCENES, subs, t)

def label(text, t0):
    return R(t0, _label(text), 4, 6, 'lt', 'none', z=5)
_LB = {}
def _label(text):
    if text not in _LB: _LB[text] = kit.pill_label(text, kit.ring_logo(200), size=76, h=160)
    return _LB[text]
DARK = kit.dark_bg()
def subx(txt, t, te=None, x=None, size=64, y=1015):
    return R(t, kit.sub(txt, size), x if x is not None else W // 2, y, 'cc', 'fade', te=te)

def network_bg(seed=7, top='#0b1b4a', bot='#050b22', speed=5.3):
    import numpy as np
    rs = np.random.RandomState(seed); n = 46
    P = rs.rand(n, 2) * [W, H]; V = (rs.rand(n, 2) - 0.5) * 30
    base = kit._fill_img(('v', [(0, top), (1, bot)]), W, H); cache = {}
    def f(k):
        key = round(k, 3)
        if key in cache: return cache[key]
        t = k * speed; im = base.copy(); lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); Q = P + V * t
        for i in range(n):
            for j in range(i + 1, n):
                dd = ((Q[i] - Q[j]) ** 2).sum() ** 0.5
                if dd < 330: d.line([tuple(Q[i]), tuple(Q[j])], fill=(70, 130, 255, int(110 * (1 - dd / 330))), width=2)
        for q in Q: d.ellipse([q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6], fill=(120, 170, 255, 190))
        im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(1.2))); im.alpha_composite(lay)
        if len(cache) > 4: cache.clear()
        cache[key] = im; return im
    return f

def radial_bg(a, b, cx=0.5, cy=0.55):
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W * cx) / W) ** 2 + ((yy - H * cy) / H * 0.9) ** 2); v = np.clip(1 - r / 0.8, 0, 1) ** 1.5
    a = np.array(C(a), np.float32); b = np.array(C(b), np.float32)
    return Image.fromarray((a + (b - a) * v[..., None]).astype(np.uint8), 'RGB').convert('RGBA')
def wine_bg(): return radial_bg('#16060e', '#781c34')
def gold_bokeh(seed=11):
    import numpy as np
    rs = np.random.RandomState(seed); im = kit._fill_img(('v', [(0, '#1a1206'), (0.5, '#3a2a0c'), (1, '#120c04')]), W, H)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    for _ in range(70):
        x, y, r = rs.rand() * W, rs.rand() * H, 20 + rs.rand() * 110
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 210, 120, int(25 + rs.rand() * 60)))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10))); return im

def card(w, h, fill=(255, 255, 255), r=28, shadow=True, outline=None):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=fill + (255,) if len(fill) == 3 else fill, outline=outline, width=6 if outline else 0)
    if shadow: im, _ = anim.shadowed(im, off=(0, 8), blur=14, alpha=0.25, pad=24)
    return im

class Bar(Elem):
    """伸びる棒（数の比べ）"""
    def __init__(self, ts, x, y, w, h, color, dur=0.6, **kw):
        super().__init__(ts, anim='none', **kw); self.bx = (x, y, w, h, color); self.d = dur
    def build(self): return None
    def draw(self, cv, t):
        if t < self.ts: return
        x, y, w, h, c = self.bx; k = ease_out((t - self.ts) / self.d)
        ImageDraw.Draw(cv).rounded_rectangle([x, y, x + max(10, int(w * k)), y + h], 18, fill=C(c) + (255,))

SEL_WHY = {'全文': '言い切り・数字など一字も落とせない文だけ全文で出す',
           '要約': '耳で聞けば分かる部分は落とし、残したい意味だけ短くして目で追える量にする',
           'キーワード': '声に集中させ、覚えてほしい語だけを大きく出す',
           '絵だけ': '文字を出すより絵の方が早く伝わる（声と絵で理解させる）',
           '何も出さない': '息継ぎ・間。文字を足すと声の勢いが落ちる'}
def selection_of(proj):
    """場面ごとに「台本の文」と「画面に出した文字」を突き合わせて、テロップの選び方を決める"""
    import re, difflib
    J = json.load(open(os.path.join(proj, 'work', 'timing.json'))); L = J['lines']
    N = lambda s: re.sub(r'<[^>]+>|[、。「」『』！？!?,.\s・…（）()【】“”"=〜~\-]', '', s.replace('【間】', ''))
    out = []
    for k, s in enumerate(SCENES):
        t1 = SCENES[k + 1].t0 if k + 1 < len(SCENES) else s.t1
        lines = [x for x in L if s.t0 - 0.1 <= x['start'] + KIJUN['telop']['offset_target'] < t1 - 0.1]
        said = ''.join(N(x['text']) for x in lines)
        shown_l = [e.image().info.get('text', '') for e in s.elems if isinstance(e, Raw)]
        shown_l = [x for x in shown_l if x and N(x) and x != 'AIエージェントの本質']
        shown = ''.join(N(x) for x in shown_l)
        imgs = sum(1 for e in s.elems if isinstance(e, Raw) and not e.image().info.get('text'))
        if not said: continue
        m = difflib.SequenceMatcher(None, said, shown, autojunk=False)
        cov = sum(b.size for b in m.get_matching_blocks()) / max(1, len(said))
        kind = '全文' if cov >= 0.85 else '要約' if cov >= 0.4 else 'キーワード' if shown else ('絵だけ' if imgs else '何も出さない')
        kept = set(i for b in m.get_matching_blocks() for i in range(b.a, b.a + b.size))
        dropped = ''.join(ch if i not in kept else '｜' for i, ch in enumerate(said))
        dropped = [w for w in dropped.split('｜') if len(w) >= 2]
        extra = [x for x in shown_l if N(x) and N(x) not in said]
        out.append({'t0': round(s.t0, 2), 'lines': [x['n'] for x in lines], 'kind': kind, 'coverage': round(cov, 2),
                    'shown': [re.sub(r'<[^>]+>', '', x).replace('\n', ' ') for x in shown_l], 'dropped': dropped[:12],
                    'added': [re.sub(r'<[^>]+>', '', x).replace('\n', ' ') for x in extra][:6], 'why': SEL_WHY[kind]})
    return out

def theme_used(proj, end):
    """世界観の統一（観点8）を測る材料：場面ごとの地（見た目の型）・本編の地が占める割合・差し色の数・常に出ているもの → theme_used.json"""
    from collections import defaultdict
    look = defaultdict(float); lab = ring = 0.0
    for s in SCENES:
        d = max(0.0, (s.t1 or end) - s.t0); b = s.bgx
        k = 'main' if b is None else (getattr(b, '__qualname__', None) or 'img%d' % id(b)) if callable(b) or isinstance(b, Image.Image) else str(b)
        look[k] += d; ring += d if getattr(s, 'ring', False) else 0
        if any(getattr(e, 'anim', '') == 'none' and getattr(e, 'z', 0) == 5 for e in s.elems): lab += d
    tot = sum(look.values()) or 1
    th = json.load(open(os.environ['THEME']))
    acc = {tuple(v) for k, v in th.items() if k in ('red', 'marker', 'sub_em', 'check', 'star') and isinstance(v, list)} | {tuple(v) for v in (th.get('colors') or {}).values()}
    # 差し色は「画面に出したテロップで実際に使った色」で数える（10/16：テーマに書いた色の数＝10を数えていた。ほぼ同じ赤3つも別に数えていた）
    #   テロップ1つごとに いちばん多い鮮やかな色（彩度0.35以上）を取り、色相12等分×明るさ3段の組で数える。見本の per_full も「使った差し色」を数えている
    import colorsys, numpy as _np
    used = set()
    for s_ in SCENES:
        for e in s_.elems:
            im = getattr(e, '_src', None)
            if not isinstance(im, Image.Image) or not im.info.get('text'): continue
            a_ = _np.asarray(im.convert('RGBA')).reshape(-1, 4); a_ = a_[a_[:, 3] > 200][:, :3].astype(float)
            if not len(a_): continue
            mx, mn = a_.max(1), a_.min(1); c_ = a_[((mx - mn) / _np.maximum(mx, 1) > 0.35) & (mx > 60)]
            if len(c_) < 200: continue
            u_, n_ = _np.unique((c_ // 32).astype(int), axis=0, return_counts=True); top = u_[n_.argmax()] * 32 + 16
            h_, l_, _s = colorsys.rgb_to_hls(*[x / 255 for x in top]); used.add((round(h_ * 12) % 12, 0 if l_ < 0.35 else 2 if l_ > 0.7 else 1))
    json.dump({'w_modes': len(look), 'w_main_share': round(max(look.values()) / tot, 3), 'w_accent_n': len(used) if used else len(acc), 'w_accent_theme': len(acc),
               'w_always_on': int(lab / tot > 0.5) + int(ring / tot > 0.5), 'looks_s': {k: round(v, 1) for k, v in look.items()}, 'theme': os.environ['THEME']},
              open(os.path.join(proj, 'theme_used.json'), 'w'), ensure_ascii=False, indent=1)


def dump_meta(proj, end, bgm, sparse):
    """質の門で使う：部品の出る秒・効果音・BGM・訴求の一覧を work/story_meta.json に"""
    boxes = []
    for e in ELEMS:
        try:
            im = e.image(); x, y = e.pos(im)
            x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
            if x1 - x0 > 8 and y1 - y0 > 8: boxes.append([round(getattr(e, 't_plan', e.ts), 3), x0, y0, x1, y1, e.anim, round(e.te, 3) if e.te else None])
        except Exception: pass
    json.dump({'end': end, 'elems': sorted(round(getattr(e, 't_plan', e.ts), 3) for e in ELEMS), 'boxes': sorted(boxes), 'sfx': SFX, 'bgm': bgm, 'sparse': sparse,
               'scenes': [round(s.t0, 3) for s in SCENES],
               'intent': [{'t': a, 'role': b, 'intent': c, 'edit': d, 'why': e} for a, b, c, d, e in sorted(INTENT)],
               'selection': selection_of(proj), 'selection_plan': sorted(SEL_PLAN, key=lambda x: x['t'])},
              open(os.path.join(proj, 'work', 'story_meta.json'), 'w'), ensure_ascii=False, indent=1)
    theme_used(proj, end)
    M = json.load(open(os.path.join(proj, 'work', 'story_meta.json')))
    sel = M['selection']
    rows = []
    for it in M['intent']:
        s_ = [x for x in sel if x['t0'] <= it['t'] + 0.05]
        rows.append(dict(it, selection=s_[-1] if s_ else None))
    json.dump(rows, open(os.path.join(proj, 'intent.json'), 'w'), ensure_ascii=False, indent=1)
