#!/usr/bin/env python3
# 場面表（stories/*.json）→ 部品の並び。どのジャンル・内容でも同じ形で書ける。
#   時刻は「at: 秒」か「say: 話す言葉（文字起こしからそのまま写す）」。say は文字起こしの単語の時刻から自動で秒に直す。
#   場面の種類（type）と中の部品の置き方は下の T_* が決める＝位置は自動。細かく置きたいときは type: custom。
import os, json, re, unicodedata, difflib
from anim import *

# ---------------- 言葉 → 秒 ----------------
_PUNCT = re.compile(r'[\s、。，．,\.！!？\?「」『』（）\(\)・…ー〜~：:;；"\'”“]')
def norm(s):
    s = unicodedata.normalize('NFKC', s).lower()
    return _PUNCT.sub('', s)

class Clock:
    """words.json（[開始, 終わり, 言葉] の並び）から、言葉の話し始めの秒を引く"""
    def __init__(self, words):
        self.chars = []; self.times = []
        for a, b, w in words:
            n = norm(w)
            for k, ch in enumerate(n):
                self.chars.append(ch); self.times.append(a + (b - a) * k / max(1, len(n)))
        self.text = ''.join(self.chars)
        self.cursor = 0
        self.log = []
    def find(self, phrase, after=None):
        q = norm(phrase)
        if not q: raise ValueError('空の say')
        start = self.cursor if after is None else self._idx(after)
        i = self.text.find(q, start)
        if i < 0: i = self.text.find(q)  # 前に戻って探す
        if i < 0:  # あいまいに探す（文字起こしの誤字に強く）
            best = (0, None)
            for j in range(max(0, start - 50), len(self.text) - len(q) + 1):
                r = difflib.SequenceMatcher(None, q, self.text[j:j + len(q)]).ratio()
                if r > best[0]: best = (r, j)
                if r > 0.95: break
            if best[0] < 0.6: raise ValueError('say が文字起こしに見つかりません: %s' % phrase)
            i = best[1]
        self.cursor = i + 1
        t = self.times[i]; self.log.append((phrase, round(t, 2)))
        return t
    def _idx(self, t):
        for k, x in enumerate(self.times):
            if x >= t: return k
        return len(self.times)

def T(clock, d, key_at='at', key_say='say', default=None):
    """部品の時刻を決める: at（秒）か say（言葉）＋ off（ずらし）"""
    if d is None: return default
    if isinstance(d, (int, float)): return float(d)
    if key_at in d and d[key_at] is not None: t = float(d[key_at])
    elif key_say in d and d[key_say]: t = clock.find(d[key_say])
    else: t = default
    return None if t is None else t + float(d.get('off', 0))

# ---------------- 色の名前 ----------------
NAMED = {'orange': (250, 150, 60), 'blue': (90, 170, 220), 'purple': (110, 30, 200), 'green': (40, 190, 80),
         'pink': (240, 90, 150), 'gray': (120, 120, 130), 'navy': (20, 40, 120), 'red': (230, 40, 50)}
def col(x, default='orange'):
    if x is None: x = default
    if isinstance(x, (list, tuple)): return tuple(x)
    return tuple(THEME.get('colors', {}).get(x, NAMED.get(x, NAMED['orange'])))

IMPACT = {  # 太い見出しの色の組（上の色・下の色・外フチ・フォント）
    'red': ((255, 60, 60), (120, 0, 10), (40, 0, 10), 'pop'),
    'purple': ((130, 40, 255), (40, 0, 110), (20, 0, 40), 'noto'),
    'white': ((255, 255, 255), (235, 235, 235), (30, 30, 30), 'pop'),
    'gold': ((255, 250, 225), (235, 195, 80), (40, 30, 0), 'pop'),
    'pinkwhite': ((255, 235, 235), (205, 25, 35), (90, 0, 0), 'pop'),
    'redbold': ((255, 70, 70), (170, 0, 20), (40, 0, 10), 'dela'),
}
def impact_from(d, size=180):
    st = IMPACT[d.get('color', 'red')]
    return impact_img(d['text'], d.get('size', size), top=st[0], bottom=st[1], out_color=st[2], name=d.get('font', st[3]),
                      angle=d.get('angle', 0), align=d.get('align', 'left'))

def fit_text_size(text, base, maxw, wght=900, name='noto'):
    """横幅に収まる文字の大きさ（大きすぎるときだけ縮める）"""
    w = text_img(text, size=base, wght=wght, name=name)[0].width
    return base if w <= maxw else max(24, int(base * maxw / w))

# ---------------- 小さな部品 ----------------
def title_tiles(text, size=96, color=(230, 20, 30)):
    f = font(size, 900); n = len(text); s = int(size * 1.12); gap = 6
    im = Image.new('RGBA', (n * (s + gap), s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, ch in enumerate(text):
        x = i * (s + gap); d.rectangle([x, 0, x + s, s], fill=color)
        d.text((x + s / 2, s / 2), ch, font=f, fill=WHITE, anchor='mm')
    return im

def redbox(text, size=78, color=(235, 20, 30)):
    t, _ = text_img(text, size=size, wght=900, color=WHITE, pad_x=0)
    t = t.crop(t.getbbox())
    h = int(size * 1.3)
    im = Image.new('RGBA', (t.width + 50, h), color + (255,))
    im.alpha_composite(t, (25, (h - t.height) // 2))
    return im

def stamp(text, size=50, angle=8):
    t, _ = text_img(text, size=size, wght=900, color=WHITE, align='center', pad_x=0, line_gap=0.1)
    w, h = t.width + 50, t.height + 10
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    g = lin_grad(w, h, [(0, (230, 40, 40)), (1, (140, 0, 0))])
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], 10, fill=255)
    im.paste(g, (0, 0), m)
    ImageDraw.Draw(im).rounded_rectangle([5, 5, w - 6, h - 6], 8, outline=WHITE, width=4)
    im.alpha_composite(t, (25, -4))
    im, _ = shadowed(im, off=(4, 8), blur=8, alpha=0.35, pad=20)
    return im.rotate(angle, resample=Image.BICUBIC, expand=True)

def person(name, label=None, color=None, h=330):
    im = fit(asset(name), h=h)
    if not label: return im
    lb = label_img(label, col(color, 'navy'), size=int(h * 0.19), pad=(int(h * 0.085), 6))
    out = Image.new('RGBA', (max(im.width, lb.width), im.height + lb.height - 10), (0, 0, 0, 0))
    out.alpha_composite(im, ((out.width - im.width) // 2, 0))
    out.alpha_composite(lb, ((out.width - lb.width) // 2, im.height - 10))
    return out

ICONS = {'check': lambda s: check_icon(int(s * 1.2)), 'star': lambda s: star_img(int(s * 1.35)),
         'glyph': lambda s: insta_glyph(int(s * 1.2)), 'share': lambda s: share_icon(int(s * 1.5)),
         'faceng': lambda s: face_ng_icon(int(s * 1.6))}
def num_icon(n, s):
    d = int(s * 1.15); im = Image.new('RGBA', (d, d), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse([0, 0, d - 1, d - 1], fill=RED); dr.text((d / 2, d / 2), str(n), font=font(int(d * 0.62), 900), fill=WHITE, anchor='mm')
    return im

def item_row(t, x, y, text, size, icon, n=None, text_anim='wipe'):
    ic = num_icon(n, size) if icon == 'num' else (ICONS[icon](size) if icon else None)
    out = []
    tx = x
    if ic is not None:
        out.append(Icon(t, ic, x=x, y=y + int(size * 0.3), anim='bounce' if icon == 'star' else 'pop', dur=0.3 if icon == 'star' else None))
        tx = x + ic.width + int(size * 0.25)
    out.append(Text(t + 0.08, text, size=size, wght=800 if icon == 'star' else 700, x=tx, y=y, anim=text_anim))
    return out, tx

# ---------------- 場面の型 ----------------
LOGO_SAFE_X = 1480  # 右下のロゴにかからない横幅の目安

def T_logo(c, sc, t0):
    return [Raw(t0, ring_logo(int(THEME['logo']['d'] * 1.15)), x=W // 2, y=H // 2, anchor='cc', anim='pop', dur=0.35)]

def T_title(c, sc, t0):
    E = []
    if sc.get('phone', True): E.append(Raw(t0, phone_img(690), x=70, y=160, anim='up', dur=0.35))
    x0 = 500 if sc.get('phone', True) else 120
    xt = x0
    if sc.get('logo'):
        lg = sc['logo']; el = Text(T(c, lg, default=t0 + 0.6), lg['text'], size=lg.get('size', 150), name=lg.get('font', 'script'),
                                   color=INK, x=x0, y=60, anim='wipe', dur=0.5)
        E.append(el); xt = x0 + el.image().width - 10
    if sc.get('tiles'):
        tl = sc['tiles']; E.append(Raw(T(c, tl, default=t0 + 1.2), title_tiles(tl['text'], tl.get('size', 150)), x=tl.get('x', xt), y=150, anim='pop'))
    y = 400
    for ln in sc.get('lines', []):
        t = T(c, ln); st = ln.get('style', 'marker'); size = ln.get('size', 72)
        if st == 'redbox':
            im = redbox(ln['text'], ln.get('size', 120)); E.append(Raw(t, im, x=x0 + 20, y=y, anim='pop')); y += im.height + 40
        else:
            E.append(Text(t, ln['text'], size=size, wght=900, marker=YEL, x=x0 + ln.get('dx', 60), y=y)); y += int(size * 1.7)
    return E

def T_marker(c, sc, t0):
    lines = sc['text']; size = sc.get('size', 136)
    maxw = 1150 if sc.get('image') else 1400
    size = fit_text_size(lines, size, maxw)
    E = [Text(T(c, sc.get('show', sc), default=t0), lines, size=size, wght=900, marker=YEL, x=100, y=sc.get('y', 170), line_gap=0.32)]
    if sc.get('image'):
        im = sc['image']; E.append(Img(T(c, im, default=t0 + 0.3), im['name'], h=im.get('h', 520), x=1250, y=120, anim='up'))
    return E

def T_dialogue(c, sc, t0):
    E = []; rows = sc['rows']; n = len(rows)
    ph = sc.get('person_h', 400 if n <= 2 else 300); y = sc.get('y', 90); gap = (H - 200 - y) // max(1, n)
    for k, r in enumerate(rows):
        t = T(c, r, default=t0); side = r.get('side', 'left'); size = r.get('size', 104 if n <= 2 else 78)
        yy = y + k * gap
        bub = bubble_img(r['text'], color=col(r.get('color'), 'orange'), tail=side if side in ('left', 'right') else 'none', size=size,
                         thought=r.get('thought', False))
        if side == 'left':
            if r.get('person'): E.append(Img(t - 0.2, r['person'], h=ph, x=60, y=yy, anim='up'))
            E.append(Raw(t, bub, x=(60 + int(ph * 0.75)) if r.get('person') else 60, y=yy + 10, anim='pop'))
        else:
            if r.get('person'): E.append(Img(t - 0.2, r['person'], h=ph, x=1480, y=yy, anim='up'))
            E.append(Raw(t, bub, x=1460 - bub.width + 40, y=yy + 10, anim='pop'))
    return E

def T_impact(c, sc, t0):
    E = []
    for k, p in enumerate(sc.get('circles', [])):
        E.append(CirclePhoto(t0 + 0.12 * k, p, d=380, x=40 + 430 * k, y=30, tg=T(c, sc.get('gray'), default=t0 + 0.35)))
    y = sc.get('y', 330 if sc.get('circles') else 200)
    for ln in sc.get('lines', []):
        im = impact_from(ln, ln.get('size', 180))
        y = ln.get('y', y)
        E.append(Raw(T(c, ln, default=t0), im, x=ln.get('x', 60), y=y, anim='zoom', dur=0.22)); y += int(im.height * 0.72)
    return E

def T_list(c, sc, t0):
    E = []; items = sc['items']; icon = sc.get('icon', 'check'); card = sc.get('card', False)
    x0, y0 = (80, 80) if card else (40, 30)
    if sc.get('title'):
        tt = sc['title']; E.append(Text(T(c, tt, default=t0), tt['text'], size=tt.get('size', 84), wght=900, marker=YEL, x=30, y=10)); y0 = 200
    nlines = sum(it['text'].count('\n') + 1 for it in items)
    avail = (H - 120 - y0) if not card else (H - 180 - y0)
    size = sc.get('size') or int(min(84, avail / (nlines * 1.45 + 0.4 * len(items))))
    ends_high = y0 + sum((it['text'].count('\n') + 1) * size * 1.45 + size * 0.4 for it in items) < 640  # ロゴ（右下）より上で終わる
    maxw = (1800 if (card or ends_high) else LOGO_SAFE_X) - x0 - int(size * 1.6)
    size = min([fit_text_size(it['text'], size, maxw, wght=800) for it in items])
    pitch = size * 1.45
    if card:
        h = int(sum((it['text'].count('\n') + 1) * pitch + size * 0.4 for it in items) + 80)
        E.append(Card(T(c, sc.get('card_at'), default=t0 + 0.1), sc.get('card_w', 1820 if size >= 76 else 1360), h, x=40, y=y0 - 40))
    y = y0
    rows = []
    for k, it in enumerate(items):
        els, tx = item_row(T(c, it, default=t0 + 0.5 + k), x0, int(y), it['text'], size, icon, n=k + 1)
        E += els; rows.append((tx, int(y), it['text']))
        y += (it['text'].count('\n') + 1) * pitch + size * 0.4
    if sc.get('highlight'):
        th = T(c, sc['highlight'])
        for k, (tx, yy, txt) in enumerate(rows):
            E.append(Text(th + 0.25 * k, txt, size=size, wght=700, marker=PALE_Y, x=tx, y=yy, z=1))
    if sc.get('image'):
        im = sc['image']; E.append(Img(T(c, im, default=t0 + 1), im['name'], h=im.get('h', 380), x=im.get('x', 1180), y=im.get('y', 230), anim='up'))
    return E

def T_people(c, sc, t0):
    E = []; items = sc['items']; n = len(items); ph = sc.get('h', 400)
    span = 1500; step = span // n
    for k, it in enumerate(items):
        E.append(Raw(T(c, it, default=t0 + 0.5 * k), person(it['person'], it.get('label'), it.get('color'), ph),
                     x=120 + step * k + step // 2, y=90, anchor='ct', anim='up'))
    if sc.get('impact'):
        im = impact_from(sc['impact'], 200); E.append(Raw(T(c, sc['impact']), im, x=780, y=640, anchor='ct', anim='zoom', dur=0.22))
    return E

def T_stat(c, sc, t0):
    E = []
    if sc.get('title'): E.append(Text(T(c, sc['title'], default=t0), sc['title']['text'], size=104, wght=900, marker=YEL, x=20, y=10))
    ch = sc.get('chart', {}); E.append(Chart(T(c, ch, default=t0 + 0.8), w=900, h=640, x=430, y=230, dur=1.8, pts=ch.get('points')))
    if sc.get('badge'):
        b = sc['badge']; E.append(Badge(T(c, b, default=t0 + 1.2), lines=tuple(b['lines']), d=420, x=40, y=290))
    return E

def T_headline(c, sc, t0):
    """大きな見出し（1行ずつ・強調つき）＋必要なら太い見出し・はんこ・絵"""
    E = []; y = sc.get('y', 40); x = sc.get('x', 30)
    if sc.get('image'):
        im = sc['image']; E.append(Img(T(c, im, default=t0), im['name'], h=im.get('h', 330), x=40, y=20, anim='up')); x = 330
    for ln in sc.get('lines', []):
        size = ln.get('size', 100); t = T(c, ln, default=t0)
        if ln.get('then'):  # 同じ行の後ろ半分を後から出す（例: 「上手くいかない人の」→「99%が」）
            a = Text(t, ln['text'], size=size, wght=900, x=ln.get('x', x), y=y + ln.get('dy', 0), marker=YEL if ln.get('marker') else None, line_gap=0.22)
            E.append(a); wa = a.image().width
            th = ln['then']
            E.append(Text(T(c, th), th['text'], size=size, wght=900, x=ln.get('x', x) + wa - 20, y=y + ln.get('dy', 0) + th.get('dy', -88), anim='pop', dur=0.28))
            y += int(size * 1.6) + ln.get('gap', 40)
            continue
        el = Text(t, ln['text'], size=size, wght=900, x=ln.get('x', x), y=y, marker=YEL if ln.get('marker') else None,
                  anim='pop' if ln.get('pop') else 'wipe', dur=0.3 if ln.get('pop') else None, line_gap=0.22,
                  stroke=6 if ln.get('pop') else 0)
        E.append(el); y += el.image().height + ln.get('gap', 20); x = sc.get('x', 30) if not sc.get('image') or y > 400 else x
    if sc.get('impact'):
        im = impact_from(sc['impact'], 250); E.append(Raw(T(c, sc['impact']), im, x=sc['impact'].get('x', 10), y=sc['impact'].get('y', 330), anim='zoom', dur=0.22))
    if sc.get('stamp'):
        st = sc['stamp']; E.append(Raw(T(c, st), stamp(st['text'], st.get('size', 70), st.get('angle', 7)), x=st.get('x', 1060), y=st.get('y', 760), anim='bounce', dur=0.3))
    return E

def T_iconcard(c, sc, t0):
    """白い板に「印＋大きな文字」の行（顔出しNG・拡散 など）＋下に結論"""
    E = [Card(t0 + 0.2, 1800, 120 + 260 * len(sc['items']), x=60, y=40)]
    for k, it in enumerate(sc['items']):
        t = T(c, it, default=t0 + 1 + k); y = 55 + 245 * k
        ic = ICONS[it.get('icon', 'check')](100)
        E.append(Icon(t, ic, x=100, y=y + 30)); E.append(Text(t + 0.05, it['text'], size=92, wght=800, x=270, y=y))
    if sc.get('after'):
        a = sc['after']; E.append(Text(T(c, a), a['text'], size=104, wght=900, marker=YEL, x=60, y=120 + 260 * len(sc['items']) + 60, anim='pop', dur=0.28))
    return E

def T_photo(c, sc, t0):
    E = []
    if sc.get('impact'):
        im = impact_from(sc['impact'], 210)
        E.append(Raw(T(c, sc['impact']), im, x=W // 2, y=sc['impact'].get('y', 300), anchor='ct', anim='zoom', dur=0.22))
    return E

def T_custom(c, sc, t0):
    E = []
    for e in sc['elems']:
        t = T(c, e, default=t0); k = e['kind']; kw = dict(x=e.get('x', 0), y=e.get('y', 0), anchor=e.get('anchor', 'lt'))
        if k == 'text': E.append(Text(t, e['text'], size=e.get('size', 72), wght=e.get('wght', 900), marker=YEL if e.get('marker') else None, anim=e.get('anim', 'wipe'), **kw))
        elif k == 'bubble': E.append(Bubble(t, e['text'], col(e.get('color')), e.get('tail', 'left'), size=e.get('size', 72), thought=e.get('thought', False), **kw))
        elif k == 'img': E.append(Img(t, e['name'], h=e.get('h'), w=e.get('w'), anim=e.get('anim', 'up'), **kw))
        elif k == 'impact': E.append(Raw(t, impact_from(e), anim='zoom', dur=0.22, **kw))
        elif k == 'stamp': E.append(Raw(t, stamp(e['text'], e.get('size', 70), e.get('angle', 7)), anim='bounce', dur=0.3, **kw))
        elif k == 'redbox': E.append(Raw(t, redbox(e['text'], e.get('size', 100)), anim='pop', **kw))
        elif k == 'circle': E.append(CirclePhoto(t, e['name'], d=e.get('d', 380), tg=e.get('gray'), **kw))
        else: raise ValueError('知らない部品: %s' % k)
    return E

TYPES = {'logo': T_logo, 'title': T_title, 'marker': T_marker, 'dialogue': T_dialogue, 'impact': T_impact, 'list': T_list,
         'people': T_people, 'stat': T_stat, 'headline': T_headline, 'iconcard': T_iconcard, 'photo': T_photo, 'custom': T_custom}

def overlay(c, ov, z0=3):
    """画面を暗くして、反応の吹き出しや見出しを重ねる（どの場面にも付けられる）"""
    t = T(c, ov); E = [Dim(t, alpha=ov.get('dim', 0.6), z=z0)]
    y = 70
    for b in ov.get('bubbles', []):
        E.append(Bubble(T(c, b), b['text'], col(b.get('color'), 'purple'), 'none', size=b.get('size', 58), x=30, y=y, anim='left', dur=0.2, z=z0 + 1)); y += 200
    if ov.get('impact'):
        E.append(Raw(T(c, ov['impact'], default=t + 0.4), impact_from(ov['impact'], 180), x=ov['impact'].get('x', 140), y=ov['impact'].get('y', 100), anim='bounce', dur=0.3, z=z0 + 1))
    return E

# ---------------- 字幕 ----------------
def auto_subs(words, maxlen=24, gap=0.6):
    """文字起こしから字幕を自動で切る（句読点・間・字数で区切る）"""
    out = []; cur = ''; t0 = None; last_end = None
    for a, b, w in words:
        if t0 is None: t0 = a
        if last_end is not None and a - last_end > gap and cur:
            out.append([t0, last_end + 0.2, cur]); cur = ''; t0 = a
        cur += w.strip(); last_end = b
        if re.search(r'[、。！？!?]$', w.strip()) and len(cur) >= 8 or len(cur) >= maxlen:
            out.append([t0, b + 0.15, cur.rstrip('、。')]); cur = ''; t0 = None
    if cur: out.append([t0, last_end + 0.3, cur])
    for k in range(len(out) - 1): out[k][1] = min(out[k][1] + 0.4, out[k + 1][0])
    return [tuple(x) for x in out]

# ---------------- 読み込み ----------------
def load_story(path):
    st = json.load(open(path))
    words = json.load(open(os.path.join(BASE, st['words'])))
    c = Clock(words)
    raw = []
    for sc in st['scenes']:
        t0 = T(c, sc); raw.append((t0, sc))
    scenes = []
    for k, (t0, sc) in enumerate(raw):
        t1 = raw[k + 1][0] if k + 1 < len(raw) else st.get('end', t0 + 5)
        c.cursor = c._idx(t0 - 0.5)
        E = TYPES[sc['type']](c, sc, t0)
        if sc.get('extra'): E += T_custom(c, {'elems': sc['extra']}, t0)
        if sc.get('overlay'): E += overlay(c, sc['overlay'])
        bgp = sc.get('photo')
        scenes.append(Scene(t0, t1, E, bg=bgp, kb=tuple(sc.get('zoom', [1.0, 1.07])), dim=sc.get('dim', 0.0),
                            ring=sc.get('ring', not bool(bgp) and sc['type'] != 'logo'), trans=sc.get('trans', 0 if k == 0 else 0.22),
                            photo_focus=tuple(sc.get('focus', [0.5, 0.5]))))
    subs = st.get('subs', 'auto')
    if subs == 'auto': items = auto_subs(words)
    else:
        c.cursor = 0
        items = []
        for s in subs:
            a = T(c, s); b = s.get('to') if 'to' in s else (a + s['dur'] if 'dur' in s else None)
            items.append([a, b, s['text']])
        for k in range(len(items)):
            if items[k][1] is None: items[k][1] = min(items[k][0] + 3.0, items[k + 1][0]) if k + 1 < len(items) else items[k][0] + 2.5
    scenes = build_timeline(scenes)
    return scenes, Subs([tuple(x) for x in items]), st, c
