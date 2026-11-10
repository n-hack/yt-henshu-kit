#!/usr/bin/env python3
# 編集の指示書（EDL・yt-edl が1文ずつ判断で書いたもの）を、書いてあるとおりに場面へ組む（v14・依頼主 10/19 19:25〜19:44）
#   道具の決まりで部品・出方・切り替えを選び直さない。書いていない所だけ既定の値（EDL-SCHEMA.md）。
#   v13 までの場面表（AI が章ごとに書く節）の代わりに、story.py の中から kumitate(globals(), <edl>) で呼ぶ。
#   足したもの：動く人物（連番・透過動画・1枚絵）／出たあとも動き続ける部品（揺れ・浮く・脈打つ・回る）／部品の移動／
#              表情の差し替え／カメラ（寄る・引く・横・縦・手持ちの揺れ・ドンの揺れ。字幕と章札は動かさない）／大きな立体文字
import os, re, json, math, glob, copy, subprocess, hashlib
from PIL import Image, ImageFilter, ImageChops

JIN_DIR = os.environ.get('JIN_DIR') or os.path.expanduser('~/rin6/state/yt-henshu/jinbutsu')   # 試しのときだけ別の置き場
POS = {'左上': (420, 270), '上': (960, 240), '右上': (1500, 270), '左': (430, 560), '中': (960, 540), '右': (1490, 560),
       '左下': (430, 780), '下': (960, 800), '右下': (1490, 780), '中左': (700, 540), '中右': (1220, 540)}
SIZE = {'小': 240, '中': 380, '大': 560, '特大': 760}
JI_NAME = {'明るい': 'LIGHT', '暗い': 'DARK', 'スポット': 'SPOT', '赤': 'AKA_JI', '黄': 'KIIRO', '青': 'AO_JI'}
FPS_CLIP = 30000 / 1001
MOJI3D_IRO = {'青': ([(0, '#9be4ff'), (0.5, '#2f95ee'), (1, '#1450c8')], (12, 34, 90)),
              '赤': ([(0, '#ffb08a'), (0.5, '#f0281a'), (1, '#a80000')], (70, 0, 0)),
              '金': ([(0, '#fff6b0'), (0.5, '#ffc21a'), (1, '#c87800')], (90, 50, 0)),
              '白': ([(0, '#ffffff'), (1, '#dfe6ee')], (40, 44, 60)),
              '金明': ([(0, '#ffffff'), (0.45, '#fff07a'), (1, '#ffc400')], (120, 70, 0)),
              '金濃': ([(0, '#e08c10'), (0.5, '#c06a00'), (1, '#7a3c00')], (60, 28, 0))}   # 明るい地の上の金（10/22 依頼主「視認性悪い」：薄い金×明るい灰はOCRでも読めなかった「30万円」）   # 暗い地の上の金（作業AI 10/19 21:0x：暗い地に暗い金の字が読めない）
OKIKAE = [   # 指示書の imi に書いた物 → parts に要る部品の名前の一部（無ければ「置き換え」として止める・作業AI 10/19 21:0x）
    ('カレンダー', ('calendar', 'himekuri')), ('表彰台', ('hyoushoudai',)), ('宝箱', ('takarabako', 'tokuten')), ('波', ('nami',)),
    ('封筒', ('fuutou', 'haitatsu', 'zu_mail')), ('再生ボタン', ('saisei',)), ('扉', ('tobira', 'shinkou_bar')), ('進み棒', ('shinkou_bar',)),
    ('電球', ('denkyu', 'teian')), ('荷物', ('nimotsu', 'shitajiki', 'hakobu')), ('日めくり', ('himekuri',)), ('時計', ('tokei', 'sunadokei')),
    ('トンカチ', ('tonkachi',)), ('虫眼鏡', ('mushimegane',)), ('旗', ('hata',)), ('3つの台', ('dai3',)), ('スポットライト', ('spot',)),
    ('吹き出し', ('fuki', 'chat_', 'zu_chat', 'teian')),
]
OKIKAE_HITO = [(r'(?:^|[^A-Za-z])M(?:[ がのはとを（]|$)', 'chara_', 'M（自社キャラ）'), (r'(?:^|[^A-Za-z])R(?:[ がのはとを（]|$)', 'robo_', 'R（ロボ）'), (r'(?:^|[^A-Za-z])C(?:[ がのはとを（]|$)', 'chat_', 'C（吹き出し顔の箱）')]
# 絵を大きく置く（作業AI 10/19 21:4x・ルール9：門の数え方は変えず、主役の人物は画面の高さの45〜60%・部品は透明な枠を内容の大きさに切ってから置く）
SHUYAKU_H = (0.45, 0.52, 0.60)   # 主役の人物の「見える中身」の高さ（画面の高さに対する割合：下限・ねらい・上限）
WAKI_H = 0.36                    # 主役でない人物・物の見える中身の高さの下限
HITO_SOKO = 950                  # 人物の足もと（字幕帯の上）
# 地は無地の淡い色（作業AI 10/19 21:4x：背景に薄く出ていた大きな人物の線画を全場面で外す・場面ごとに色を変えてよい）
JI_MUJI = ['#f4f1ea', '#e8f1f8', '#f7ebe4', '#e9f4ea', '#f0ebf6', '#f8f2dc', '#e6f1f3', '#f6e8ee']
JI_KURAI = '#1d1f26'
_MUJI = {}
def muji(W, H, hexc):
    if hexc not in _MUJI: _MUJI[hexc] = Image.new('RGBA', (W, H), tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
    return _MUJI[hexc]
def kiritoru(img):
    """透明な枠を内容の大きさに切る（動く図解・ほぼ枠いっぱいの絵はそのまま）"""
    if img is None or img.mode != 'RGBA' or (getattr(img, 'info', None) or {}).get('pipe_dyn'): return img
    b = img.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()
    if not b or (b[2] - b[0]) * (b[3] - b[1]) > 0.97 * img.width * img.height: return img
    inf = dict(img.info); im2 = img.crop(b); im2.info.update(inf); return im2
_NAIYOU = {}
def clip_naiyou(G, name, h):
    """連番の各コマで見える中身の高さ・幅（枠に対する割合の中央値）・足もとの空き（割合）・枠の横縦比"""
    key = (name, h)
    if key in _NAIYOU: return _NAIYOU[key]
    fr, lp = clip_frames(G, name, h)
    if not fr: _NAIYOU[key] = None; return None
    hs, ws, bs = [], [], []
    for im in fr[::max(1, len(fr) // 12)]:
        b = im.getchannel('A').point(lambda v: 255 if v > 24 else 0).getbbox()
        if b: hs.append((b[3] - b[1]) / im.height); ws.append((b[2] - b[0]) / im.width); bs.append((im.height - b[3]) / im.height)
    med = lambda a: sorted(a)[len(a) // 2] if a else 1.0
    _NAIYOU[key] = (med(hs), med(ws), med(bs), fr[0].width / fr[0].height); return _NAIYOU[key]
GAMEN_FOCUS = {'38_90': (0.83, 0.30), '33_90': (0.55, 0.70)}   # 画面のスクショで読ませたい所（スクショの中の割合）：38_90＝右の自社キャラ式AIエージェント・33_90＝「3体が同時に動いています」
GAMEN_MIN_W = 0.74   # 画面のスクショは画面の幅の7割以上（作業AI 10/19 21:4x：s034・s036 が小さくて読めない）
DE_P0 = 0.35   # 出方は 35% の所から始める：0% から始めると言葉の頭のコマでは透明で、見えるのが2〜7コマ遅れた（r6 門のルール5 本当のずれ17件・作業AI 10/19 21:0x「その部品そのものが出た瞬間で測る」）
ICON3D_MAX_W = 0.30   # 立体アイコンは主役にしない：幅は画面の3割まで・人物と大字に重ねない（作業AI 10/19 21:0x）
LOG = {'shots': 0, 'parts': 0, 'jinbutsu': 0, 'ugoku_bubun': 0, 'camera': 0, 'mitsukaranai': [], 'buhin_nashi': [], 'kirikae': {}, 'kotoba_zure': [], 'hoshii': []}

# ---------------- 部品の絵 ----------------
def moji3d(G, text, iro='青', size=150):
    """大きな立体文字（見本 IMG_8721「何で稼ぐ？」の形）：斜体・上から下へ色の段々・白い縁・右下へ奥行きの厚み・影"""
    kit = G['kit']; fill, deep = MOJI3D_IRO.get(iro, MOJI3D_IRO['青'])
    face = kit.deco(text, size, name=G['GOTH'], fill=('v', fill), strokes=[(10, '#ffffff')], italic=0.16, pad=40)
    body = kit.deco(text, size, name=G['GOTH'], fill=deep, strokes=[(10, deep)], italic=0.16, pad=40)
    d = max(6, size // 14)
    out = Image.new('RGBA', (face.width + d + 8, face.height + d + 8), (0, 0, 0, 0))
    sh = Image.new('RGBA', out.size, (0, 0, 0, 0)); blk = Image.new('RGBA', face.size, (0, 0, 0, 110)); sh.paste(blk, (d + 6, d + 8), body.getchannel('A'))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    for k in range(d, 0, -1): out.alpha_composite(body, (k, k))
    out.alpha_composite(face, (0, 0))
    bb = out.getbbox(); out = out.crop(bb) if bb else out
    out.info.update({'pipe_text': text, 'pipe_fn': 'moji3d', 'pipe_shurui': '図解', 'pipe_name': 'moji3d'})
    return out

def icon3d(G, name, iro='青', h=300):
    """色のついた立体のアイコン：上から下へ色の段々・白い縁・右下へ奥行き・影（黒い単色アイコンの代わり）"""
    try: base = G['ic'](name, int(h * 0.9), '#ffffff')
    except Exception: return None
    m = base.getchannel('A'); bb = m.getbbox()
    if not bb: return None
    m = m.crop(bb); fill, deep = MOJI3D_IRO.get(iro, MOJI3D_IRO['青']); w_, h_ = m.size; pad = 24; d = max(6, h // 18)
    gd = Image.linear_gradient('L').resize((w_, h_))
    top = Image.new('RGBA', (w_, h_), G['kit'].C(fill[0][1]) + (255,)); bot = Image.new('RGBA', (w_, h_), G['kit'].C(fill[-1][1]) + (255,)); G2 = Image.composite(bot, top, gd)
    out = Image.new('RGBA', (w_ + pad * 2 + d, h_ + pad * 2 + d), (0, 0, 0, 0))
    rim = Image.new('L', (w_ + 30, h_ + 30), 0); rim.paste(m, (15, 15)); rim = rim.filter(ImageFilter.MaxFilter(15))
    sh = Image.new('RGBA', out.size, (0, 0, 0, 0)); sh.paste(Image.new('RGBA', rim.size, (0, 0, 0, 110)), (pad - 15 + d + 6, pad - 15 + d + 8), rim); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    for k in range(d, 0, -1): out.paste(Image.new('RGBA', rim.size, deep + (255,)), (pad - 15 + k, pad - 15 + k), rim)
    out.paste(Image.new('RGBA', rim.size, (255, 255, 255, 255)), (pad - 15, pad - 15), rim)
    out.paste(G2, (pad, pad), m)
    out.info.update({'pipe_fn': 'icon3d', 'pipe_shurui': '挿絵', 'pipe_name': name})   # 形は Material Symbols（素材サイト・Apache 2.0）＝挿絵として数える
    return out

def _find_file(G, name, exts):
    roots = [JIN_DIR, os.path.join(G['PROJ'], 'sozai'), os.path.expanduser('~/rin6/tools/yt-henshu/pipe/sozai'), G['SOZAI'],
             os.path.expanduser('~/rin6/state/yt-evervsl-1019/e')]
    if os.path.isabs(os.path.expanduser(name)) and os.path.exists(os.path.expanduser(name)): return os.path.expanduser(name)
    for r in roots:
        for ext in exts:
            for p in glob.glob(os.path.join(r, '**', name + ext), recursive=True): return p
    return None

_CLIP = {}
_BOX = {}
# 実際の画面の録画（chat-rokuga の real-*.mp4・1920x1080）：左右の空きを切って字を大きく見せ、下の「AI であり、間違えることがあります」の行は切って隠す（作業AI 10/19 21:3x・AIラベルを外す決まり）
REAL_CROP = {'real-claude': (200, 0, 1720, 1016), 'real-chatgpt': (200, 0, 1720, 1080)}
REAL_MIN_H = 760   # 実際の画面は字が小さくならない高さより小さく置かない（PC 幅のまま）
_META = None
def clip_meta(name):
    """clips/meta.json の1行（loop・dur・tsuzuki）"""
    global _META
    if _META is None:
        try: _META = json.load(open(os.path.join(JIN_DIR, 'clips', 'meta.json')))
        except Exception: _META = {}
    return _META.get(name) or {}
def sw_h(G, base, new, h):
    """表情の差し替え・続きの部品の高さ：前の部品と見える中身の高さをそろえる（枠の大きさが違う部品で人物が急に小さくなる・s042 の旗・s044）。
    場面まるごとの芝居（shibai_）は元の絵の縮尺をそろえる（人が去ったあとに残る人の大きさが跳ねない）"""
    if not base: return h
    if str(base).startswith('shibai_'):
        clip_frames(G, new, h)
        return int(h * _BOX.get(new, 1) / max(1, _BOX.get(base, 1))) if base in _BOX and new in _BOX else h
    a, b = clip_naiyou(G, base, h), clip_naiyou(G, new, h)
    if not a or not b: return h
    return int(min(h * 1.6, max(h * 0.6, h * a[0] / max(0.05, b[0]))))
_KIRI = {}
def _kiri_frames(name, files):
    """連番を読んで全コマ同じ枠で切る（高さをそろえる前）。同じ絵を別の高さで使うときに読み直さない"""
    kk = (name, tuple(files))
    if kk in _KIRI: return _KIRI[kk]
    fr = []
    for f in files:
        im = Image.open(f).convert('RGBA')
        if name in REAL_CROP and im.size == (1920, 1080): im = im.crop(REAL_CROP[name])
        fr.append(im)
    # 全コマで同じ切り抜き（足もとの位置がコマごとにずれないように）
    box = None
    for im in fr:
        b = im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()   # ほぼ透明の帯は数えない
        if b: box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    if box: fr = [im.crop(box) for im in fr]
    _KIRI[kk] = fr
    while len(_KIRI) > 8: _KIRI.pop(next(iter(_KIRI)))
    return fr
RZ_DIR = os.environ.get('JIN_RZ_DIR') or os.path.expanduser('~/rin6/state/yt-henshu/jin_rz_cache')   # 高さをそろえた後の画素の控え（消しても作り直すだけ）
RZ_VER = 'v1'
_RZ_CODE = None
def _rz_code():
    # 控えの鍵に「切り抜きと高さそろえの書き方」も入れる（直したら古い控えは使わずに作り直す）
    global _RZ_CODE
    if _RZ_CODE is None:
        import inspect
        _RZ_CODE = hashlib.md5((inspect.getsource(_kiri_frames) + inspect.getsource(clip_frames) + repr(sorted(REAL_CROP.items())) + Image.__version__).encode()).hexdigest()[:12]
    return _RZ_CODE
def _rz_path(name, h, files, src=None):
    # 元が動画なら動画の名前・大きさ・時刻で（連番に書き出した先の時刻は門の写しで変わるので使わない）、連番・1枚絵ならその絵ごとに
    if src: sig = [RZ_VER, _rz_code(), name, h, REAL_CROP.get(name), src, [os.path.basename(f) for f in files]]
    else: sig = [RZ_VER, _rz_code(), name, h, REAL_CROP.get(name)] + [(f, os.path.getsize(f), int(os.path.getmtime(f))) for f in files]
    return os.path.join(RZ_DIR, hashlib.md5(repr(sig).encode()).hexdigest())
class _RzFrames:
    """控えの画素をファイルに写したまま（mmap）持ち、使うコマだけその場で絵にする並び（10/20 yt-hayasa：長い動画でメモリが尽きないように）。
    読み出す画素は控えの画素そのもの＝前と1つも変わらない。番号・長さ・飛ばし読み（[::k]）は list と同じに振る舞う"""
    def __init__(self, mm, size, infos, extra=None):
        self.mm, self.size, self.infos, self.extra = mm, size, infos, dict(extra or {}); self.sz = size[0] * size[1] * 4
    def __len__(self): return len(self.infos)
    def __bool__(self): return len(self.infos) > 0
    def _one(self, i):
        im = Image.frombytes('RGBA', self.size, self.mm[i * self.sz:(i + 1) * self.sz]); im.info.update(self.infos[i]); im.info.update(self.extra); return im
    def __getitem__(self, k):
        if isinstance(k, slice): return [self._one(i) for i in range(*k.indices(len(self)))]
        if k < 0: k += len(self)
        if not 0 <= k < len(self): raise IndexError(k)
        return self._one(k)
    def __iter__(self): return (self._one(i) for i in range(len(self)))
def _rz_load(p):
    import pickle, mmap
    try:
        with open(p + '.meta', 'rb') as f: M = pickle.load(f)
        with open(p + '.raw', 'rb') as f:
            w, hh, n = M['size'][0], M['size'][1], M['n']
            if os.fstat(f.fileno()).st_size != w * hh * 4 * n or n == 0: return None
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try: os.utime(p + '.raw')   # 使った印（上限を超えたときは使っていない順に消す）
        except OSError: pass
    except (OSError, EOFError, ValueError, pickle.UnpicklingError): return None
    return _RzFrames(mm, (w, hh), M['info']), M['box']
def _rz_save(p, fr, box):
    import pickle
    try:
        os.makedirs(RZ_DIR, exist_ok=True); tmp = p + '.%d.tmp' % os.getpid()
        with open(tmp + 'r', 'wb') as f:
            for im in fr: f.write(im.tobytes())
        with open(tmp + 'm', 'wb') as f: pickle.dump({'size': fr[0].size, 'n': len(fr), 'box': box, 'info': [dict(im.info) for im in fr]}, f)
        os.replace(tmp + 'r', p + '.raw'); os.replace(tmp + 'm', p + '.meta')
        _rz_trim(p)
    except Exception: pass
RZ_MAX_GB = float(os.environ.get('JIN_RZ_MAX_GB') or 150)   # 作り置きの上限（10/20 作業AI：内蔵を食わないように。超えたら使っていない順に消す・消しても次に要るとき作り直すだけ）
def _rz_trim(keep):
    try:
        ent = []
        for e in os.scandir(RZ_DIR):
            if e.name.endswith('.raw'):
                st = e.stat(); ent.append((st.st_mtime, st.st_size, e.path[:-4]))
        tot = sum(x[1] for x in ent); lim = RZ_MAX_GB * 2**30
        for mt, sz, base in sorted(ent):
            if tot <= lim: break
            if base == keep: continue
            for ext in ('.raw', '.meta'):
                try: os.remove(base + ext)
                except OSError: pass
            tot -= sz
    except OSError: pass
def clip_frames(G, name, h):
    """動く人物：<名前>/ の連番PNG・<名前>.mov/.webm（透過）・<名前>.png（1枚）を、高さ h にそろえた絵の並びで返す（[絵], ループするか）"""
    key = (name, h)
    if str(name).startswith(('chara_', 'shibai_chara_')): raise SystemExit('🔴 使ってはいけないキャラ（自社キャラの頭＋線の体・依頼主 10/20 23:45「一生使わないで」）：%s → ~/rin6/state/yt-henshu/kinshi/chara-boujin' % name)
    if key in _CLIP: return _CLIP[key]
    d = os.path.join(JIN_DIR, name); files = []; loop = bool(clip_meta(name).get('loop', True)); src = None
    meta = _find_file(G, name, ['.json'])
    if meta:
        try: loop = bool(json.load(open(meta)).get('loop', True))
        except Exception: pass
    if os.path.isdir(d): files = sorted(glob.glob(os.path.join(d, '*.png')))
    if not files:
        v = _find_file(G, name + '_kiri', ['.mov', '.webm', '.mp4']) or _find_file(G, name, ['.mov', '.webm', '.mp4'])   # 余白を切った版があれば先に（yt-jinbutsu clips/kiri.json）
        if v:
            cd = os.path.join(G['PROJ'], 'work', 'jin_cache', hashlib.md5(('%s|%d|%d' % (v, os.path.getmtime(v), os.path.getsize(v))).encode()).hexdigest()[:10])   # 部品が作り直されたら読み直す（10/19 22時台 左右の透明の帯の直し）
            if not glob.glob(os.path.join(cd, '*.png')):
                os.makedirs(cd, exist_ok=True)
                dec = ['-c:v', 'libvpx-vp9'] if v.endswith('.webm') else []
                subprocess.run(['nice', '-n', '19', 'ffmpeg', '-v', 'error', '-y'] + dec + ['-i', v, '-r', str(FPS_CLIP), '-pix_fmt', 'rgba', os.path.join(cd, '%04d.png')], check=True)
            files = sorted(glob.glob(os.path.join(cd, '*.png'))); src = (v, os.path.getsize(v), int(os.path.getmtime(v)))
    if not files:
        p = _find_file(G, name, ['.png', '.webp'])
        if p: files = [p]
    if not files: _CLIP[key] = (None, loop); return _CLIP[key]
    # 速さ（10/20 yt-hayasa）：同じ絵・同じ高さで前に作った並びがあれば、その画素をそのまま読む（作り方は変えない・画素は1つも変わらない）
    rz = _rz_path(name, h, files, src)
    got = _rz_load(rz)
    if got:
        fr, _BOX[name] = got
        if getattr(Image.open, '__module__', 'PIL.Image') != 'PIL.Image':   # 門（zettai-mon の trace）が読んだ絵を数えているときは、元の絵を開いたことを同じように残す
            for f in files: Image.open(f).close()
    else:
        fr = _kiri_frames(name, files)
        _BOX[name] = fr[0].height   # 元の絵での枠の高さ（差し替えで同じ縮尺にそろえるため）
        k = h / fr[0].height; sz = (max(1, int(fr[0].width * k)), h)
        fr = [im.resize(sz, Image.LANCZOS) for im in fr]
        _rz_save(rz, fr, _BOX[name])
        got = _rz_load(rz)   # 控えに書けたら、そこから読む形にそろえる（画素は同じ）
        if got: fr = got[0]
    _tag = {'pipe_shurui': '実際の画面' if name.startswith('real-') else 'イラスト', 'pipe_name': name, 'pipe_fn': 'jinbutsu'}
    if isinstance(fr, _RzFrames): fr.extra.update(_tag)
    else:
        for im in fr: im.info.update(_tag)
    _CLIP[key] = (fr, loop); return _CLIP[key]

# ---------------- 効果（kouka）：紙吹雪・スポットライト・きらきら・はてな・汗・集中線・びっくり ----------------
import random as _rnd
from PIL import ImageDraw as _ID
_KOUKA = {}
def kouka_frames(G, name, x, y, h):
    """全画面（W×H）の透過の絵の並びを返す（[絵], ループするか）。x, y は効果の中心（スポット・きらきら・はてな・汗・びっくり）"""
    W, H = G['W'], G['H']; key = (name, x, y, h)
    if key in _KOUKA: return _KOUKA[key]
    rg = _rnd.Random(7); fr = []; loop = True
    def blank(): return Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if name == 'kamifubuki':   # 上から色紙が舞い落ちる（1.6秒・止まる）
        cols = [(230, 40, 50), (255, 200, 30), (40, 150, 240), (60, 190, 90), (240, 110, 180), (255, 255, 255)]
        P = [(rg.uniform(0, W), rg.uniform(-440, 40), rg.uniform(380, 620), rg.uniform(-60, 60), rg.choice(cols), rg.uniform(0, 6.28), rg.uniform(8, 16)) for _ in range(140)]
        for i in range(48):
            im = blank(); d = _ID.Draw(im); t = i / 30
            for x0, y0, vy, vx, c, ph, sz in P:
                yy = y0 + vy * t; xx = x0 + vx * t + 18 * math.sin(ph + t * 6)
                if -30 < yy < H + 30:
                    w_ = sz * abs(math.cos(ph + t * 9)) + 2; d.rectangle([xx - w_ / 2, yy - sz / 2, xx + w_ / 2, yy + sz / 2], fill=c + (255,))
            fr.append(im)
        loop = False
    elif name == 'spot':       # まわりが暗くなり、上から光が差す（中心 x, y）
        im = Image.new('RGBA', (W, H), (0, 0, 0, 190)); m = Image.new('L', (W, H), 0); d = _ID.Draw(m)
        d.polygon([(x - 120, 0), (x + 120, 0), (x + h * 0.55, y + h * 0.5), (x - h * 0.55, y + h * 0.5)], fill=255)
        d.ellipse([x - h * 0.55, y + h * 0.5 - 60, x + h * 0.55, y + h * 0.5 + 60], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(40)); a_ = ImageChops.subtract(im.getchannel('A'), m); im.putalpha(a_)
        lit = Image.new('RGBA', (W, H), (255, 245, 200, 0)); lit.putalpha(m.point(lambda v: v * 50 // 255)); im.alpha_composite(lit)
        for i in range(20):   # 光がわずかに揺れる
            f = im.copy(); f.putalpha(f.getchannel('A').point(lambda v, k=i: int(v * (0.94 + 0.06 * math.sin(k / 20 * 6.28))))); fr.append(f)
    elif name in ('kira', 'hatena', 'ase', 'bikkuri'):
        F = G['kit'].font(int(h * 0.32), 900, G['GOTH']) if name in ('hatena', 'bikkuri') else None
        pts = [(x + rg.uniform(-h * 0.6, h * 0.6), y + rg.uniform(-h * 0.6, h * 0.2), rg.uniform(0, 6.28)) for _ in range({'kira': 7, 'hatena': 3, 'ase': 3, 'bikkuri': 1}[name])]
        if name == 'bikkuri': pts = [(x + h * 0.35, y - h * 0.45, 0)]
        for i in range(24):
            im = blank(); d = _ID.Draw(im); u = i / 24
            for px, py, ph in pts:
                if name == 'kira':
                    r = (0.4 + 0.6 * abs(math.sin(ph + u * 6.28))) * h * 0.08
                    d.polygon([(px, py - r * 2), (px + r * 0.4, py - r * 0.4), (px + r * 2, py), (px + r * 0.4, py + r * 0.4), (px, py + r * 2), (px - r * 0.4, py + r * 0.4), (px - r * 2, py), (px - r * 0.4, py - r * 0.4)], fill=(255, 225, 70, 255), outline=(255, 255, 255, 255))
                elif name in ('hatena', 'bikkuri'):
                    dy = -10 * abs(math.sin(ph + u * 6.28)); ch_ = '？' if name == 'hatena' else '！'
                    d.text((px, py + dy), ch_, font=F, fill=(40, 40, 50, 255), stroke_width=6, stroke_fill=(255, 255, 255, 255), anchor='mm')
                else:   # 汗：しずくが垂れる
                    yy = py + (u * 60) % 60; d.ellipse([px - 9, yy - 12, px + 9, yy + 12], fill=(110, 190, 255, 230), outline=(255, 255, 255, 255), width=3)
            fr.append(im)
    elif name == 'shuchusen':  # 集中線（まんがの驚き・強調）
        for i in range(6):
            im = blank(); d = _ID.Draw(im); r2 = random_ = _rnd.Random(i)
            for k in range(90):
                a0 = r2.uniform(0, 6.283); w0 = r2.uniform(0.004, 0.012); r_in = r2.uniform(330, 470)
                pts_ = [(x + math.cos(a0) * 2000, y + math.sin(a0) * 2000), (x + math.cos(a0 + w0) * 2000, y + math.sin(a0 + w0) * 2000), (x + math.cos(a0) * r_in, y + math.sin(a0) * r_in)]
                d.polygon(pts_, fill=(20, 20, 20, 200))
            fr.append(im)
    else:
        return None, True
    _KOUKA[key] = (fr, loop); return _KOUKA[key]

# ---------------- 動き続ける部品 ----------------
def make_ugoki_class(G):
    Raw = G['Raw']; paste_safe = G['paste_safe']; with_alpha = G['with_alpha']; ease_in_out = G['ease_in_out']; clamp = G['clamp']
    class Ugoki(Raw):
        """出たあとも動く部品：frames（連番）・idle（揺れ・浮く・脈打つ・回る）・move（場所を移る）・switch（表情の差し替え）・flip"""
        frames = None; loop = True; idle = None; moves = (); switches = (); flip = False
        def cur(self, t):
            fr, loop = self.frames, self.loop
            for ts, f2, l2 in self.switches:
                if t >= ts: fr, loop, base = f2, l2, ts
            if not fr: return self._src
            t0 = self.ts
            for ts, f2, l2 in self.switches:
                if t >= ts: t0 = ts
            st = (getattr(self, 'stops', None) or {}).get(t0)   # 指示書の tomaru（入って／替わってからの秒）でその絵に止める（作業AI 10/20）
            if st is not None and t > st: t = st
            i = int(max(0.0, t - t0) * FPS_CLIP)
            im = fr[i % len(fr)] if loop else fr[min(i, len(fr) - 1)]
            return im.transpose(Image.FLIP_LEFT_RIGHT) if self.flip else im
        def where(self, t):
            x, y = self.x0, self.y0
            for ts, dur, x2, y2 in self.moves:
                if t <= ts: break
                q = ease_in_out(clamp((t - ts) / max(0.05, dur))); x, y = x + (x2 - x) * q, y + (y2 - y) * q
            return x, y
        def draw(self, cv, t):
            if t < self.ts: return
            a_out = 1.0
            if self.te is not None:
                if t >= self.te: return
                if t > self.te - 0.2 and self.out == 'fade': a_out = (self.te - t) / 0.2
            im = self.cur(t); u = t - self.ts
            sw = [ts_ for ts_, f2, l2 in self.switches if ts_ <= t]
            if sw and t - sw[-1] < 0.25:   # 替わった直後は前の絵から溶けて、少しふくらんで収まる（変形）
                q = (t - sw[-1]) / 0.25; old = self.cur(sw[-1] - 0.001); bt = self.anchor[1] == 'b'; s2 = 1 + 0.12 * math.sin(q * math.pi)
                im2 = im.resize((max(1, int(im.width * s2)), max(1, int(im.height * s2))), Image.BILINEAR) if s2 > 1.005 else im
                c2 = Image.new('RGBA', (max(old.width, im2.width), max(old.height, im2.height)), (0, 0, 0, 0))
                for i3, al3 in ((old, 1 - q), (im2, q)): c2.alpha_composite(with_alpha(i3, al3), ((c2.width - i3.width) // 2, c2.height - i3.height if bt else (c2.height - i3.height) // 2))
                im = c2
            if self.idle == 'yure': im = im.rotate(2.2 * math.sin(u * 2 * math.pi * 0.9), resample=Image.BICUBIC, expand=True)
            elif self.idle == 'kaiten': im = im.rotate(-40 * u, resample=Image.BICUBIC, expand=True)
            elif self.idle == 'doki':
                s = 1 + 0.045 * max(0.0, math.sin(u * 2 * math.pi * 1.4)) ** 3
                im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
            elif self.idle == 'iki':   # 1枚絵の人物：息をする（縦にわずかに伸び縮み・足もと固定）
                s = 1 + 0.012 * math.sin(u * 2 * math.pi * 0.55)
                im = im.resize((im.width, max(1, int(im.height * s))), Image.BILINEAR)
            self.x, self.y = self.where(t)
            if self.idle == 'fuwa': self.y += 9 * math.sin(u * 2 * math.pi * 0.6)
            x, y = self.pos(im)
            dur = self.dur or self.default_dur(); p = u / dur if dur > 0 else 1
            if p >= 1: paste_safe(cv, with_alpha(im, a_out), x, y)
            else: self.animate(cv, im, x, y, DE_P0 + (1 - DE_P0) * max(0.0, p), a_out)   # 言葉の頭のコマで部品がもう見えている（ルール5・出方の途中から始める）
    return Ugoki

# ---------------- 流れる地（写真:名前@流す）----------------
def nagasu_ji(name, op):
    """横に長い絵（素材の shashin/<名前>.png・画面より幅が広い）を秒速 v px で左へ流す。<名前>_kage.png（L・値÷127.5＝明るさの倍率）があれば
    画面に止まった陰影として掛ける（柄だけ流れ、中央が明るく外が暗いのは動かない・手本 KTbQ 頭）"""
    import numpy as _np
    _o = op.split(':'); v = float(_o[1]) if len(_o) > 1 else 280.0
    yure = float(_o[2]) if len(_o) > 2 else 0.0   # 揺れ：平均この秒おきに、0.1秒で余分に跳ぶ（手本 KTbQ の柄は 0.6〜1.1秒おきに一瞬速く進む・跳んだコマが大きな切り替わりになる）
    jump = float(_o[3]) if len(_o) > 3 else 40.0
    hikari = float(_o[4]) if len(_o) > 4 else 0.0   # 光：跳ぶたびに柄が 0.4秒かけて明るくなって戻る（手本 KTbQ 2.6〜2.9秒・3.6〜3.9秒 は柄の明るさが上がり、画面の4割が一度に変わる）
    import random as _r; _g = _r.Random(name); tk, _t = [], 0.0
    while yure and _t < 600: _t += yure * _g.uniform(0.7, 1.3); tk.append(_t)
    import bisect as _b
    def _x(t):
        n = _b.bisect_right(tk, t); q = 0.0
        if n and t - tk[n - 1] < 0.1: u = (t - tk[n - 1]) / 0.1; q = u * u * (3 - 2 * u); n -= 1
        return v * t + jump * (n + q)
    import sys as _s; _s.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib')); import paths as _pa; SOZAI = _pa.sozai_dir()
    src = Image.open(os.path.join(SOZAI, 'shashin', name + '.png')).convert('RGB')
    if src.height != 1080: src = src.resize((int(src.width * 1080 / src.height), 1080), Image.LANCZOS)
    a = _np.asarray(src)
    kp = os.path.join(SOZAI, 'shashin', name + '_kage.png')
    kage = (_np.asarray(Image.open(kp).convert('L')).astype(_np.float32) / 127.5)[..., None] if os.path.exists(kp) else None
    span = a.shape[1] - 1920
    def f(t):
        x = int(round(_x(t))) % max(1, 2 * span); x = x if x <= span else 2 * span - x   # 端まで流れたら折り返す（絵の幅が足りないときだけ）
        c = a[:, x:x + 1920]
        m = 1.0
        if hikari:
            n = _b.bisect_right(tk, t)
            if n and t - tk[n - 1] < 0.4: m = 1.0 + hikari * math.sin(math.pi * (t - tk[n - 1]) / 0.4)
        if kage is not None or m != 1.0: c = _np.clip(c.astype(_np.float32) * (kage if kage is not None else 1.0) * m, 0, 255).astype(_np.uint8)
        return Image.fromarray(c).convert('RGBA')
    f.abs_t = True; f.pipe_shurui = '全画面挿絵'; f.pipe_name = name
    return f

# ---------------- カメラのある場面 ----------------
def make_scene_class(G):
    Sc = G['Sc']; W, H = G['W'], G['H']; clamp = G['clamp']; ease_in_out = G['ease_in_out']
    class EdlSc(Sc):
        cam = None; lbl = None
        def raw(self, t):
            k = clamp((t - self.t0) / max(0.1, self.t1 - self.t0))
            if self.bgx is None: cv = Image.new('RGBA', (W, H), (246, 246, 246, 255))
            elif callable(self.bgx): cv = (self.bgx(t) if getattr(self.bgx, 'abs_t', False) else self.bgx(k)).copy()   # 流す地は動画の秒で動く（keep でつないでも途切れない）
            elif isinstance(self.bgx, tuple): cv = Image.new('RGBA', (W, H), self.bgx + (255,))
            else: cv = self.bgx.copy()
            for e in sorted(self.elems, key=lambda e: e.z): e.draw(cv, t)
            c = self.cam
            if c:
                kc = k if c.get('t_from') is None else clamp((t - c['t_from']) / max(0.1, min(c.get('t_dur', 9e9), self.t1 - c['t_from'])))
                kk = c['kind']; q = ease_in_out(kc); s, fx, fy, dx, dy = 1.0, 0.5, 0.5, 0.0, 0.0
                if kk in ('yoru', 'hiku'):
                    a, b = c.get('from', 1.0 if kk == 'yoru' else 1.14), c.get('to', 1.14 if kk == 'yoru' else 1.0); s = a + (b - a) * q
                    fx, fy = c.get('focus', (0.5, 0.5))
                elif kk == 'pan': dx = c.get('dx', -160) * (q - 0.5); s = 1 + abs(c.get('dx', -160)) / W + 0.02
                elif kk == 'tilt': dy = c.get('dy', -90) * (q - 0.5); s = 1 + abs(c.get('dy', -90)) / H + 0.02
                elif kk == 'yureru':
                    u = t - self.t0; dx = 9 * math.sin(u * 1.7) + 4 * math.sin(u * 4.1); dy = 6 * math.sin(u * 1.3 + 1); s = 1.03
                if c.get('shake_t') is not None and 0 <= t - c['shake_t'] < 0.45:
                    v = (1 - (t - c['shake_t']) / 0.45) ** 2; dx += 22 * v * math.sin((t - c['shake_t']) * 70); dy += 14 * v * math.cos((t - c['shake_t']) * 55); s = max(s, 1.04)
                if abs(s - 1) > 0.002 or abs(dx) > 0.5 or abs(dy) > 0.5:
                    cw, ch = W / s, H / s
                    cx = min(max(fx * W - dx, cw / 2), W - cw / 2); cy = min(max(fy * H - dy, ch / 2), H - ch / 2)
                    cv = cv.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx - cw / 2) + int(cw), int(cy - ch / 2) + int(ch))).resize((W, H), Image.BILINEAR)
            bi = getattr(self, 'boke_in', None)
            if bi and 0 <= t - self.t0 < bi:
                q = 1 - (t - self.t0) / bi; s_ = 1 + 0.35 * q
                cw, ch = int(W / s_), int(H / s_); cv = cv.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
                k_ = max(1, int(140 * q)); cv = cv.resize((max(1, W // k_ * 4), H), Image.BILINEAR).resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6 * q))
            if self.lbl is not None: self.lbl.draw(cv, t)
            if getattr(self, 'lbl2', None) is not None: self.lbl2.draw(cv, t)   # 場面の札（カメラが寄っても上に残る）
            return cv
    import ki1 as _k1
    _orig = _k1._sc_render0
    if not getattr(_orig, 'edl', False):
        def _disp(sc, t): return sc.raw(t) if isinstance(sc, EdlSc) else _orig(sc, t)
        _disp.edl = True; _k1._sc_render0 = _disp
    return EdlSc

# ---------------- 言葉から秒へ ----------------
def make_finder(G):
    """言葉 → 声の字の位置と秒。声の字（ref）は書き起こしなので、台本の字と表記が違う（第2／第二・AI／ai）→ 揃えてから探す。
    win（指示書の行の秒）があれば、その秒の範囲の中を、見つからなければ似た並びで探す。それでも無ければ行の頭の秒"""
    import unicodedata, difflib, bisect
    ON = G['ON']; FPS = G['FPS']
    KAN = str.maketrans('〇一二三四五六七八九', '0123456789')
    def nz(x): return unicodedata.normalize('NFKC', ON.N(x or '')).lower().translate(KAN)
    raw = ON.ref; ref = ''.join(nz(c) if len(nz(c)) == 1 else c.lower() for c in raw)   # 1字ずつ揃える（位置を変えない）
    line_of = sorted((v, k) for k, v in ON.L0.items())
    def gyou_at(i):
        n = None
        for v, k in line_of:
            if v <= i: n = k
            else: break
        return n
    def find(kotoba, start, gyou=None, what='', win=None):
        p = nz(kotoba)
        if not p: return None
        if win:
            a = max(0, bisect.bisect_left(ON.T, win[0] - 1.5)); b = min(len(ref), bisect.bisect_right(ON.T, win[1] + 1.5))
            a = max(a, start - 3) if start - 3 < b else a
            for q in (p, p[:6], p[:4]):
                i = ref.find(q, a, b)
                if i >= 0: return _t(i, kotoba, what, q != p)
            sm = difflib.SequenceMatcher(None, ref[a:b], p, autojunk=False); m = sm.find_longest_match(0, b - a, 0, len(p))
            if m.size >= min(3, len(p)):
                return _t(max(a, a + m.a - m.b), kotoba, what, True)
            j = bisect.bisect_left(ON.T, win[0]); LOG['kotoba_zure'].append(kotoba + '（行の頭の秒）')
            return _t(min(j, len(ref) - 1), kotoba, what, False)
        for q in (p, p[:6], p[:4]):
            if gyou is not None and gyou in ON.L0:
                i = ref.find(q, ON.L0[gyou])
                if i >= 0 and i >= start - 2: return _t(i, kotoba, what, q != p)
            i = ref.find(q, start)
            if i >= 0: return _t(i, kotoba, what, q != p)
        return None
    def _t(i, kotoba, what, short):
        t1 = ON.refine(ON.T[i]); fr = int(round(t1 * FPS))
        ON.EV.append({'what': what or kotoba, 'line': gyou_at(i), 'word': kotoba, 'whisper': round(ON.WS[i], 3), 'voice': round(t1, 3), 'how': ON.KIND[i], 'frame': fr})
        if short: LOG['kotoba_zure'].append(kotoba)
        return fr / FPS, i
    find.nz = nz; find.ref = ref; find.T = ON.T
    return find

# ---------------- 読む部分の見張り（絶対ルール：読む部分は被らない・字が見切れない） ----------------
TEXT_KINDS = {'moji3d', 'fuki', 'midashi', 'oaka', 'ao', 'kon', 'obi_aka', 'aka_box', 'tag', 'card_hai', 'card_ao', 'card_kuro', 'check', 'kin_l', 'waku', 'pink'}
def _bb(e, final=True):
    if not getattr(e, 'bb_wh', None) or getattr(e, 'kind_', '') == 'kouka': return None
    w, h = e.bb_wh; x, y = (getattr(e, 'x0', e.x), getattr(e, 'y0', e.y))
    if final and getattr(e, 'moves', ()): x, y = e.moves[-1][2], e.moves[-1][3]
    a = getattr(e, 'anchor', 'cc') or 'cc'
    l = x - w / 2 if a[0] == 'c' else (x - w if a[0] == 'r' else x)
    t = y - h / 2 if a[1] == 'c' else (y - h if a[1] == 'b' else y)
    bi = getattr(e, 'bb_in', None)   # 絵の中の透明でない所（人物の絵は 960x800 の枠の中で細い）
    if bi: return (l + bi[0], t + bi[1], l + bi[2], t + bi[3])
    return (l, t, l + w, t + h)
def _live(a, b, end):
    """2つの部品が同じ時に画面にいるか"""
    ae = a.te if a.te is not None else end; be = b.te if b.te is not None else end
    return min(ae, be) > max(a.ts, b.ts)
def _shift(e, dx, dy):
    e.x += dx; e.y += dy
    if hasattr(e, 'x0'): e.x0 += dx; e.y0 += dy
    if getattr(e, 'moves', ()): e.moves = tuple((ts, du, x2 + dx, y2 + dy) for ts, du, x2, y2 in e.moves)
def _ov(a, b): return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
def _cam_window(cam, W, H):
    """カメラが動く間に画面に映る範囲の共通部分（字が見切れないか見る）。揺れ（shake・yureru）は小さいので余白で見る"""
    if not cam or cam.get('kind', 'none') == 'none': return (0, 0, W, H)
    kk = cam['kind']; ws = []
    for q in (0.0, 0.5, 1.0):
        s, fx, fy, dx, dy = 1.0, 0.5, 0.5, 0.0, 0.0
        if kk in ('yoru', 'hiku'):
            a, b = cam.get('from', 1.0 if kk == 'yoru' else 1.14), cam.get('to', 1.14 if kk == 'yoru' else 1.0); s = a + (b - a) * q; fx, fy = cam.get('focus', (0.5, 0.5))
        elif kk == 'pan': dx = cam.get('dx', -160) * (q - 0.5); s = 1 + abs(cam.get('dx', -160)) / W + 0.02
        elif kk == 'tilt': dy = cam.get('dy', -90) * (q - 0.5); s = 1 + abs(cam.get('dy', -90)) / H + 0.02
        elif kk == 'yureru': s = 1.03
        cw, ch = W / s, H / s
        cx = min(max(fx * W - dx, cw / 2), W - cw / 2); cy = min(max(fy * H - dy, ch / 2), H - ch / 2)
        ws.append((cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))
    return (max(w[0] for w in ws), max(w[1] for w in ws), min(w[2] for w in ws), min(w[3] for w in ws))
def mihari(sc, carried, sid, W, H, LOG):
    L = LOG.setdefault('mihari', {'kesu': [], 'yoseru': [], 'camera_hazusu': []})
    # 空の画面：場面の頭から最初の字・絵が出るまで 0.3秒を超えて何も無い（見出しも絵も無い白板）なら記録して組み立ての最後で止める
    #   （作業AI 10/20：vhm8 7版目 22.73〜23.50秒の0.77秒が空。前の場面から残す部品は頭より前に出ているので数えない）
    _vis = [e.ts for e in sc.elems if getattr(e, 'kind_', '') != 'kouka' and (e.te is None or e.te > sc.t0)]
    _gap = (min(_vis) - sc.t0) if _vis else ((getattr(sc, 't1', None) or sc.t0) - sc.t0)
    if _gap > 0.3: L.setdefault('kara_gamen', []).append({'id': sid, 't0': round(sc.t0, 2), 'kara_byou': round(_gap, 2)})
    new_txt = [e for e in sc.elems if getattr(e, 'kind_', '') != 'kouka' and e not in carried]
    # A：残し足しの場面で、新しく出る部品（字・図・物・人物）に前の場面の部品（人物は除く）が重なるなら、その部品が出るコマで前の部品を消す（s010 の 50万円の残り）
    for nt in new_txt:
        b = _bb(nt)
        if b is None: continue
        if getattr(nt, 'kind_', '') == 'oaka' and any(_ov(b, _bb(ce)) > 0 for ce in carried if _bb(ce) is not None):   # 例外（決めた人：作業AI 10/21・根拠 kata.md 10/20 目視）：赤い大字は前の場面から残った部品にかぶせてよい（手本 KTbQ ほか「赤の大字を前の画面にかぶせる」）→ 前の部品を消さない
            L.setdefault('oaka_kabuse', []).append({'id': sid, 'kimeta': '作業AI 10/21・根拠 kata.md 10/20 目視'}); continue
        area = max(1, (b[2] - b[0]) * (b[3] - b[1]))
        for ce in carried:
            if getattr(ce, 'kind_', '') == 'jinbutsu' or (ce.te is not None and ce.te <= nt.ts): continue
            cb = _bb(ce)
            if cb is not None and _ov(b, cb) > 0.10 * area:
                ce.te = nt.ts; ce.out = 'fade'; L['kesu'].append({'id': sid, 't': round(nt.ts, 2), 'kind': getattr(ce, 'kind_', '?')})
    # B：字が画面（カメラの映る範囲）から見切れるなら内側へ寄せる。寄せても入らない大きさならその場面のカメラを外す
    win = _cam_window(getattr(sc, 'cam', None), W, H); m = 24
    for e in sc.elems:
        if not getattr(e, 'is_text', False) or (e.te is not None and e.te <= sc.t0): continue
        _c = getattr(sc, 'cam', None) or {}
        if _c.get('t_from') is not None and e.te is not None and e.te <= _c['t_from'] + 0.01: continue
        b = _bb(e)
        if b is None: continue
        if b[2] - b[0] > win[2] - win[0] - 2 * m or b[3] - b[1] > win[3] - win[1] - 2 * m:
            if getattr(sc, 'cam', None): sc.cam = None; L['camera_hazusu'].append(sid); win = (0, 0, W, H)
            continue
        dx = (win[0] + m - b[0]) if b[0] < win[0] + m else ((win[2] - m - b[2]) if b[2] > win[2] - m else 0)
        dy = (win[1] + m - b[1]) if b[1] < win[1] + m else ((win[3] - m - b[3]) if b[3] > win[3] - m else 0)
        if dx or dy:
            _shift(e, dx, dy)
            L['yoseru'].append({'id': sid, 'dx': round(dx), 'dy': round(dy)})
    end = getattr(sc, 't1', None) or 1e9
    live = [e for e in sc.elems if getattr(e, 'kind_', '') != 'kouka' and _bb(e) is not None and (e.te is None or e.te > sc.t0)]
    def free(e, b, kinds):
        for o in live:
            if o is e or not _live(e, o, end): continue
            if kinds(o) and _ov((b[0] - 10, b[1] - 10, b[2] + 10, b[3] + 10), _bb(o)) > (0 if getattr(o, 'is_text', False) and getattr(e, 'is_text', False) else 0.05 * max(1, (b[2] - b[0]) * (b[3] - b[1]))): return False
        return win[0] + m <= b[0] and b[2] <= win[2] - m and win[1] + m <= b[1] and b[3] <= min(win[3], 960) - m
    def oki(e, kinds, tag, kiroku=True):
        """e が kinds の部品に重なっていれば、重ならない近い場所（9か所）へ動かす。動かせたら True・どこも無ければ記録して False"""
        b = _bb(e)
        if free(e, b, kinds): return True
        w, h = b[2] - b[0], b[3] - b[1]; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        cands = sorted(POS.values(), key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
        for qx, qy in cands:
            nb = (qx - w / 2, qy - h / 2, qx + w / 2, qy + h / 2)
            if free(e, nb, kinds):
                _shift(e, qx - cx, qy - cy); L.setdefault(tag, []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'dx': round(qx - cx), 'dy': round(qy - cy)}); return True
        if kiroku: L.setdefault(tag + '_nokoru', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?')})
        return False
    # C：同じ時に出ている字どうしが重なるなら、後から出る字を空いた所へ（s043 の赤い帯）
    txt = sorted([e for e in live if getattr(e, 'is_text', False)], key=lambda e: e.ts)
    pad = lambda b, m=12: (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
    for k, e in enumerate(txt):
        if any(_live(e, o, end) and _ov(pad(_bb(e)), _bb(o)) > 0 and not (getattr(e, 'kind_', '') == 'oaka' and o in carried) for o in txt[:k]):   # 赤い大字が前の場面から残った字にかぶるのは例外（作業AI 10/21・根拠 kata.md 10/20 目視）。ほかの字どうしは今までどおり
            hito_ji = lambda x: lambda o: (getattr(o, 'is_text', False) and o is not x) or getattr(o, 'kind_', '') == 'jinbutsu'   # 寄せた先で人物の顔にかぶせない（s043 r3）
            if oki(e, hito_ji(e), 'ji_kasanari', kiroku=False): continue
            # 後の字の行き場が無ければ、重なっている前の字（小さい札など）のほうを空いた所へ
            mae = [o for o in txt[:k] if _live(e, o, end) and _ov(_bb(e), _bb(o)) > 0]
            if not all(oki(o, hito_ji(o), 'ji_kasanari_mae', kiroku=False) for o in mae):
                L.setdefault('ji_kasanari_nokoru', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?')})
    # G：同じ言葉の字が同じ時に2つ出ていれば、後から出るほうを出さない（s046「こうしたら良くなります」が札と吹き出しで2回）
    for k, e in enumerate(txt):
        if not getattr(e, 'text_', '') or len(e.text_) < 3: continue
        for o in txt[:k]:
            if getattr(o, 'text_', '') == e.text_ and _live(e, o, end) and (e.te is None or e.te > e.ts):
                e.te = e.ts; L.setdefault('onaji_ji_kesu', []).append({'id': sid, 'text': e.text_}); break
    # E：上の大きな字（見出し）に絵がかぶるなら、絵を見出しの下へ下げる（足もとは字幕帯の上まで）。下げきれない分は記録（s002・s004・s008・s024・s040）
    UE = ('midashi', 'moji3d', 'oaka', 'ao', 'kon', 'kin_l', 'pink')
    for e in live:
        if getattr(e, 'kind_', '') not in UE or (e.te is not None and e.te <= e.ts): continue
        b = _bb(e)
        if b is None or (b[1] + b[3]) / 2 > 420: continue
        for o in live:
            if o is e or getattr(o, 'is_text', False) or getattr(o, 'kind_', '') in ('kouka',) or not _live(e, o, end): continue
            ob = _bb(o)
            if ob is None or _ov(pad(b, 10), ob) <= 0 or (ob[3] - ob[1]) > 0.9 * H: continue
            need = b[3] + 14 - ob[1]; room = (min(win[3], 952) - 8) - ob[3]
            dy = max(0, min(need, room))
            if dy > 0: _shift(o, 0, dy); L.setdefault('ue_ji_sageru', []).append({'id': sid, 'kind': getattr(o, 'kind_', '?'), 'dy': round(dy)})
            if need > room + 1: L.setdefault('ue_ji_kasanari_nokoru', []).append({'id': sid, 'kind': getattr(o, 'kind_', '?'), 'nokori': round(need - max(0, room))})
    # F：絵が画面の端で切れる・字幕帯（下 952 から）にかかるなら内側へ寄せる（動いて入ってくる部品は動き終わりの場所で見る）
    for e in live:
        if getattr(e, 'is_text', False) or getattr(e, 'kind_', '') in ('kouka',) or (e.te is not None and e.te <= e.ts): continue
        b = _bb(e)
        if b is None or (b[2] - b[0]) > W - 32: continue
        dx = (16 - b[0]) if b[0] < 16 else ((W - 16 - b[2]) if b[2] > W - 16 else 0)
        soko = 952 if getattr(e, 'kind_', '') != 'jinbutsu' else 958
        dy = (soko - b[3]) if b[3] > soko else 0
        if getattr(e, 'shita_kiri', False): dy = (H + 6 - b[3]) if b[3] < H + 6 else 0   # shita_kiri：体の切れ目を画面の下端（1080）より下へ下げる（字幕帯の裏に入ってよい）
        if dy and b[1] + dy < 8: dy = 8 - b[1]   # 上に寄せきれないときは上端まで
        if dx or dy: _shift(e, dx, dy); L.setdefault('hashi_yoseru', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'dx': round(dx), 'dy': round(dy)})
    # 字の見切れ（吹き出し・札も）：B はカメラの範囲で見るが、カメラの無い場面の画面の端も見る
    for e in live:
        if not getattr(e, 'is_text', False) or (e.te is not None and e.te <= e.ts): continue
        b = _bb(e)
        if b is None: continue
        dx = (16 - b[0]) if b[0] < 16 else ((W - 16 - b[2]) if b[2] > W - 16 else 0)
        if dx: _shift(e, dx, 0); L.setdefault('ji_hashi_yoseru', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'dx': round(dx)})
    # H：左上の章の札・右上の場面の札に字・絵がかかるなら、札の下へ下げる（r8 別の目：1:28・1:31・1:34・2:38 の見出しが章の札に重なる）
    #   札はカメラの外（寄っても同じ場所）なので、カメラの範囲ではなく画面の座標で見る。下げると字幕帯（952〜）にかかるときは記録だけ
    fuda = [f for f in (getattr(sc, 'lbl', None), getattr(sc, 'lbl2', None)) if f is not None]
    for fe in fuda:
        _fi = getattr(fe, '_src', None)
        fb = (fe.x, fe.y, fe.x + _fi.width, fe.y + _fi.height) if _fi is not None else None
        if fb is None:
            continue
        # カメラが寄ると絵は画面の上・外へ広がる（札は動かない）→ カメラの映る範囲 win を画面いっぱいに広げた座標で比べる
        sx, sy = W / max(1, win[2] - win[0]), H / max(1, win[3] - win[1])
        for e in live:
            if getattr(e, 'kind_', '') in ('kouka',) or (e.te is not None and e.te <= e.ts): continue
            b0 = _bb(e)
            if b0 is None: continue
            b = ((b0[0] - win[0]) * sx, (b0[1] - win[1]) * sy, (b0[2] - win[0]) * sx, (b0[3] - win[1]) * sy)
            if _ov((fb[0] - 12, fb[1], fb[2] + 12, fb[3] + 14), b) <= 0: continue
            dy = (fb[3] + 14 - b[1]) / sy; b = b0
            if b[3] + dy > 952: L.setdefault('fuda_kasanari_nokoru', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'nokori': round(b[3] + dy - 952)}); continue
            _shift(e, 0, dy); L.setdefault('fuda_shita', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'dy': round(dy)})
    # D：立体アイコンは主役にしない＝人物と字に重ねない（重なれば空いた所へ）
    for e in live:
        if getattr(e, 'kind_', '') == 'icon3d':
            oki(e, lambda o: getattr(o, 'kind_', '') == 'jinbutsu' or getattr(o, 'is_text', False) or (getattr(o, 'kind_', '') == 'icon3d' and o.ts <= e.ts and o is not e), 'icon3d_yoke')
    # J：部品と字の重なりの見張り（直しはしない・記録して組み立ての最後で止める・作業AI 10/20）。上の A〜H で動かしたあとの最終の場所で、
    #   同じ時に出ている字（見出しの帯・札を含む）と、字でない部品（人物・効果は除く）の見える部分の箱が、小さいほうの3%を超えて重なれば記録
    #   （vhm8 7版目 s008 の旗が見出し「目的」の帯の下に隠れた。icon3d_yoke_nokoru は「動かせる空きが無い」も含むので重なりの実測にしない）
    for e in live:
        if getattr(e, 'is_text', False) or getattr(e, 'kind_', '') in ('kouka', 'jinbutsu') or getattr(e, 'fn_na', None) == 'maru' or (e.te is not None and e.te <= e.ts): continue
        b = _bb(e)
        if b is None or (b[2] - b[0]) * (b[3] - b[1]) > 0.6 * W * H: continue
        for o in live:
            if not getattr(o, 'is_text', False) or not _live(e, o, end) or (o.te is not None and o.te <= o.ts): continue
            ob = _bb(o); ov = _ov(b, ob)
            if ov <= 0: continue
            # 手本どおりの重なりは止めない：絵（アイコン）の上に小さな札・帯・箱を貼る形（手本13本のカット表で「アイコンの上に赤い札／青い帯」など・kazoe-ji-e-ue-1020.txt）
            if getattr(o, 'kind_', '') in ('tag', 'obi_aka', 'aka_box', 'card_hai', 'card_ao', 'card_kuro', 'check') and (ob[2] - ob[0]) * (ob[3] - ob[1]) < (b[2] - b[0]) * (b[3] - b[1]): continue
            r_ = ov / max(1, min((b[2] - b[0]) * (b[3] - b[1]), (ob[2] - ob[0]) * (ob[3] - ob[1])))
            if r_ > 0.03: L.setdefault('buhin_ji_kasanari', []).append({'id': sid, 'buhin': getattr(e, 'kind_', '?'), 'ji': getattr(o, 'text_', '')[:12], 'wariai': round(r_, 2)})
    # K：すべての重なり（作業AI 11/03・依頼主 11:51「図がぐちゃぐちゃで被っている」）。同じ時に出ている図・字・人物・画像の箱どうしを全部の組で比べ、
    #   小さいほうの3%を超えて重なれば記録（効果・画面の6割を超える地は除く）。指示書に "kasanari0": true があれば組み立ての最後で止める
    _kz = [e for e in live if getattr(e, 'kind_', '') != 'kouka' and getattr(e, 'fn_na', None) != 'maru' and not (e.te is not None and e.te <= e.ts)]
    for i_, e in enumerate(_kz):
        b = _bb(e)
        if b is not None: L.setdefault('hako', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'ji': getattr(e, 'text_', '')[:20], 'name': getattr(e, 'name_', None), 'box': [round(v) for v in b], 'ts': round(e.ts, 2)})
        if b is None or (b[2] - b[0]) * (b[3] - b[1]) > 0.6 * W * H: continue
        for o in _kz[i_ + 1:]:
            if not _live(e, o, end): continue
            ob = _bb(o)
            if ob is None or (ob[2] - ob[0]) * (ob[3] - ob[1]) > 0.6 * W * H: continue
            ov = _ov(b, ob)
            if ov <= 0: continue
            r_ = ov / max(1, min((b[2] - b[0]) * (b[3] - b[1]), (ob[2] - ob[0]) * (ob[3] - ob[1])))
            if r_ > 0.03: L.setdefault('kasanari_zenbu', []).append({'id': sid, 'a': getattr(e, 'kind_', '?'), 'b': getattr(o, 'kind_', '?'), 'a_ji': getattr(e, 'text_', '')[:12], 'b_ji': getattr(o, 'text_', '')[:12], 'wariai': round(r_, 2)})
    # I：外枠の見張り（直しはしない・記録して組み立ての最後で止める）。字・大字・札の外枠が画面の内側に収まっているか
    #   字はカメラの映る範囲 win を画面いっぱいに広げた座標で見る（寄ると外へ広がる）。札はカメラの外なので画面の座標のまま
    #   r12 の 3472（2行にすべき大字が1行で画面の幅を超えた）・3784（「大」で幅を超えた）を次から止める
    win2 = _cam_window(getattr(sc, 'cam', None), W, H); sx2, sy2 = W / max(1, win2[2] - win2[0]), H / max(1, win2[3] - win2[1])
    def _soto(b): return max(0, -b[0], b[2] - W, -b[1], b[3] - H)
    for e in live:
        if not getattr(e, 'is_text', False) or (e.te is not None and e.te <= e.ts): continue
        b0 = _bb(e)
        if b0 is None: continue
        b = ((b0[0] - win2[0]) * sx2, (b0[1] - win2[1]) * sy2, (b0[2] - win2[0]) * sx2, (b0[3] - win2[1]) * sy2)
        if _soto(b) > 2: L.setdefault('gaiwaku_hamidashi', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'text': getattr(e, 'text_', '')[:20], 'waku': [round(v) for v in b], 'haba': round(b[2] - b[0]), 'soto_px': round(_soto(b))}); continue
        # 出る途中に大きくなる出方（zoom は 1.7倍から縮んで止まる・anim.Elem.animate）は、出始めの大きさで見る（r13 3784：収まった後は入るが出始め3コマが両端で切れた）
        k_ = DEGUCHI_BAI.get(getattr(e, 'anim', None), 1.0)
        if k_ > 1.0:   # 出始めの倍率を、画面に収まる所まで下げる（収まった後の字の大きさは変えない・team-lead 10/20：1時間尺でも出ないように）
            cx, cy, hw0, hh0 = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(1.0, (b[2] - b[0]) / 2), max(1.0, (b[3] - b[1]) / 2)
            fit = min(cx / hw0, (W - cx) / hw0, cy / hh0, (H - cy) / hh0)
            if fit < k_:
                s0 = max(1.0, fit); e.zoom_s0 = s0
                L.setdefault('zoom_dashi_chiisaku', []).append({'id': sid, 'text': getattr(e, 'text_', '')[:20], 'bai': [k_, round(s0, 3)]}); k_ = s0
        if k_ > 1.0:
            cx, cy, hw, hh = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) * k_ / 2, (b[3] - b[1]) * k_ / 2
            bz = (cx - hw, cy - hh, cx + hw, cy + hh)
            if _soto(bz) > 2: L.setdefault('gaiwaku_hamidashi', []).append({'id': sid, 'kind': getattr(e, 'kind_', '?'), 'text': getattr(e, 'text_', '')[:20], 'deguchi': getattr(e, 'anim', None), 'bai': k_, 'waku': [round(v) for v in bz], 'soto_px': round(_soto(bz))})
    # J：大字が人物・写真（画面のスクショ）の上に重なっていないか（直しはしない・記録して組み立ての最後で止める）
    #   大字の枠の中で、人物・写真の絵の色のある画素が占める割合で見る（枠どうしの重なりでは人物の細い絵の余白まで数えてしまう）
    #   r14：s030「ファイルを開く」が A の頭と荷物の山に、s034「セミナーでも伝えた」が画面写真にかぶっていた（作業AI 10/20）
    def _waku(o):
        im = getattr(o, '_src', None)
        if im is None: return None, None
        w, h = im.size; x, y = (getattr(o, 'x0', o.x), getattr(o, 'y0', o.y))
        if getattr(o, 'moves', ()): x, y = o.moves[-1][2], o.moves[-1][3]
        a_ = getattr(o, 'anchor', 'cc') or 'cc'
        l = x - w / 2 if a_[0] == 'c' else (x - w if a_[0] == 'r' else x); t = y - h / 2 if a_[1] == 'c' else (y - h if a_[1] == 'b' else y)
        return im, (int(l), int(t))
    for e in live:
        if getattr(e, 'kind_', '') != 'moji3d' or (e.te is not None and e.te <= e.ts): continue
        b = _bb(e)
        if b is None: continue
        area = max(1, (b[2] - b[0]) * (b[3] - b[1]))
        for o in live:
            if o is e or getattr(o, 'kind_', '') not in ('jinbutsu', 'gamen') or not _live(e, o, end): continue
            im, lt = _waku(o)
            if im is None or im.mode != 'RGBA': continue
            x0, y0, x1, y1 = max(int(b[0]), lt[0]), max(int(b[1]), lt[1]), min(int(b[2]), lt[0] + im.width), min(int(b[3]), lt[1] + im.height)
            if x1 <= x0 or y1 <= y0: continue
            al = im.getchannel('A').crop((x0 - lt[0], y0 - lt[1], x1 - lt[0], y1 - lt[1])).point(lambda v: 255 if v > 128 else 0)
            r_ = (sum(al.histogram()[255:]) ) / area
            if r_ > 0.08: L.setdefault('ji_hito_kasanari', []).append({'id': sid, 'text': getattr(e, 'text_', '')[:20], 'aite': getattr(o, 'kind_', '?') + ':' + str(getattr(o, 'clip_name', '') or ''), 'wariai': round(r_, 2), 'ji_waku': [round(v) for v in b], 'aite_waku': [lt[0], lt[1], lt[0] + im.width, lt[1] + im.height]})
    for fe in (getattr(sc, 'lbl', None), getattr(sc, 'lbl2', None)):
        _fi = getattr(fe, '_src', None) if fe is not None else None
        if _fi is None: continue
        b = (fe.x, fe.y, fe.x + _fi.width, fe.y + _fi.height)
        if _soto(b) > 2: L.setdefault('gaiwaku_hamidashi', []).append({'id': sid, 'kind': 'fuda', 'waku': [round(v) for v in b], 'soto_px': round(_soto(b))})

DEGUCHI_BAI = {'zoom': 1.7}   # 出方の出始めの倍率（anim.Elem.animate：zoom は s = 1.0 + 0.7 * (1 - ease_out(p))。pop・bounce は 1 を少し超えるだけ）

def okikae(s, mae=None):
    """指示書の絵（imi の ／ の後ろ）に書いた物・人物が parts に無い＝別の物（立体アイコンなど）で置き換えている → その物の名前を返す
    kirikae が keep の場面は、前の場面から画面に残る部品（mae＝keep でつながる前の場面の parts）も数える"""
    e = (s.get('imi') or '').split(' ／ ')[-1]
    names = []
    for p in s.get('parts', []) + list(mae or []):
        for k in ('name', 'clip', 'fn'):
            if p.get(k): names.append(str(p[k]))
        if p.get('kind') in ('fuki',): names.append('fuki')
        if isinstance(p.get('to'), dict) and p['to'].get('name'): names.append(str(p['to']['name']))
    names = [n for n in names if n != 'chara_icon1024']   # 静止の M アイコンは M の芝居ではない
    if any(n.startswith('shibai_') for n in names): return []   # 場面まるごとの芝居の部品（yt-jinbutsu の shibai_*）は指示書の絵そのもの
    out = []
    for w, pats in OKIKAE:
        if w in e and not any(pt in n for n in names for pt in pats): out.append(w)
    for rx, pre, lbl in OKIKAE_HITO:
        if re.search(rx, e) and not any(n.startswith(pre) or (pre == 'chat_' and 'dankai_waku' in n) for n in names): out.append(lbl)   # 段の枠（zu_dankai_waku）の中に C が描いてある
    return out

# ---------------- 組む ----------------
def kumitate(G, path):
    E = json.load(open(os.path.expanduser(path)))
    THEME_KURAI = None
    THEME_BG = None   # 指示書に "theme" があれば、明るい地はテーマの地の色1つにそろえる（パステルを回さない・手本の編集者さんの白板の型5／12本・10/20）
    if E.get('theme') and os.environ.get('THEME') and os.path.exists(os.environ['THEME']):
        _tb = json.load(open(os.environ['THEME'])).get('bg')
        if _tb: THEME_BG = '#%02x%02x%02x' % tuple(_tb[:3])
        _jm = json.load(open(os.environ['THEME'])).get('jimon')   # 地の人物の線画を薄く透かす（型23・8本）：{"image","alpha","h","pos"}
        if _jm and 'chara' in os.path.basename(_jm.get('image', '')): raise SystemExit('🔴 テーマの地紋が使ってはいけないキャラ（自社キャラの線画）：%s（依頼主 10/20 23:45）' % _jm['image'])
        if THEME_BG and _jm and os.path.exists(os.path.expanduser(_jm['image'])):
            W, H = G['W'], G['H']; _bgi = muji(W, H, THEME_BG).copy(); _im = Image.open(os.path.expanduser(_jm['image'])).convert('RGBA')
            _h = int(_jm.get('h', 760)); _im = _im.resize((max(1, int(_im.width * _h / _im.height)), _h), Image.LANCZOS)
            _a = _im.getchannel('A').point(lambda v: int(v * float(_jm.get('alpha', 0.12)))); _im.putalpha(_a)
            _px, _py = _jm.get('pos', [W // 2, H // 2 + 40]); _bgi.alpha_composite(_im, (int(_px - _im.width / 2), int(_py - _im.height / 2)))
            _MUJI[THEME_BG + '+jimon'] = _bgi; THEME_BG = THEME_BG + '+jimon'
        _kt = json.load(open(os.environ['THEME'])).get('kurai_tsubu')   # {"n":粒の数,"seed":種}：暗い地に光の粒を置く
        # 暗い地の色はテーマの "kurai_iro": [r,g,b]（無ければ今までの (12,12,16)・ほかの本は変わらない）。手本13本の暗い地は外周の明るさ 12〜59・中央33（darkbg/kurai-171.json・10/20）
        if _kt:
            import random as _r2
            W, H = G['W'], G['H']; _rg = _r2.Random(int(_kt.get('seed', 7))); _ki = json.load(open(os.environ['THEME'])).get('kurai_iro') or [12, 12, 16]; _k = Image.new('RGBA', (W, H), tuple(int(v) for v in _ki[:3]) + (255,)); _d = __import__('PIL.ImageDraw', fromlist=['x']).Draw(_k)
            for _ in range(int(_kt.get('n', 260))):
                _x, _y, _rr = _rg.randint(0, W), _rg.randint(0, H), _rg.choice([1, 1, 1, 2, 2, 3]); _c = _rg.randint(150, 255)
                _d.ellipse((_x - _rr, _y - _rr, _x + _rr, _y + _rr), fill=(_c, _c, _c, 255))
            _gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); __import__('PIL.ImageDraw', fromlist=['x']).Draw(_gl).ellipse((W * 0.2, H * 0.15, W * 0.8, H * 0.85), fill=(90, 90, 100, 90))
            _k.alpha_composite(_gl.filter(ImageFilter.GaussianBlur(160))); _MUJI['kurai+tsubu'] = _k; THEME_KURAI = 'kurai+tsubu'
    Ugoki = make_ugoki_class(G); EdlSc = make_scene_class(G); find = make_finder(G)
    T = G['T']; W, H = G['W'], G['H']; TR_KINDS = G['TR_KINDS']; TRLOG = G['TRLOG']; sfx = G['sfx']; add = G['add']
    shou = {str(c.get('ch')): c for c in E.get('shou', [])}
    shots = E['shots']
    # 字の中に「\\n」が文字のまま入っていたら止める（y8zh 10/20：画面に「\\n」と出た・指示書の二重エスケープ）
    _kg = [(s.get('id'), q.get('kind')) for s in shots for q in s.get('parts', []) for v in (q.get('text'), *[a_ for a_ in q.get('args', []) if isinstance(a_, str)]) if isinstance(v, str) and '\\n' in v]
    if _kg: raise SystemExit('🔴 EDL：字の中に「\\n」が文字のまま入っている %d件：%s（改行は本物の改行で書く）' % (len(_kg), _kg[:8]))
    # 道具が読まない欄名が指示書にあったら組む前に止める（作業AI 10/20：vhm8 7版目は立体アイコンの大きさを 'h' で書き、道具は 'size' しか読まず黙って「中」で組んで旗が見出しに隠れた）
    #   読む欄名は組み立ての中の p.get / s.get から拾った一覧。説明だけの欄（wadai・kata・memo）は通す。試しで通すときだけ PIPE_EDL_RANMEI_OK=1
    _PK = {'args', 'at', 'av', 'clip', 'dur', 'flip', 'fn', 'hyoujou', 'idle', 'in', 'iro', 'kara', 'kara_dur', 'kind', 'kwargs', 'mono', 'move', 'na', 'name', 'out_at', 'pos', 'px', 'shita_kiri', 'shurui', 'size', 'text', 'to', 'tomaru', 'w', 'z', 'memo', 'kotei'}
    _SK = {'camera', 'ch', 'fuda_ue', 'gamen_yoranai', 'gyou', 'id', 'imi', 'ji', 'jikan', 'kirikae', 'kotoba', 'parts', 'riyuu', 'se', 'wakaru', 'wadai', 'kata', 'memo', 'atama_boke'}
    _MK = {'at', 'dur', 'to'}; _SEK = {'at', 'kind'}; _TK = {'bgm', 'shots', 'shou', 'theme', 'koe', 'memo', 'kasanari0'}
    _rm = [('指示書', k) for k in E if k not in _TK]
    for s_ in shots:
        _rm += [(s_.get('id'), k) for k in s_ if k not in _SK]
        _rm += [(s_.get('id'), 'se.' + k) for x_ in s_.get('se', []) for k in x_ if k not in _SEK]
        for q in s_.get('parts', []):
            _rm += [(s_.get('id'), '%s.%s' % (q.get('kind'), k)) for k in q if k not in _PK]
            if isinstance(q.get('to'), dict): _rm += [(s_.get('id'), '%s.to.%s' % (q.get('kind'), k)) for k in q['to'] if k not in _PK]
            for m_ in (q.get('move') if isinstance(q.get('move'), list) else ([q['move']] if q.get('move') else [])):
                _rm += [(s_.get('id'), '%s.move.%s' % (q.get('kind'), k)) for k in m_ if k not in _MK]
    if _rm:
        msg = '🔴 EDL：道具が読まない欄名が %d件（黙って捨てられ既定の値で組まれる）：%s' % (len(_rm), _rm[:12])
        if os.environ.get('PIPE_EDL_RANMEI_OK') != '1': raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    # 0回目：置き換えの見張り（指示書の物・人物が parts に無い場面は組まずに止める。試しで通すときだけ PIPE_EDL_OKIKAE_OK=1）
    _mae = []; _ok = []
    for s in shots:
        _mae = (_mae if s.get('kirikae') == 'keep' else [])   # keep でつながる間は前の場面の部品が画面に残る
        o = okikae(s, _mae)
        if o: _ok.append({'id': s.get('id'), 'tarinai': o})
        _mae = _mae + list(s.get('parts', []))
    LOG['okikae'] = _ok
    if LOG['okikae']:
        msg = '🔴 EDL：指示書の絵の部品が parts に無い（置き換え）%d場面：%s' % (len(LOG['okikae']), json.dumps(LOG['okikae'][:12], ensure_ascii=False))
        if os.environ.get('PIPE_EDL_OKIKAE_OK') != '1':
            json.dump(LOG, open(os.path.join(G['PROJ'], 'work', 'edl_kumi.json'), 'w'), ensure_ascii=False, indent=1)   # 止めるときだけ書く（書き出しの各部品が組み直すたびに記録を上書きしない）
            raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    # 1回目：場面の頭の秒
    cur = 0; heads = []
    for s in shots:
        r = find(s.get('kotoba'), cur, s.get('gyou'), s.get('id', ''), s.get('jikan'))
        if r is None:
            LOG['mitsukaranai'].append({'id': s.get('id'), 'kotoba': s.get('kotoba')}); heads.append(None); continue
        heads.append(r); cur = r[1] + 1
    # 場面の頭の言葉が、次の場面の頭までにもう一度出てくるなら止める（どちらで替えるか決まらない＝先に出た方で替わる）
    #   作業AI 10/20：vhm8 8版目 s007「裏技」が 22.76秒の「で裏技っていう」ではなく 19.58秒の「裏技シリーズ」で替わり、前の場面が2.6秒短くなった
    _am = []
    for k_, s_ in enumerate(shots):
        if heads[k_] is None or s_.get('jikan'): continue
        q_ = find.nz(s_.get('kotoba')); i_ = heads[k_][1]
        nx_ = next((heads[j_][1] for j_ in range(k_ + 1, len(shots)) if heads[j_] is not None), len(find.ref))
        j2 = find.ref.find(q_, i_ + 1, nx_) if q_ else -1
        if j2 >= 0: _am.append({'id': s_.get('id'), 'kotoba': s_.get('kotoba'), 'tsukatta': round(find.T[i_], 2), 'mou_ichido': round(find.T[j2], 2)})
    if _am:
        msg = '🔴 EDL：場面の頭の言葉が次の場面までに2回出る %d件（先に出た方で替わる・頭の言葉を長くして1つに決める）：%s' % (len(_am), json.dumps(_am, ensure_ascii=False))
        if os.environ.get('PIPE_EDL_ATAMA_OK') != '1': raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    if LOG['mitsukaranai']:
        raise SystemExit('🔴 EDL の言葉が声の字に見つからない %d件：%s' % (len(LOG['mitsukaranai']), json.dumps(LOG['mitsukaranai'][:12], ensure_ascii=False)))
    # 最初の場面は0秒から始める（言葉の頭が0.1〜0.2秒あとだと、その間テーマの明るい地が出て「地が替わる」が1回多く測られた・dEw0/y8zh 10/20）
    if heads and heads[0] is not None and 0 < heads[0][0] < 2.0:
        LOG['atama0'] = round(heads[0][0], 3); heads[0] = (0.0,) + tuple(heads[0][1:])
    prev_sc = None; prev_ch = None; lbl_img = None; kokuchi = None; prev_ci = None
    _an = G.get('_anim')   # zoom の出始めの倍率を部品ごとに持てるようにする（zoom_s0 が無い部品は元の 1.7 のまま）
    if _an is not None and not getattr(_an.Elem, '_zoom_s0_ok', False):
        _orig_animate = _an.Elem.animate
        def _animate_s0(self, cv, im, x, y, p, a_out, _o=_orig_animate, _a=_an):
            s0 = getattr(self, 'zoom_s0', None)
            if self.anim != 'zoom' or s0 is None: return _o(self, cv, im, x, y, p, a_out)
            s = 1.0 + (s0 - 1.0) * (1 - _a.ease_out(p)); al = _a.ease_out(p)
            if abs(s - 1) < 0.01: _a.paste_safe(cv, _a.with_alpha(im, al * a_out), x, y); return
            sw, sh = max(1, int(im.width * s)), max(1, int(im.height * s))
            _a.paste_safe(cv, _a.with_alpha(im.resize((sw, sh), Image.BILINEAR), al * a_out), x + (im.width - sw) // 2, y + (im.height - sh) // 2)
        _an.Elem.animate = _animate_s0; _an.Elem._zoom_s0_ok = True
    def _bg_kurai(im):   # 地が暗いか（縮めた灰色の平均が 90 未満）
        import numpy as _np
        if not hasattr(im, 'convert'): return False
        return float(_np.asarray(im.convert('L').resize((32, 18))).mean()) < 90
    for k, s in enumerate(shots):
        t0, i0 = heads[k]; i1 = heads[k + 1][1] if k + 1 < len(shots) else len(G['ON'].ref)
        ch = str(s.get('ch', '')); G['CH'] = ch
        if ch != prev_ch:
            c = shou.get(ch, {})
            lbl_img = G['label_aka'](c['fuda']) if c.get('fuda') else None
            if c.get('kokuchi') and kokuchi is None: kokuchi = t0
            prev_ch = ch
        def at(kw, what):
            if isinstance(kw, (int, float)) and not isinstance(kw, bool): return t0 + float(kw)   # 数なら場面の頭からの秒（群れが順に去る・0.3秒おき など）
            if not kw: return t0
            r = find(kw, i0, None, what, (t0, max(t0 + 0.5, (heads[k + 1][0] if k + 1 < len(shots) else t0 + 30))) if s.get('jikan') else None)
            if r is None or r[1] > i1 + 40:
                LOG['mitsukaranai'].append({'id': s.get('id'), 'kotoba': kw}); return t0
            return max(t0, r[0])
        # 地
        ji = s.get('ji') or '明るい'
        if ji.startswith('写真:'):   # 「写真:名前@止める」で寄らない写真の地（手本 Nzjn@2.1 の地は止まっている・寄ると動きの量が手本の最大を超えた 10/20 projk）
            _nm, _, _op = ji[3:].partition('@'); jikind = '写真の地'
            if _op.startswith('流す'): bg = nagasu_ji(_nm, _op)   # 「写真:名前@流す[:秒速px]」で横に流れる地（KTbQ 頭0〜8秒の再生柄は 1920幅で約280px/秒 横に流れ続ける・10/21 実測）
            else:
                # 明るい写真は地として暗くする（zen6：明るい札束の写真に金の字で明るさの差2.9・依頼主 10/22 20:33「視認性」）。平均の明るさを95前後へ（暗い写真はそのまま）
                import sys as _s2; _s2.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib')); import paths as _pa2
                from PIL import ImageStat as _IS
                _mean = _IS.Stat(Image.open(os.path.join(_pa2.sozai_dir(), 'shashin', _nm + '.png')).convert('L')).mean[0]
                _dim = round(max(0.0, min(0.5, 1 - 95 / _mean)), 2) if _mean > 0 else 0.0
                bg = G['photo'](_nm, zoom=(1.0, 1.0), dim=_dim) if _op == '止める' else G['photo'](_nm, dim=_dim)
                LOG.setdefault('shashin_dim', []).append({'id': s.get('id'), 'name': _nm, 'mean': round(_mean), 'dim': _dim})
        elif ji == '明るい' and THEME_BG: bg = muji(W, H, THEME_BG); jikind = '明るい地'
        elif ji == '明るい':   # 色は場面のIDで決める（番号で回すと、場面を1つ足しただけで後ろが全部変わる・team-lead 10/20）。前の場面と同じ色なら1つずらす
            ci = int(hashlib.md5(str(s.get('id', k)).encode()).hexdigest(), 16) % len(JI_MUJI)
            if ci == prev_ci: ci = (ci + 1) % len(JI_MUJI)
            bg = muji(W, H, JI_MUJI[ci]); jikind = '明るい地'; prev_ci = ci
        elif ji == '暗い' and THEME_KURAI: bg = _MUJI[THEME_KURAI]; jikind = '暗い地'   # テーマの暗い地（光の粒・中央が少し明るい・手本の編集者さんの頭の型）
        elif ji == '暗い': bg = muji(W, H, JI_KURAI); jikind = '暗い地'
        else: bg = G[JI_NAME.get(ji, 'LIGHT')]; jikind = {'暗い': '暗い地', 'スポット': 'スポットの地'}.get(ji, '色の地（赤・黄・青）' if ji in ('赤', '黄', '青') else '明るい地')
        kr = s.get('kirikae') or 'cut'
        elems = []
        if kr == 'keep' and prev_sc is not None:
            for e in prev_sc.elems:
                # 前の場面の中で消えた部品（見張りAで消した字など・te が場面の頭より前）は持ち越さない
                # （r13 0:15.47：s003 の「9割以上が見て終わり」が s003b で消えたのに、s004 の残し足しで te が戻って「見」だけ見えた）
                if e.te is not None and e.te < t0 - 0.01: LOG.setdefault('keep_kieta', []).append({'id': s.get('id'), 'kind': getattr(e, 'kind_', '?'), 'te': round(e.te, 2)}); continue
                e2 = copy.copy(e); e2.te = None; elems.append(e2)
            bg = prev_sc.bgx
        carried = list(elems)
        sc = EdlSc(t0, 0, elems, bg=bg, ring=False, trans=0.0, zoom=None)
        if kr in TR_KINDS: sc.trk = kr
        if s.get('atama_boke'): sc.boke_in = float(s['atama_boke']); LOG['atama_boke'] = s.get('id')   # 頭の入り：場面の頭を横にぶれた大きな絵から この秒で絞って入る（手本 KTbQ 0〜0.2秒・最初のコマが場面替わりになる）
        cam = s.get('camera') or {}
        if cam and cam.get('kind', 'none') != 'none':
            cam = dict(cam)
            if cam.get('kind') == 'shake': cam['shake_t'] = at(cam.get('at'), 'カメラの揺れ'); cam['kind'] = 'none'
            elif cam.get('shake_at'): cam['shake_t'] = at(cam['shake_at'], 'カメラの揺れ')
            sc.cam = cam; LOG['camera'] += 1
        if lbl_img is not None:
            le = G['Raw'](t0, lbl_img, x=0, y=0, anchor='lt', anim='none'); le.z = 5; sc.lbl = le
        if s.get('fuda_ue'):   # 場面の札（右上・カメラの外＝寄っても読める）。画面のスクショの場面で「何の画面か」を一言（作業AI 10/19 22:4x s034）
            fi = G['label_aka'](s['fuda_ue'])
            l2 = G['Raw'](t0, fi, x=W - fi.width - 24, y=18, anchor='lt', anim='none')   # 右上（左上の章の札と重ねない・r7 で真ん中だと章の札の字を切った）
            l2.z = 5; sc.lbl2 = l2
            LOG.setdefault('fuda_ue', []).append({'id': s.get('id'), 'text': s['fuda_ue']})
        # 部品
        named = {}
        if kr == 'keep' and prev_sc is not None:
            for e in sc.elems:
                if getattr(e, 'jin_name', None): named[e.jin_name] = e
        def build(p, x, y, h, a):
            """部品の絵を作る → (絵, 連番, ループ, 基準, x, y, 出方)。作れなければ None（buhin_nashi に残す）"""
            kind = p.get('kind'); frames = None; loop = True; anchor = 'cc'; img = None
            if kind == 'jinbutsu':
                frames, loop = clip_frames(G, p['name'], int(h))
                if frames is None: LOG['buhin_nashi'].append({'id': s.get('id'), 'jinbutsu': p['name']}); return None
                img = frames[0]; anchor = 'cb'; y = min(950, y + int(h) // 2)
            elif kind == 'moji3d': img = moji3d(G, p['text'], ('金明' if ji in ('暗い', 'スポット') else ('金' if ji.startswith('写真:') else '金濃')) if p.get('iro') == '金' else p.get('iro', '青'), int(p.get('px') or {'小': 96, '中': 130, '大': 170, '特大': 220}.get(p.get('size', '大'), 170)))
            elif kind == 'icon3d':   # 色のついた立体のアイコン（黒い単色は見づらい・作業AI 10/19 19:5x）
                img = icon3d(G, p['name'], p.get('iro', '青'), int(h))
                if img is None: LOG['buhin_nashi'].append({'id': s.get('id'), 'icon3d': p['name']}); return None
                img = kiritoru(img)
                if img.width > W * ICON3D_MAX_W:
                    inf = dict(img.info); k_ = W * ICON3D_MAX_W / img.width; img = img.resize((int(img.width * k_), int(img.height * k_)), Image.LANCZOS); img.info.update(inf)
                    LOG.setdefault('icon3d_chiisaku', []).append(s.get('id'))
            elif kind == 'mono':
                fr, lp = clip_frames(G, p['name'], int(h))
                if fr is not None: frames, loop, img = (fr if len(fr) > 1 else None), lp, fr[0]
                else:
                    try: img = G['ic'](p['name'], int(h))
                    except Exception: LOG['buhin_nashi'].append({'id': s.get('id'), 'mono': p['name']}); return None
                    img = kiritoru(img); inf = dict(img.info); img = img.resize((max(1, int(img.width * int(h) / img.height)), int(h)), Image.LANCZOS); img.info.update(inf)
            elif kind == 'kouka':
                fr, lp = kouka_frames(G, p['name'], x, y, int(h))
                if fr is None: LOG['buhin_nashi'].append({'id': s.get('id'), 'kouka': p['name']}); return None
                frames, loop, img = fr, lp, fr[0]; x, y, anchor = 0, 0, 'lt'
                if a == 'pop': a = 'fade'
            elif kind == 'gamen': img = G['gamen'](p['name'], w=(int(p['w']) if p.get('w') and p.get('pos') is not None else max(int(p.get('w') or 0), int(W * GAMEN_MIN_W))))   # 画面のスクショは画面の幅の7割以上（指示書に場所と大きさの両方がある場面だけその値・作業AI 10/20 s034）
            elif kind in ('fuki', 'midashi', 'oaka', 'ao', 'kon', 'obi_aka', 'aka_box', 'tag', 'card_hai', 'card_ao', 'card_kuro', 'check', 'kin_l', 'waku', 'pink'):
                kw_ = {'av': bool(p['av'])} if kind == 'fuki' and 'av' in p else ({'av': False} if kind == 'fuki' and ba_hito else {})
                kind_g = kind
                if kind == 'midashi' and _bg_kurai(bg):   # 暗い地では帯が下半分の見出しは上半分が沈む → 帯を字の高さ全部にかける（字は黒のまま・作業AI 10/20）
                    if 'midashi_kurai' not in G:
                        try:
                            from ki1 import midashi_kurai as _mk
                        except ImportError:   # 組み場（proj）に古い ki1.py の写しがあるときは、ここで同じ形を作る
                            from ki1 import kit as _kit, GOTH as _GOTH
                            from PIL import ImageDraw as _IDk
                            def _mk(text, size=60):
                                t = _kit.deco(text, size, name=_GOTH, fill=_kit.C('#111111'), pad=4)
                                w_, h_ = t.width + 24, t.height + 4
                                im_ = Image.new('RGBA', (w_, h_), (0, 0, 0, 0)); _IDk.Draw(im_).rectangle([0, 0, w_ - 1, h_ - 1], fill=_kit.C('#fff200'))
                                im_.alpha_composite(t, (12, 0)); return im_
                        G['midashi_kurai'] = _mk
                    kind_g = 'midashi_kurai'; LOG.setdefault('kurai_ji_shiro', []).append({'id': s.get('id'), 'kind': kind})
                img = G[kind_g](p['text'], *([p['px']] if p.get('px') else []), **kw_)
                if kind == 'obi_aka' and img is not None and img.width > W - 32:   # 画面幅の帯は影込みで画面の内に収める（型19・x 16〜1964 で門に止まった 10/20）
                    img = img.resize((W - 32, max(1, int(img.height * (W - 32) / img.width))), Image.LANCZOS)
            elif kind in ('zukai', 'fn'):
                fn_na = p.get('fn')
                # 暗い地（地の明るさ 90 未満・残しで前の暗い地を引き継いだ場面も）に黒い字は読めない → 白い字に替える（10/20 vhm8 地替えの試験・s004 で黒字が地に沈んだ）
                if fn_na in ('kuro', 'kuro_moji') and _bg_kurai(bg):
                    if 'shiro' not in G:
                        from riso_kata import shiro as _shiro; G['shiro'] = _shiro
                    LOG.setdefault('kurai_ji_shiro', []).append({'id': s.get('id'), 'fn': fn_na}); fn_na = 'shiro'
                fn = G.get(fn_na)
                if fn is None: LOG['buhin_nashi'].append({'id': s.get('id'), 'fn': p.get('fn')}); return None
                try: img = fn(*p.get('args', []), **p.get('kwargs', {}))
                except Exception as ex: LOG['buhin_nashi'].append({'id': s.get('id'), 'fn': p.get('fn'), 'err': '%s: %s' % (type(ex).__name__, ex)}); return None
                if a == 'pop' and (getattr(img, 'info', None) or {}).get('pipe_dyn'): a = 'grow'
                img = kiritoru(img)
            elif kind == 'hoshii':   # 指示書が求めた絵が手元に無い：空けずに「欲しかった絵の種類と言葉」を残す（作業AI 10/20・素材が無いための外れを分けて数える）
                LOG['hoshii'].append({'id': s.get('id'), 'shurui': p.get('shurui'), 'mono': p.get('mono') or p.get('name'), 'at': p.get('at'), 'imi': s.get('imi')}); return None
            else:
                LOG['buhin_nashi'].append({'id': s.get('id'), 'kind': kind}); return None
            return img, frames, loop, anchor, x, y, a
        def xy(v, dflt='中'):
            return POS.get(v, POS[dflt]) if isinstance(v, str) else tuple(v)
        # 絵を大きく置く（作業AI 10/19 21:4x）：上の字（見出し）の下端と横の広がりを先に測り、主役の人物は見える中身を画面の高さの45〜60%に
        ba_hito = any(p.get('kind') in ('jinbutsu', 'gamen') for p in s.get('parts', []))
        ue_ji = []
        for p in s.get('parts', []):
            if p.get('kind') in TEXT_KINDS and p.get('kind') != 'fuki':
                x_, y_ = xy(p.get('pos', '中'))
                if y_ > 420: continue
                r_ = build(p, x_, y_, 0, 'none')
                if r_ is None: continue
                im_ = r_[0]; w_ = min(im_.width, W - 60); h_ = im_.height * w_ / max(1, im_.width)
                x_ = min(max(x_, w_ / 2 + 30), W - w_ / 2 - 30); y_ = max(y_, h_ / 2 + 20)
                ue_ji.append((x_ - w_ / 2, x_ + w_ / 2, y_ + h_ / 2))
        hito = [p for p in s.get('parts', []) if p.get('kind') == 'jinbutsu' and not str(p.get('name', '')).startswith('real-')]
        def _sz(p):
            v = p.get('size', '中'); return SIZE.get(v, v) if isinstance(v, str) else int(v)
        shuyaku = max(hito, key=_sz) if hito else None
        def ookiku(p, h, x, y):
            """人物・物の高さ h（枠）を、見える中身が決まりの大きさになるよう直す。指示書の大きさより小さくはしない（上の字にかぶるときだけ字の下まで）。
            見える中身はコマごとの透明でない所＝汗・吹き出し・動きの線も入るので、主役は上限の60%をねらう（r6 の試し：52%では体が画面の3割台だった）"""
            if p.get('kotei'): return h   # 整頓（格子）で大きさを決めた人物は直さない（作業AI 11/03・重なり0のため）
            nai = clip_naiyou(G, p['name'], int(h))
            if nai is None: return h
            rh, rw, rb, asp = nai
            n_ = max(1, len(hito) + sum(1 for q in s.get('parts', []) if q.get('kind') in ('gamen', 'icon3d', 'mono', 'zukai')))
            sita0 = max([sita for lx, rx, sita in ue_ji] or [0])
            if str(p.get('name', '')).startswith('shibai_'):   # 場面まるごとの芝居：字の下の空き（横は画面の94%）いっぱいに
                h2 = min((HITO_SOKO - sita0 - 14) / max(0.05, rh + rb), 0.94 * W / max(0.05, asp))
                h2 = max(h2, h * 0.9)
            else:
                want = (SHUYAKU_H[2] if p is shuyaku else WAKI_H + 0.06) * H
                h2 = max(h, min(want / max(0.05, rh), 0.92 * H, (0.94 * W / n_) / max(0.05, asp * rw)))
            soko = (y + h2 / 2) if p.get('shita_kiri') else min(HITO_SOKO, y + h2 / 2)   # shita_kiri：上半身だけの部品は足もとを字幕帯の上にそろえない（切れ目を画面の下端より下へ・作業AI 10/20 s046）
            for lx, rx, sita in ue_ji:   # 上の字の下に収める（字と人物が横で重なるときだけ・s044）
                hw = asp * rw * h2 / 2
                if lx < x + hw and x - hw < rx and sita + 14 > soko - rb * h2 - rh * h2:
                    h2 = max(h * 0.75, (soko - sita - 14) / max(0.05, rh + rb))
            if abs(h2 - h) > 8: LOG.setdefault('ookiku', []).append({'id': s.get('id'), 'name': p['name'], 'mae': int(h), 'ato': int(h2), 'naiyou': round(rh * h2 / H, 2)})
            return h2
        gamen_t = None
        for p in s.get('parts', []):
            kind = p.get('kind'); ta = at(p.get('at'), p.get('kind', ''))
            if kind in ('kao', 'kawaru'):   # 表情の差し替え（人物）／変形（どの部品も・na で指す）：前の絵から新しい絵へ溶けながら替わる
                e = named.get(p.get('na') or p.get('name'))
                if e is None: LOG['buhin_nashi'].append({'id': s.get('id'), kind: p.get('na') or p.get('name')}); continue
                if kind == 'kao':
                    clipn = p.get('clip') or ('%s_%s' % (p.get('name'), p.get('hyoujou')))
                    fr, lp = clip_frames(G, clipn, sw_h(G, getattr(e, 'clip_name', None), clipn, e.jin_h))
                    if fr is None: LOG['buhin_nashi'].append({'id': s.get('id'), 'kao': clipn}); continue
                else:
                    q = dict(p.get('to') or {}); hq = q.get('size', '中'); hq = SIZE.get(hq, hq) if isinstance(hq, str) else int(hq)
                    r = build(q, e.x0, e.y0, hq, 'none')
                    if r is None: continue
                    fr, lp = (r[1] or [r[0]]), r[2]
                e.switches = tuple(e.switches) + ((ta, fr, lp),); LOG['henkei'] = LOG.get('henkei', 0) + 1
                if p.get('tomaru') is not None: e.stops = dict(getattr(e, 'stops', None) or {}); e.stops[ta] = ta + float(p['tomaru']); LOG['tomaru'] = LOG.get('tomaru', 0) + 1
                continue
            h = p.get('size', '中'); h = SIZE.get(h, h) if isinstance(h, str) else int(h)
            if str(p.get('name', '')).startswith('real-'): h = max(h, REAL_MIN_H)
            x, y = xy(p.get('pos', '中'))
            if kind == 'jinbutsu' and not str(p.get('name', '')).startswith('real-'): h = int(ookiku(p, h, x, y))
            if kind == 'gamen' and not (p.get('w') and p.get('pos') is not None): x, y = 960, 575   # 場所と大きさの両方が書いてある場面は指示書の場所
            n_ = len(LOG['buhin_nashi']); r = build(p, x, y, h, p.get('in') or 'pop')
            if r is None:
                if len(LOG['buhin_nashi']) > n_: LOG['buhin_nashi'][-1].update(at=p.get('at'), imi=s.get('imi'))   # 無かった部品にも言葉を付ける（欲しい絵の一覧の元）
                continue
            img, frames, loop, anchor, x, y, a = r
            if kind == 'jinbutsu': LOG['jinbutsu'] += 1
            kara = p.get('kara')   # 組み上がる：ほかの場所（画面の外も）から飛んできて pos に収まる
            if kara is not None:
                kx, ky = xy(kara)
                if kind == 'jinbutsu': ky = min(950, ky + int(h) // 2)
                p = dict(p); p['move'] = [{'to': [x, y] if kind != 'jinbutsu' else [x, y - int(h) // 2], 'at': p.get('at') if p.get('at') is not None else 0, 'dur': p.get('kara_dur', 0.5)}] + (p['move'] if isinstance(p.get('move'), list) else ([p['move']] if p.get('move') else []))
                x, y = kx, ky
            e = T(ta, img, x, y, a, p.get('dur'), anchor, n=len(re.sub(r'\s', '', p.get('text', ''))) or 10)
            ELEMS = G['ELEMS']
            if frames is not None or p.get('idle') or p.get('move') or p.get('flip') or kind == 'jinbutsu' or p.get('na'):
                e.__class__ = Ugoki; e.frames = frames; e.loop = loop; e.flip = bool(p.get('flip'))
                e.idle = p.get('idle') or ('iki' if kind == 'jinbutsu' and not frames else None)
                e.x0, e.y0 = (e.x, e.y) if kara is None else (x, y)   # 組み上がるは画面の外から（T が画面の内へ寄せた分を戻す）
                mv = p.get('move')
                if mv:
                    mvs = mv if isinstance(mv, list) else [mv]; out = []
                    for m in mvs:
                        to = m.get('to'); x2, y2 = (POS.get(to, POS['中']) if isinstance(to, str) else tuple(to))
                        if kind == 'jinbutsu': y2 = min(950, y2 + int(h) // 2)
                        out.append((at(m.get('at'), '移る') if m.get('at') is not None else ta + (e.dur or 0.3), float(m.get('dur', 0.6)), x2, y2))
                    e.moves = tuple(out)
                LOG['ugoku_bubun'] += 1
            if kind == 'jinbutsu': e.jin_name = p['name']; e.jin_h = int(h); named[p['name']] = e; e.clip_name = p['name']; e.shita_kiri = bool(p.get('shita_kiri'))
            if kind == 'jinbutsu' and p.get('tomaru') is not None: e.stops = {e.ts: e.ts + float(p['tomaru'])}; LOG['tomaru'] = LOG.get('tomaru', 0) + 1   # 入ってから tomaru 秒の絵で止める
            if p.get('na'): e.jin_name = p['na']; e.jin_h = int(h); named[p['na']] = e
            if p.get('out_at'): e.te = at(p['out_at'], '消える')
            e.z = int(p.get('z', 4 if kind in TEXT_KINDS else {'jinbutsu': 1, 'kouka': 3}.get(kind, 2)))   # 字はスポットの暗がりの上（s004）
            e.fn_na = p.get('fn') if kind in ('zukai', 'fn') else None   # 囲みの赤い丸（maru）は字を囲むのが役目なので、部品と字の重なりの見張りから外す（作業AI 10/20 s015 手本の赤い輪）
            e.kind_ = kind; e.is_text = kind in TEXT_KINDS or (kind == 'fn' and str(p.get('fn', '')) in ('kuro', 'kuro_moji', 'shiro')); e.bb_wh = (img.width, img.height); e.text_ = re.sub(r'[\s！!。、…〜~]', '', str(p.get('text', '')))
            if img.mode == 'RGBA': e.bb_in = img.getchannel('A').getbbox()
            sc.elems.append(e); LOG['parts'] += 1
            if kind == 'gamen' and gamen_t is None: gamen_t = (ta, e, p['name'])
        # 1回きりの部品（着地・お辞儀など loop: False）は、動き終わりで続き（<名前>_tsuzuki・繰り返し）へ自動で替える。指示書に kao があればそちらを使う
        for e in sc.elems:
            cn = getattr(e, 'clip_name', None)
            if not cn or e in carried or getattr(e, 'switches', ()) or e.ts in (getattr(e, 'stops', None) or {}): continue   # tomaru で止めた部品は続きへ替えない
            m = clip_meta(cn); tz = (m.get('tsuzuki') or {}).get('name')
            if m.get('loop', True) is not False or not tz: continue
            fr2, lp2 = clip_frames(G, tz, sw_h(G, cn, tz, e.jin_h))
            if fr2 is None: continue
            e.switches = ((e.ts + float(m.get('dur', 2.5)), fr2, True),); LOG['tsuzuki_jidou'] = LOG.get('tsuzuki_jidou', 0) + 1
        if gamen_t is not None and s.get('gamen_yoranai'): LOG.setdefault('gamen_yoranai', []).append(s.get('id'))   # 指示書で寄りを止めた場面（画面は置いたまま）
        elif gamen_t is not None:
            tg, eg, gn = gamen_t; t_from = tg + 1.2
            gw, gh = eg.bb_wh; gl, gt = eg.x - gw / 2, eg.y - gh / 2
            fx_, fy_ = GAMEN_FOCUS.get(gn, (0.5, 0.5))
            fx = (gl + 12 + fx_ * (gw - 24)) / W; fy = (gt + 48 + fy_ * (gh - 60)) / H
            sc.cam = {'kind': 'yoru', 'from': 1.0, 'to': 1.45, 'focus': (fx, fy), 't_from': t_from, 't_dur': 1.0}
            for e in sc.elems:
                if e is not eg and getattr(e, 'is_text', False) and (e.te is None or e.te > t_from): e.te = t_from; e.out = 'fade'
            LOG.setdefault('gamen_yoru', []).append({'id': s.get('id'), 'gamen': gn, 'w': gw, 'focus': [round(fx, 2), round(fy, 2)]})
        for se in s.get('se', []): sfx(at(se.get('at'), '効果音'), se.get('kind', 'pon'))
        mihari(sc, carried, s.get('id'), W, H, LOG)
        add(sc)
        kind_tr = '動く切り替え' if kr in TR_KINDS else ('前を残して足す' if kr == 'keep' else ('実写・画面・写真へ' if ji.startswith('写真:') or any(p.get('kind') == 'gamen' for p in s.get('parts', [])) else '全消し（1コマ）'))
        TRLOG.append({'t': round(t0, 3), 'kind': kind_tr, 'tr': kr if kr in TR_KINDS else None, 'ch': ch, 'ji': jikind, 'id': s.get('id'), 'camera': (s.get('camera') or {}).get('kind')})
        LOG['kirikae'][kr] = LOG['kirikae'].get(kr, 0) + 1
        G['intent'](t0, 'EDL ' + str(s.get('id', '')), s.get('imi', ''), s.get('riyuu', ''), s.get('wakaru', ''))
        prev_sc = sc; LOG['shots'] += 1
    G['KOKUCHI_FROM'] = kokuchi
    # BGM：指示書に bgm があれば、そのとおりに置く（[{"from": 言葉か秒, "to": 言葉か秒, "kyoku": "honpen_gray|honpen_gray_b|kokuchi", "db": -21.5, "off": 曲の頭からの秒}]）
    if E.get('bgm'):
        def _bt(v):
            if isinstance(v, (int, float)): return float(v)
            r = find(v, 0, None, 'BGM'); return r[0] if r else None
        out = []
        for b_ in E['bgm']:
            a_, z_ = _bt(b_.get('from', 0)), _bt(b_.get('to', G['END']))
            if a_ is None or z_ is None: LOG['mitsukaranai'].append({'id': 'bgm', 'kotoba': b_.get('from') if a_ is None else b_.get('to')}); continue
            out.append((a_, min(z_, G['END']), 'bgm/%s.wav' % b_.get('kyoku', 'honpen_gray'), float(b_.get('off', 0.0)), float(b_.get('db', -21.5))))
        G['BGM_EDL'] = out; LOG['bgm'] = len(out)
    else: LOG['bgm'] = '指示書に無い（道具の既定の並べ方）'
    G['CH'] = ''
    json.dump(LOG, open(os.path.join(G['PROJ'], 'work', 'edl_kumi.json'), 'w'), ensure_ascii=False, indent=1)
    # 大字が人物・写真に重なる：割合0.30以上は止める（指示書の直しが要る）・0.15〜0.30は🟡で記録に出す（作業AI 10/20）。試しで通すときだけ PIPE_KASANARI_OK=1
    _hk = LOG.get('mihari', {}).get('ji_hito_kasanari', [])
    if os.environ.get('PIPE_WAKU_DAKE') == '1':   # 枠だけ見る道具（edl_waku.py）：見張りの結果を書いて、書き出しに進まずに終わる（作業AI 10/20）
        _hm0 = LOG.get('mihari', {}).get('gaiwaku_hamidashi', [])
        _wd = {'kasanari_tomeru': [x for x in _hk if x['wariai'] >= 0.30], 'kasanari_kiiro': [x for x in _hk if 0.15 <= x['wariai'] < 0.30],
               'kasanari_hikui': [x for x in _hk if x['wariai'] < 0.15], 'gaiwaku_hamidashi': _hm0, 'zoom': LOG.get('mihari', {}).get('zoom_dashi_chiisaku', []),
               'kara_kasanari_tomeru': {k: LOG.get('mihari', {}).get(k, []) for k in ('kara_gamen', 'buhin_ji_kasanari', 'ji_kasanari_nokoru', 'fuda_kasanari_nokoru') if LOG.get('mihari', {}).get(k)}}
        json.dump(_wd, open(os.path.join(G['PROJ'], 'work', 'waku_dake.json'), 'w'), ensure_ascii=False, indent=1)
        raise SystemExit(0)
    _hk_y = [x for x in _hk if 0.15 <= x['wariai'] < 0.30]; _hk_r = [x for x in _hk if x['wariai'] >= 0.30]
    if _hk_y: print('🟡 EDL：大字が人物・写真に少し重なる %d場面（割合0.15〜0.30・work/edl_kumi.json の mihari.ji_hito_kasanari）：%s' % (len(_hk_y), json.dumps(_hk_y[:12], ensure_ascii=False)), flush=True)
    if _hk_r:
        msg = '🔴 EDL：大字が人物・写真の上に重なる %d場面（割合0.30以上・割合＝大字の枠の中の人物／写真の画素）：%s' % (len(_hk_r), json.dumps(_hk_r[:12], ensure_ascii=False))
        if os.environ.get('PIPE_KASANARI_OK') != '1': raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    # 空の画面と、部品と字（見出しの帯を含む）の重なりの残り：記録だけだったものを止める（作業AI 10/20：vhm8 7版目 s006 層のアイコン・s008 旗が見出しに隠れた）
    _mi = LOG.get('mihari', {})
    _kn = {k: _mi.get(k, []) for k in ('kara_gamen', 'buhin_ji_kasanari', 'ji_kasanari_nokoru', 'fuda_kasanari_nokoru') if _mi.get(k)}
    if _kn:
        msg = '🔴 EDL：空の画面（0.3秒超）／部品と字の重なりが残る（work/edl_kumi.json の mihari）：%s' % json.dumps(_kn, ensure_ascii=False)[:1500]
        if os.environ.get('PIPE_KARA_KASANARI_OK') != '1': raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    _kz0 = LOG.get('mihari', {}).get('kasanari_zenbu', [])
    print('［重なり］図・字・人物・画像の重なり %d か所（%d 場面）' % (len(_kz0), len({x['id'] for x in _kz0})), flush=True)
    if E.get('kasanari0') and _kz0 and os.environ.get('PIPE_KASANARI0_OK') != '1':   # 指示書が重なり0を合格条件にしている版だけ止める
        raise SystemExit('🔴 EDL：重なり %d か所（kasanari0・work/edl_kumi.json の mihari.kasanari_zenbu）：%s' % (len(_kz0), json.dumps(_kz0[:12], ensure_ascii=False)))
    _hm = LOG.get('mihari', {}).get('gaiwaku_hamidashi', [])
    if _hm:   # 外枠が画面から出ている字・札があれば書き出しに進まない（試しで通すときだけ PIPE_GAIWAKU_OK=1）
        msg = '🔴 EDL：字・札の外枠が画面からはみ出す %d件（work/edl_kumi.json の mihari.gaiwaku_hamidashi）：%s' % (len(_hm), json.dumps(_hm[:12], ensure_ascii=False))
        if os.environ.get('PIPE_GAIWAKU_OK') != '1': raise SystemExit(msg)
        print(msg.replace('🔴', '🟡（試しで通す）'), flush=True)
    if LOG['buhin_nashi'] or len(LOG['mitsukaranai']):
        print('🟡 EDL：部品が無い %d件・言葉が場面の外 %d件（work/edl_kumi.json）' % (len(LOG['buhin_nashi']), len(LOG['mitsukaranai'])), flush=True)
    return LOG
