#!/usr/bin/env python3
# zettai-mon.py の試験用の場面表（作業AI・2026-10-19）。work/henkei.json の形で「通る例」と「止まる例」を作り分ける
#   ok    … 9つとも守った形（字幕帯を全部の言葉に・自社キャラのアイコン・手本の作者さんの効果音だけ・挿絵／イラスト／図解／全画面挿絵／実際の画面）
#   gaibu  … gaibu_x の元の効果音（試験専用 se/_shiken_gaibu_pon.wav）を1本入れる
#   telop … 3行目の字幕帯を出さない
#   icon  … 話し手のアイコンを手本の作者さんのロゴの写し（v1_mascot_line）にする
#   koe   … 場面表は ok と同じ（声の方を切ってある）
#   nobgm … BGM を入れない（ルール10）
import os, sys, json
PROJ = os.environ.get('PROJ') or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
from henshu import *
from PIL import Image, ImageDraw, ImageFont
HK = json.load(open(os.path.join(PROJ, 'work', 'henkei.json')))['henkei']
TJ = json.load(open(os.path.join(PROJ, 'work', 'timing.json'))); LINES = TJ['lines']
END = TJ['duration']; SFX_SPARSE = ()
# BGM（ルール10）：手本の作者さんの BGM を全体に。大きさは手本15本の 声−BGM の中央値（zettai/bgm_kijun.json）。nobgm は入れない
_BK = json.load(open(os.path.join(os.path.expanduser('~/rin6/tools/yt-henshu/zettai'), 'bgm_kijun.json')))['声−BGM（dB）の幅（BGMが8割以上の本）']['中央値']
BGM = [] if HK == 'nobgm' else [(0.0, END, 'bgm/honpen_gray.wav', 0.0, -_BK)]
# gaibu：gaibu_x の元の pon（試験専用に se/_shiken_gaibu_pon.wav として置き、帳簿に gaibu_x で載せた）を 2秒の所で鳴らす。
#   sound_map.json は oto-tokutei の持ち場なので触らず、素材集の音を直接重ねる BGM の筋で鳴らす
if HK == 'gaibu': BGM.append((2.0, 4.0, 'se/_shiken_gaibu_pon.wav', 0.0, -6.0))
GOTH = '/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc'
A = os.path.join(paths.ENGINE, 'assets'); GAMEN = os.path.expanduser('~/rin6/state/yt-evervsl-1019/e/gamen')

def band(text):
    """下の紺の字幕帯（手本の形・白い字）。長い行は2段"""
    f = ImageFont.truetype(GOTH, 50)
    rows = [text[i:i + 30] for i in range(0, len(text), 30)][:2]
    im = Image.new('RGBA', (1840, 70 * len(rows) + 30), (16, 32, 84, 235)); d = ImageDraw.Draw(im)
    for k, r in enumerate(rows): d.text((920, 50 + 70 * k), r, font=f, fill=(255, 255, 255, 255), anchor='mm')
    im.info['text'] = text; return im
def icon():
    src = os.path.join(A, 'v1_mascot_line.png' if HK == 'icon' else 'chara_flat.png')
    im = Image.open(src).convert('RGBA').resize((220, 220)); c = Image.new('RGBA', (240, 240), (60, 180, 90, 255))
    m = Image.new('L', (240, 240), 0); ImageDraw.Draw(m).ellipse([0, 0, 239, 239], fill=255); c.putalpha(m); c.alpha_composite(im, (10, 10)); return c
def pic(name, w): return fit(Image.open(os.path.join(A, name)).convert('RGBA'), w=w)
def gamen(name, w=900):
    im = Image.open(os.path.join(GAMEN, name)).convert('RGBA'); return fit(im, w=w)
def zukai(t):
    im = Image.new('RGBA', (700, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = ImageFont.truetype(GOTH, 44)
    for k, s in enumerate(('指示', '実行', '完成')):
        d.rounded_rectangle([k * 240, 60, k * 240 + 200, 200], 20, fill=(255, 200, 0, 255)); d.text((k * 240 + 100, 130), s, font=f, fill=(20, 20, 20, 255), anchor='mm')
    return im

COL = [(200, 30, 40), (20, 40, 120), (240, 180, 0), (0, 120, 90), (120, 20, 120), (210, 90, 0)]
k = 0
for n, x in enumerate(LINES):
    a, b = x['start'], x['end']
    cuts = [a] + ([a + (b - a) / 2] if b - a > 3 else [])
    for j, t0 in enumerate(cuts):
        t1 = cuts[j + 1] if j + 1 < len(cuts) else b
        el = []
        if not (HK == 'telop' and n == 2): el.append(R(t0, band(x['text']), 40, 1080 - band(x['text']).height - 20, 'lt', 'pop', s='telop'))
        el.append(R(t0, icon(), 60, 60, 'lt', 'pop', s='whoosh'))
        if k % 5 == 0: el.append(R(t0, pic('p_man_think.png', 360), 1500, 120, 'lt', 'pop', s='don'))          # イラスト
        if k % 5 == 1: el.append(R(t0, zukai(t0), 600, 300, 'lt', 'pop', s='don'))                            # 図解
        if k % 5 == 2: el.append(R(t0, gamen('01_55.png'), 500, 200, 'lt', 'pop', s='don'))   # 実際の画面
        if k % 5 == 3: el.append(R(t0, pic('p_office.png', 1920).crop((0, 0, 1920, 1080)), 0, 0, 'lt', 'fade', s='whoosh'))   # 全画面挿絵
        if k % 5 == 4: el.append(R(t0, pic('ph_desk.png', 520), 1300, 250, 'lt', 'pop', s='don'))           # 挿絵
        # 動く要素を手本の密度へ：場面の頭の 0.8 秒あとから 0.5 秒おきに小さな札（場面の切り替わりと切り替わりの溶け（0.22秒）も含めて12コマより離す＝ずれの測りが切り替わりを拾わない）
        for m, tt in enumerate([t0 + 0.8 + 0.5 * i for i in range(8) if t0 + 0.8 + 0.5 * i < t1 - 0.2]):
            ch = Image.new('RGBA', (320, 140), (255, 255, 255, 235)); ImageDraw.Draw(ch).text((160, 70), '✓ %d' % (m + 1), font=ImageFont.truetype(GOTH, 80), fill=(200, 20, 30, 255), anchor='mm')
            el.append(R(tt, ch, 1560, 300 + (m % 3) * 160, 'lt', 'pop', s='kira_hi'))
        add(Sc(t0, t1, el, bg=COL[k % len(COL)], ring=False, zoom=None)); k += 1
finish(END)
json.dump({'ev': [], 'elems': [{'t': round(getattr(e, 't_plan', 0), 4), 'x': e.x, 'y': e.y, 'anchor': e.anchor, 'w': e._src.width, 'h': e._src.height, 'anim': e.anim}
                               for e in ELEMS if e.anim != 'none']}, open(os.path.join(PROJ, 'work', 'zure-plan.json'), 'w'), ensure_ascii=False)
if __name__ == '__main__': print(len(SCENES), 'scenes', len(SFX), 'sfx', 'END %.2f' % END)
