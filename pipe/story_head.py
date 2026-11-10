#!/usr/bin/env python3
import math
# 場面表（yt-henshu-pipe が組んだ）：頭＝この紙（pipe/story_head.py）・中身＝章ごとに AI が書いた節（work/bamen/ch*.py）・終わり＝pipe/story_tail.py
#   作りは面談前VSL v12（state/yt-evervsl-1019/loomzen/story.py）と同じ：薄い灰の地に線画の透かし・左上の赤い章札・黄のマーカー見出し・
#   黒いピクトグラムの図解・赤の帯・白縁の赤明朝・紺の字幕・ぼかし重ね。秒は書かず、言葉の頭のコマ（onset.py）に置く
import os, sys, re
PROJ = os.environ.get('PROJ') or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ)
from ki1 import *
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
from onset import Onset
# v14（依頼主 10/19 19:12「アニメーションのバリエーションを最大に・図解アニメーション・切り替えは多いほど良い」）：動く図解・出方・地を足す（pipe/zukai.py）
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/pipe'))
from zukai import kazu_up, bars_up, sen_graph, en_graph, maru, shitasen, chk, atsumaru, hyou_umeru, kaidan, tsunagu, sumaho, SPOT, KIIRO, AKA_JI, AO_JI, yoru, DUR as _ZDUR, ANIM_KATA, PART_KATA, TR_KATA
import zukai as _zk
_dd0 = Elem.default_dur
Elem.default_dur = lambda self: _ZDUR.get(self.anim) or _dd0(self)
_yaji0 = yaji
def yaji(direction='right', length=120, width=70, color='#e3141b'):
    im = _yaji0(direction, length, width, color); im.info['pipe_dir'] = direction; return im
for _im, _k in ((SPOT, 'スポットの地'), (KIIRO, '色の地（赤・黄・青）'), (AKA_JI, '色の地（赤・黄・青）'), (AO_JI, '色の地（赤・黄・青）')): _im.info['pipe_ji'] = _k
# 拭いて出す（wipe）の最初のコマに、帯の左の縁だけが細い縦棒で1コマ出ていた（作業AI 10/19：0:44.99 の青い縦棒・anim.Elem.wipe は幅0から開く）
#   → 1字目の幅（部品の高さ）から開き、最初の数コマは薄く入れる。字の部品（Text）は行ごとに出す元の形のまま
import anim as _anim
def _wipe_bou_nashi(self, cv, im, x, y, p, a_out):
    w0 = min(im.width, im.height)
    w = int(w0 + (im.width - w0) * ease_in_out(p))
    if w > 0: paste_safe(cv, with_alpha(im.crop((0, 0, w, im.height)), a_out * clamp(p * 4)), x, y)
_anim.Elem.wipe = _wipe_bou_nashi
ON = Onset(PROJ); L = lambda n: ON.line(n); K = lambda piece, n: ON.at(piece, n)
import subprocess as _sp, json as _pj
END = float(os.environ.get('RENSHU_END') or round(float(_sp.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(PROJ, 'work', 'vocals.wav')], capture_output=True, text=True).stdout) - 0.02, 2))
CX = W // 2
LBL = None   # 左上の章の札（つかみの後から常に出す）
CH = ''      # いま組んでいる章（AI の節ごとに設定する・検査で使う）

# 素材の種類の記録（素材一覧 sozai-ichiran.json の「使った秒」を自動で書くため）：部品の絵に種類を貼り、置いた秒を USED に残す
USED = []
def _shurui(fn, kind, name=None):
    def w(*a, **k):
        im = fn(*a, **k)
        try: im.info['pipe_shurui'] = kind; im.info['pipe_name'] = name or fn.__name__; im.info['pipe_arg'] = str(a[0]) if a else ''
        except Exception: pass
        return im
    w.__name__ = fn.__name__; return w
for _n, _k in (('ic', '挿絵'), ('icl', '挿絵'), ('iclab', '挿絵'), ('hito_ic', '挿絵'), ('hito_mure', '挿絵'), ('ninmure', '挿絵'),
               ('jin', 'イラスト'), ('card3', '図解'), ('yaji', '図解'), ('hyou', '図解'), ('bars', '図解'), ('waku', '図解'),
               ('gamen', '実際の画面'), ('logo', 'ロゴ')):
    if _n in globals(): globals()[_n] = _shurui(globals()[_n], _k)
# 画面に出した字を部品に覚えさせる（字幕と帯の食い違いの検査 pipe/kensa_bamen.py が使う）
def _moji(fn):
    def w(*a, **k):
        im = fn(*a, **k)
        try: im.info['pipe_text'] = ' '.join(str(x) for x in a if isinstance(x, str))
        except Exception: pass
        return im
    w.__name__ = fn.__name__; return w
for _n in ('midashi', 'oaka', 'ao', 'kin_l', 'kin', 'obi_aka', 'aka_box', 'kon', 'fuki', 'fuki_hai', 'card_hai', 'card_ao', 'card_kuro', 'check', 'tag', 'pink', 'waku', 'kazu'):
    if _n in globals(): globals()[_n] = _moji(globals()[_n])
# v14：動く図解も種類と名前を貼る（素材一覧・型の数え）
for _n, _k in (('kazu_up', '図解'), ('bars_up', '図解'), ('sen_graph', '図解'), ('en_graph', '図解'), ('hyou_umeru', '図解'), ('kaidan', '図解'), ('tsunagu', '図解'),
               ('maru', '図解'), ('shitasen', '図解'), ('chk', '図解'), ('atsumaru', '挿絵'), ('sumaho', '実際の画面')):
    globals()[_n] = _shurui(globals()[_n], _k)
# どの部品の関数で作った絵かを全部の部品に貼る（表現の型を数える kata_v14.py が使う）
def _fn(fn):
    def w(*a, **k):
        im = fn(*a, **k)
        try: im.info.setdefault('pipe_fn', fn.__name__)
        except Exception: pass
        return im
    w.__name__ = fn.__name__; return w
for _n in ('midashi', 'oaka', 'ao', 'kin_l', 'kin', 'obi_aka', 'aka_box', 'kon', 'fuki', 'fuki_hai', 'card_hai', 'card_ao', 'card_kuro', 'check', 'tag', 'pink', 'waku', 'kazu',
           'ic', 'icl', 'iclab', 'hito_ic', 'hito_mure', 'ninmure', 'jin', 'card3', 'yaji', 'hyou', 'bars', 'gamen', 'logo', 'batsu', 'kazu_up', 'bars_up', 'sen_graph', 'en_graph',
           'hyou_umeru', 'kaidan', 'tsunagu', 'maru', 'shitasen', 'chk', 'atsumaru', 'sumaho'):
    if _n in globals(): globals()[_n] = _fn(globals()[_n])
KATALOG = []   # 部品が動いて出た記録（秒・出方・部品・章）
_photo0 = photo
def photo(name, *a, **k):
    f = _photo0(name, *a, **k); f.pipe_shurui = '全画面挿絵'; f.pipe_name = name; return f

def T(t, img, x, y, a='pop', dur=None, anchor='cc', n=10):
    # 画面からはみ出さない：幅が画面の幅−60を超える字は縮め、中心の部品は端から30の内側へ寄せる（全編の一覧で大字が切れていた・10/19）
    if anchor == 'cc' and not (img.width == W and img.height == H):   # 白い幕（画面と同じ大きさ）だけは除く
        if img.width > W - 60:
            k = (W - 60) / img.width; inf = dict(img.info); sz = (int(img.width * k), int(img.height * k)); img = img.resize(sz, Image.LANCZOS); img.info.update(inf)
            if inf.get('pipe_dyn'): _f0 = inf['pipe_dyn']; img.info['pipe_dyn'] = lambda p, _f0=_f0, sz=sz: _f0(p).resize(sz, Image.BILINEAR)
        x = min(max(x, img.width // 2 + 30), W - img.width // 2 - 30); y = min(max(y, img.height // 2 + 20), H - img.height // 2 - 20)
    if getattr(img, 'info', None) and img.info.get('pipe_shurui'):   # 一度に出す（a='none'）部品も画面に出ているので数える（10/21 yt-henshu-pipe：none の人物・ロゴが素材一覧から抜けて門のルール1・3・7が外れていた）
        USED.append({'t': round(t, 2), 'shurui': img.info['pipe_shurui'], 'name': img.info.get('pipe_name'), 'arg': img.info.get('pipe_arg'), 'ch': CH})
    if a == 'grow' and not (getattr(img, 'info', None) or {}).get('pipe_dyn'): a = 'egaku'   # 動く図解でない絵の grow は描き出しに
    e = R(t, img, x, y, anchor, a, dur=dur); e.nchar = n; e.pipe_ch = CH
    if a != 'none':
        inf = getattr(img, 'info', None) or {}
        KATALOG.append({'t': round(t, 3), 'anim': a, 'fn': inf.get('pipe_fn') or inf.get('pipe_name') or '', 'zukai': inf.get('pipe_zukai') or '', 'ch': CH})
    return e
# 場面の切り替え方の記録（v13・手本の作者さん対v12の比べ 10/19：v12は3種類で「動く切り替え」「字・帯だけ差し替え」が0回）
#   全消し（1コマ）／前を残して足す／重ねる（後ろをぼかす・暗くする）／動く切り替え（zoom・slide・fade・flash・blur）／字・帯だけ差し替え／実写・画面・写真へ
TRLOG = []
TR_KINDS = {'zoom': 0.30, 'slide': 0.28, 'fade': 0.26, 'flash': 0.24, 'blur': 0.30, 'hosha': 0.30, 'yokobure': 0.26, 'glitch': 0.24, 'anten': 0.30}   # v14：放射ズーム・横ぶれ・グリッチ・暗転を足した
class Stack:
    """足し算で積む（同じ話題の間は前の部品を残し、新しい部品だけ動く）。new で全消し
    tr＝前の画面からの動く切り替え（zoom 寄って入る／slide 横へ押し出す／fade 溶ける／flash 白く光る／blur ぼけて替わる）"""
    def __init__(self, bg=None, tr=None):
        self.bg = bg if bg is not None else LIGHT; self.items = []; self._bg_logged = False
        if tr is not None and tr not in TR_KINDS: raise ValueError('切り替え tr は %s のどれか（%s と書かれた）' % ('・'.join(TR_KINDS), tr))
        self.tr = tr; self._first = True
    def _sc(self, t, elems, kind, first_img=None):
        """場面を1つ足し、切り替え方を記録する（新しい Stack の最初の場面だけ 全消し／動く切り替え／実写・画面・写真へ）"""
        sc = add(Sc(t, 0, elems, bg=self.bg, ring=False, trans=0.0, zoom=None))
        if self._first:
            info = getattr(first_img, 'info', None) or {}
            if self.tr: kind = '動く切り替え'; sc.trk = self.tr
            elif getattr(self.bg, 'pipe_shurui', None) or info.get('pipe_shurui') == '実際の画面': kind = '実写・画面・写真へ'
            else: kind = '全消し（1コマ）'
            self._first = False
        bgk = getattr(self.bg, 'pipe_ji', None) or (getattr(self.bg, 'info', None) or {}).get('pipe_ji') or ('暗い地' if self.bg is DARK else ('写真の地' if getattr(self.bg, 'pipe_shurui', None) else '明るい地'))
        TRLOG.append({'t': round(t, 3), 'kind': kind, 'tr': getattr(sc, 'trk', None), 'ch': CH, 'ji': bgk})
        return sc
    def _logbg(self, t):
        if not self._bg_logged and getattr(self.bg, 'pipe_shurui', None):
            USED.append({'t': round(t, 2), 'shurui': self.bg.pipe_shurui, 'name': 'photo', 'arg': self.bg.pipe_name, 'ch': CH}); self._bg_logged = True
    def add(self, t, img, x, y, a='pop', dur=None, anchor='cc', se=None, n=10, drop=0):
        self._logbg(t)
        if drop: self.items = self.items[:-drop] if drop > 0 else []
        keep = [T(t, im, xx, yy, 'none', None, an) for im, xx, yy, an in self.items]
        if LBL is not None: keep.insert(0, T(t, LBL, 0, 0, 'none', None, 'lt'))
        self._sc(t, keep + [T(t, img, x, y, a, dur, anchor, n)], '字・帯だけ差し替え' if getattr(self, '_swap', False) else '前を残して足す', img)
        self.items.append((img, x, y, anchor))
        if se: sfx(t, se)
        return self
    def swap(self, t, img, a='type', dur=None, se=None, n=None, x=None, y=None):
        """字・帯だけ差し替え：いちばん新しい部品（帯・見出し・札）を同じ場所で別の字に替える。ほかの部品は残す"""
        if not self.items: raise ValueError('swap は積んだ部品がある Stack でだけ使う（先に add する）')
        _im, xx, yy, an = self.items[-1]
        if n is None: n = max(1, len(re.sub(r'<[^>]+>|\s', '', (getattr(img, 'info', None) or {}).get('pipe_text', '')))) if (getattr(img, 'info', None) or {}).get('pipe_text') else 10
        self._swap = True
        try: return self.add(t, img, xx if x is None else x, yy if y is None else y, a, dur, an, se, n, drop=1)
        finally: self._swap = False
    def over(self, t, img, x, y, a='blur', dur=0.3, se='don', veil=60):
        """期1の「上から大字」：積んだ画面に暗い幕をかけ、その上に大きな言い切りを重ねる（幕は残る）"""
        self._logbg(t)
        from PIL import ImageFilter as _F   # 10月の4本：前の部品をぼかしてから重ねる
        self.items = [(im.filter(_F.GaussianBlur(7)) if im.width < W else im, xx, yy, an) for im, xx, yy, an in self.items]
        kuro = os.environ.get('OVER_KURO', '1') == '1'   # 手本15本の半分は暗い地で埋まり方が高い（v12 9版目）
        self.items.append((Image.new('RGBA', (W, H), (14, 14, 18, max(veil, 205)) if kuro else (246, 246, 246, veil)), 0, 0, 'lt'))
        keep = [T(t, im, xx, yy, 'none', None, an) for im, xx, yy, an in self.items]
        if LBL is not None: keep.insert(0, T(t, LBL, 0, 0, 'none', None, 'lt'))
        self._sc(t, keep + [T(t, img, x, y, a, dur, 'cc')], '重ねる（後ろをぼかす・暗くする）', img)
        self.items.append((img, x, y, 'cc'))
        if se: sfx(t, se)
        return self
    def multi(self, t, parts, se=None):
        self._logbg(t)
        keep = [T(t, im, xx, yy, 'none', None, an) for im, xx, yy, an in self.items]
        if LBL is not None: keep.insert(0, T(t, LBL, 0, 0, 'none', None, 'lt'))
        self._sc(t, keep + [T(t, img, x, y, a, dur, 'cc') for img, x, y, a, dur in parts], '前を残して足す', parts[0][0] if parts else None)
        self.items += [(img, x, y, 'cc') for img, x, y, a, dur in parts]
        if se: sfx(t, se)
        return self
def I(t, role, what, how, why=''): intent(t, role, what, how, why)
# 動く切り替えの描き方（v13）：前の場面と次の場面を字幕なしで描いて混ぜ、字幕は最後に上から描く（字幕は切り替えで動かさない）。
#   どれも最初のコマから画面全体が変わる形だけにした（左から拭く形は、右の部品が言葉より遅れて見えるので使わない＝門のルール5）
import ki1 as _k1, bisect as _bis
from PIL import ImageFilter as _IFt
_fa0 = frame_at
_T0 = None
def _raw(sc, t): return _k1._sc_render0(sc, t)
def _ji(cv, t):
    J = _k1.JIMAKU
    if J:
        i = _bis.bisect_right(J, (t, 1e9, '')) - 1
        if i >= 0 and J[i][0] <= t < J[i][1]:
            im = _k1._jimaku_img(J[i][2]); cv.alpha_composite(im, ((W - im.width) // 2, H - im.height - 14))
    return cv
def _scale(im, s):
    if abs(s - 1) < 0.003: return im
    if s > 1:
        cw, ch = int(W / s), int(H / s); return im.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
    sw, sh = int(W * s), int(H * s); out = Image.new('RGBA', (W, H), (246, 246, 246, 255)); out.alpha_composite(im.resize((sw, sh), Image.BILINEAR), ((W - sw) // 2, (H - sh) // 2)); return out
def frame_at(t, subs=None):
    global _T0
    if _T0 is None or len(_T0) != len(SCENES): _T0 = [s.t0 for s in SCENES]
    i = _bis.bisect_right(_T0, t) - 1
    # 切り替えは場面の頭から始める（元の形に戻した・10/20 r10：頭の前に終える形にすると、切り替えの間に中身の無い地だけのコマが17か所・計83コマ出た。手本の作者さんの手本5本の頭10分では0〜1か所）
    #   部品が言葉の頭で見えるよう、白抜け・暗転・溶ける切り替えは「次の場面が最初の2コマで半分以上見える」曲線にした（r8 1141 の白抜けで宝箱が4〜7コマ遅れた分）
    if i >= 1:
        cur = SCENES[i]; kd = getattr(cur, 'trk', None)
        if kd and t < cur.t0 + TR_KINDS[kd]:
            p = clamp((t - cur.t0) / TR_KINDS[kd]); e = ease_out(p); prev = SCENES[i - 1]
            a = _raw(prev, min(t, prev.t1 - 0.001)); b = _raw(cur, t)
            w2 = min(1.0, 0.5 + 0.5 * p * 4) if p > 0 else 0.5   # 次の場面の見え方の下限：頭のコマで5割・4分の1で全部（言葉の頭で部品が見える）
            if kd == 'fade': cv = Image.blend(a, b, max(w2, ease_in_out(min(1.0, p * 1.15))))
            elif kd == 'zoom':   # 前の画面が寄りながら消え、次の画面が少し大きい所から寄って止まる
                cv = Image.blend(_scale(a, 1.0 + 0.25 * e), _scale(b, 1.16 - 0.16 * e), max(w2, min(1.0, e * 1.25)))
            elif kd == 'slide':  # 次の画面が右から入り、前の画面を左へ押し出す
                dx = int(W * (1 - e)); cv = Image.new('RGBA', (W, H), (246, 246, 246, 255))
                if dx > 0: cv.paste(a.crop((W - dx, 0, W, H)), (0, 0))
                if dx < W: cv.paste(b.crop((0, 0, W - dx, H)), (dx, 0))
            elif kd == 'flash':  # 白く光って替わる
                wh = Image.new('RGBA', (W, H), (255, 255, 255, 255))
                cv = Image.blend(Image.blend(a, b, w2), wh, 0.55 * math.sin(math.pi * p))   # 白く光りながら次の場面へ（真っ白のコマを作らない）
            elif kd == 'hosha':  # 放射ズーム：前の画面が中心へ吸い込まれるように寄ってぼけ、次の画面が大きい所から寄って止まる
                aa = _scale(a, 1.0 + 0.6 * e).filter(_IFt.GaussianBlur(4 + 10 * e)); bb = _scale(b, 1.35 - 0.35 * e)
                if e < 0.6: bb = bb.filter(_IFt.GaussianBlur(10 * (1 - e / 0.6)))
                cv = Image.blend(aa, bb, max(w2, min(1.0, e * 1.3)))
            elif kd == 'yokobure':   # 横ぶれ：前の画面が横に流れてぶれ、次の画面が反対から流れ込んで止まる
                dx = int(W * 0.5 * e); k_ = 1 + int(7 * (1 - abs(0.5 - e) * 2))
                aa = Image.new('RGBA', (W, H), (246, 246, 246, 255)); aa.paste(a, (-dx, 0))
                bb = Image.new('RGBA', (W, H), (246, 246, 246, 255)); bb.paste(b, (int(W * 0.5 * (1 - e)), 0))
                cv = Image.blend(aa, bb, max(w2, min(1.0, e * 1.15)))
                if k_ > 1: cv = cv.resize((W // k_, H), Image.BILINEAR).resize((W, H), Image.BILINEAR)
            elif kd == 'glitch':     # グリッチ：色ずれと横の刻みで次の画面に替わる
                import random as _rn
                rg = _rn.Random(int(p * 40)); base = b if p > 0.25 else a; cv = base.copy(); off = int(26 * (1 - p))
                if off > 1:
                    r_, g_, b_, al_ = base.split(); cv = Image.merge('RGBA', (r_.transform(r_.size, Image.AFFINE, (1, 0, off, 0, 1, 0)), g_, b_.transform(b_.size, Image.AFFINE, (1, 0, -off, 0, 1, 0)), al_))
                    for _k in range(6):
                        yy = rg.randint(0, H - 40); hh = rg.randint(10, 60); sl = (a if rg.random() < 0.5 else b).crop((0, yy, W, yy + hh)); cv.paste(sl, (rg.randint(-60, 60), yy))
            elif kd == 'anten':      # 暗転：前の画面が暗く落ち、次の画面が暗い所から明るくなる
                blk = Image.new('RGBA', (W, H), (0, 0, 0, 255))
                cv = Image.blend(Image.blend(a, b, w2), blk, 0.55 * math.sin(math.pi * p))   # 暗くなりながら次の場面へ（真っ黒のコマを作らない）
            else:                # blur：前の画面がぼけて消え、次の画面がぼけからくっきり
                r = 16 * (1 - e); cv = Image.blend(a.filter(_IFt.GaussianBlur(10 + 10 * e)), b.filter(_IFt.GaussianBlur(r)) if r > 0.5 else b, max(w2, min(1.0, e * 1.2)))
            return _ji(cv, t).convert('RGB')
    return _fa0(t)
KOKUCHI_FROM = None   # 告知・CTA の章が始まる秒（BGM を kokuchi に替える）。章の節が設定する

