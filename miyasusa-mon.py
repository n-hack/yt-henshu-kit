#!/usr/bin/env python3
# 見やすさの門（依頼主 10/22 20:33「視認性悪いところあったからそこは気をつけてね」・zen5 への返事）
#   python3 miyasusa-mon.py <動画.mp4> [--t0 0 --t1 秒] [--fps 2] [--out kekka.json] [--sheet 並べシートの置き場] [--mon]
#   1秒に fps コマ・1920x1080 で ocr（Vision）にかけ、読めた字の箱ごとに測る：
#     コントラスト比  箱の中の明るさを大津の方法で2つに分け、2つの組の相対輝度（WCAG）の平均どうしの比。縁取り・帯つきの字は縁と中で高く出る
#                     4.5 未満＝赤・3 未満＝真っ赤（WCAG 2.x の本文の基準と大きい字の基準）
#     字の高さ        箱の高さ（1080p の画素）。SMALL_PX 未満＝小さすぎ
#     重なり          別の字の箱どうしが重なる（小さい方の面積の 25% 以上）＝字の上に字
#     読めなさ        ocr の確からしさが 0.5 未満（参考・判定しない）
#   同じ字が同じ所に続けて出た分を1つの「出」にまとめ、MOTSU 秒以上続いて悪い出だけ数える（出入りの動きの途中のコマは数えない）
#   --mon：赤の出が1つでもあれば exit 1（納品前の門）
import os, sys, json, argparse, subprocess, tempfile, re
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageDraw

OCR = os.path.expanduser('~/rin6/tools/yt-henshu/ocr')
AKA, MAKKA = 4.5, 3.0          # WCAG 2.x：本文 4.5・大きい字 3
SMALL_PX = 24                  # 1080p で箱の高さ 24 画素未満＝小さすぎ（手本15本で決め直す・下の --sen）
KASANARI = 0.25
MOTSU = 1.0                    # 悪い状態がこの秒数以上続いた出だけ数える
CONF_MIN = 0.3

def lin(c):
    c = c / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def otsu(v):
    h, e = np.histogram(v, bins=64, range=(0, 1)); h = h.astype(np.float64); w = h.sum()
    if w == 0: return 0.5
    mid = (e[:-1] + e[1:]) / 2; best, th = -1, 0.5; w0 = 0; s0 = 0; st = (h * mid).sum()
    for i in range(63):
        w0 += h[i]; s0 += h[i] * mid[i]; w1 = w - w0
        if w0 == 0 or w1 == 0: continue
        m0 = s0 / w0; m1 = (st - s0) / w1; b = w0 * w1 * (m0 - m1) ** 2
        if b > best: best, th = b, e[i + 1]
    return th

def kontorasuto(img, box):
    """箱の中を明るさで2つに分け（大津）、2つの組の 相対輝度の比・色相の差・彩度・くっきり具合 を返す"""
    W, H = img.size; x, y, w, h = box
    x0, y0 = max(0, int(x * W) - 3), max(0, int(y * H) - 3); x1, y1 = min(W, int((x + w) * W) + 3), min(H, int((y + h) * H) + 3)
    if x1 - x0 < 4 or y1 - y0 < 4: return None
    a = np.asarray(img.crop((x0, y0, x1, y1)).convert('RGB')).astype(np.float64)
    L = 0.2126 * lin(a[..., 0]) + 0.7152 * lin(a[..., 1]) + 0.0722 * lin(a[..., 2])
    g = L ** (1 / 2.2)                   # 目に近い明るさで分ける
    t = otsu(g.ravel()); mh = g > t; ml = ~mh
    if mh.sum() < 5 or ml.sum() < 5: return {'c': 1.0, 'hue_d': 0.0, 'sat_min': 0.0, 'sharp': 0.0}
    a1, a2 = float(np.median(L[mh])), float(np.median(L[ml]))
    c = round((max(a1, a2) + 0.05) / (min(a1, a2) + 0.05), 2)
    def hs(m):
        r, gg, bb = [float(np.median(a[..., k][m])) / 255 for k in range(3)]
        mx, mn = max(r, gg, bb), min(r, gg, bb); sat = 0 if mx == 0 else (mx - mn) / mx
        if mx == mn: hue = 0.0
        elif mx == r: hue = (60 * ((gg - bb) / (mx - mn))) % 360
        elif mx == gg: hue = 60 * ((bb - r) / (mx - mn)) + 120
        else: hue = 60 * ((r - gg) / (mx - mn)) + 240
        return hue, sat
    h1, s1 = hs(mh); h2, s2 = hs(ml); hd = abs(h1 - h2); hd = min(hd, 360 - hd)
    gy = g * 255; lap = np.abs(gy[1:-1, 1:-1] * 4 - gy[:-2, 1:-1] - gy[2:, 1:-1] - gy[1:-1, :-2] - gy[1:-1, 2:])
    sharp = float(np.percentile(lap, 95)) if lap.size else 0.0
    return {'c': c, 'hue_d': round(hd, 1), 'sat_min': round(min(s1, s2), 2), 'sharp': round(sharp, 1)}

def yomu(mp4, t0, t1, fps, d):
    vf = 'fps=%s,scale=1920:1080' % fps
    cmd = ['ffmpeg', '-v', 'error', '-ss', str(t0)] + (['-t', str(t1 - t0)] if t1 else []) + ['-i', mp4, '-vf', vf, os.path.join(d, '%05d.png')]
    subprocess.run(cmd, check=True)
    ps = sorted(os.path.join(d, x) for x in os.listdir(d) if x.endswith('.png'))
    def run(ch): return subprocess.run([OCR] + ch, capture_output=True, text=True).stdout.splitlines()
    rows = {}
    with ThreadPoolExecutor(8) as ex:
        for out in ex.map(run, [ps[i:i + 20] for i in range(0, len(ps), 20)]):
            for l in out:
                if l.strip(): r = json.loads(l); rows[r['p']] = r.get('r') or []
    return ps, rows

def norm(s): return re.sub(r'\s+', '', s)

def yomu_raw(mp4, t0=0.0, t1=None, fps=2):
    """1コマごとに読めた字の箱と、その箱の色の測り（判定はしない・線を変えて何度でも判定し直せるように残す）"""
    d = tempfile.mkdtemp(prefix='miyasusa-')
    ps, rows = yomu(mp4, t0, t1, fps, d)
    koma = []
    for i, p in enumerate(ps):
        t = round(t0 + i / fps, 2); bx = [b for b in rows.get(p, []) if b[5] >= CONF_MIN and len(norm(b[0])) >= 2]   # 1字（！・？など記号）は絵と見分けられないので外す
        out = []
        if bx:
            img = Image.open(p)
            for k, b in enumerate(bx):
                m = kontorasuto(img, b[1:5])
                if m is None: continue
                kas = False
                for j, o in enumerate(bx):
                    if j == k: continue
                    ix = max(0, min(b[1] + b[3], o[1] + o[3]) - max(b[1], o[1])); iy = max(0, min(b[2] + b[4], o[2] + o[4]) - max(b[2], o[2]))
                    if ix * iy > KASANARI * min(b[3] * b[4], o[3] * o[4]): kas = True
                out.append(dict(m, text=b[0], box=[round(v, 4) for v in b[1:5]], conf=round(b[5], 2), h=round(b[4] * 1080, 1), kasanari=kas))
        koma.append({'t': t, 'n': len(out), 'r': out})
    subprocess.run(['rm', '-rf', d])
    return {'動画': mp4, '頭の秒': [t0, t1], 'fps': fps, 'koma': koma}

# 線（手本15本で決める・SEN_PATH があればそれを使う）
SEN0 = {'c_aka': AKA, 'c_makka': MAKKA, 'hue_d': 35, 'hue_c': 2.5, 'hue_sat': 0.35, 'small_px': SMALL_PX, 'telop_h': 30, 'sharp': 0, 'mitsu_n': 12, 'motsu': MOTSU}
SEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zettai', 'miyasusa-sen.json')
def sen_yomu():
    s = dict(SEN0)
    if os.path.exists(SEN_PATH): s.update(json.load(open(SEN_PATH)).get('sen', {}))
    return s

def hantei(raw, sen):
    fps = raw['fps']; de = []; akai = {}
    for kq in raw['koma']:
        t = kq['t']; seen = set(); mitsu = kq['n'] >= sen['mitsu_n']   # 字の箱が多いコマ＝画面の録画・表（中の小さい字は見せ物・テロップとは別に数える）
        for o in kq['r']:
            key = None
            for k, e in akai.items():
                if k in seen: continue
                if (norm(o['text']) == e['norm'] or (len(o['text']) > 3 and norm(o['text'])[:4] == e['norm'][:4])) and abs(o['box'][0] - e['box'][0]) < 0.05 and abs(o['box'][1] - e['box'][1]) < 0.05 and t - e['t1'] <= 1.5 / fps:
                    key = k; break
            if key is None:
                key = len(de); e = {'norm': norm(o['text']), 'text': o['text'], 'box': o['box'], 't0': t, 't1': t, 'koma': []}; de.append(e); akai[key] = e
            e = akai[key]; e['t1'] = t; e['box'] = o['box']; e['koma'].append(dict(o, t=t, mitsu=mitsu)); seen.add(key)
        for k in [k for k, e in akai.items() if t - e['t1'] > 1.5 / fps]: del akai[k]
    ichiran = []
    for e in de:
        K = e['koma']
        def tsuzuku(f):
            best = cur = 0; prev = None
            for q in K:
                if f(q): cur = cur + 1 if prev is not None and q['t'] - prev <= 1.5 / fps else 1; prev = q['t']; best = max(best, cur)
                else: cur = 0; prev = None
            return best / fps
        telop = lambda q: q['h'] >= sen['telop_h'] and q['sharp'] >= sen['sharp'] and not q['mitsu']   # わざとぼかした字・画面の録画の中の字は外す
        naze = []
        if tsuzuku(lambda q: telop(q) and q['c'] < sen['c_makka']) >= sen['motsu']: naze.append('真っ赤：明るさの差 %.2f（%.1f未満）' % (min(q['c'] for q in K if telop(q)), sen['c_makka']))
        elif tsuzuku(lambda q: telop(q) and q['c'] < sen['c_aka']) >= sen['motsu']: naze.append('赤：明るさの差 %.2f（%.1f未満）' % (min(q['c'] for q in K if telop(q)), sen['c_aka']))
        if tsuzuku(lambda q: telop(q) and q['c'] < sen['hue_c'] and q['hue_d'] < sen['hue_d'] and q['sat_min'] >= sen['hue_sat']) >= sen['motsu']:
            naze.append('似た色：色相の差 %.0f度・明るさの差 %.2f' % (min(q['hue_d'] for q in K), min(q['c'] for q in K)))
        if tsuzuku(lambda q: not q['mitsu'] and q['h'] < sen['small_px']) >= sen['motsu']: naze.append('小さい：字の高さ %.0f 画素（%d 未満）' % (float(np.median([q['h'] for q in K])), sen['small_px']))
        if tsuzuku(lambda q: telop(q) and q['kasanari']) >= sen['motsu']: naze.append('重なり：別の字の箱と重なる')
        T = [q for q in K if telop(q)] or K
        worst = min(T, key=lambda q: q['c'])
        ichiran.append({'t0': e['t0'], 't1': e['t1'], 'text': e['text'], 'box': worst['box'], 'telop': any(telop(q) for q in K), 'c_min': worst['c'], 'c_med': round(float(np.median([q['c'] for q in T])), 2),
                        'hue_d': worst['hue_d'], 'sat_min': worst['sat_min'], 'sharp': worst['sharp'], 'h_med': round(float(np.median([q['h'] for q in K])), 1), 'naze': naze, 'worst_t': worst['t']})
    aka = [x for x in ichiran if x['naze']]
    return {'動画': raw['動画'], '頭の秒': raw['頭の秒'], 'fps': fps, 'コマ': len(raw['koma']), '字の出': len(ichiran), 'テロップの出': sum(1 for x in ichiran if x['telop']), '赤の出': len(aka),
            '内訳': {k: sum(1 for x in aka if any(s.startswith(k) for s in x['naze'])) for k in ('真っ赤', '赤', '似た色', '小さい', '重なり')},
            '線': sen, '赤の一覧': aka, '全部': ichiran}

from PIL import ImageFont
try: FONT = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 40)
except Exception: FONT = ImageFont.load_default()
def mmss(t): return '%d:%05.2f' % (int(t // 60), t % 60)

def narabe(mp4, aka, sheet):
    os.makedirs(sheet, exist_ok=True); tiles = []; d = tempfile.mkdtemp(prefix='miyasusa-s-')
    for i, x in enumerate(aka):
        f = os.path.join(d, '%04d.png' % i)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(x['worst_t']), '-i', mp4, '-frames:v', '1', '-vf', 'scale=1920:1080', f])
        if not os.path.exists(f): continue
        im = Image.open(f).convert('RGB'); dr = ImageDraw.Draw(im); bx = x['box']
        dr.rectangle([bx[0] * 1920 - 6, bx[1] * 1080 - 6, (bx[0] + bx[2]) * 1920 + 6, (bx[1] + bx[3]) * 1080 + 6], outline=(255, 0, 0), width=6)
        dr.rectangle([0, 0, 1920, 64], fill=(0, 0, 0)); dr.text((16, 8), '%s  %s' % (mmss(x['worst_t']), ' / '.join(x['naze'])), fill=(255, 255, 255), font=FONT)
        tiles.append(im.resize((640, 360)))
    for s in range(0, len(tiles), 12):
        ch = tiles[s:s + 12]; sh = Image.new('RGB', (640 * 3, 360 * ((len(ch) + 2) // 3)), (40, 40, 40))
        for i, t in enumerate(ch): sh.paste(t, ((i % 3) * 640, (i // 3) * 360))
        sh.save(os.path.join(sheet, 'miyasusa-%02d.jpg' % (s // 12)), quality=88)
    subprocess.run(['rm', '-rf', d])

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mp4'); ap.add_argument('--t0', type=float, default=0); ap.add_argument('--t1', type=float)
    ap.add_argument('--fps', type=float, default=2); ap.add_argument('--out'); ap.add_argument('--sheet'); ap.add_argument('--mon', action='store_true')
    ap.add_argument('--raw', help='測りの控え（あれば読み直さずに判定だけ・無ければ作る）')
    a = ap.parse_args()
    if a.raw and os.path.exists(a.raw): raw = json.load(open(a.raw))
    else:
        raw = yomu_raw(a.mp4, a.t0, a.t1, a.fps)
        if a.raw: json.dump(raw, open(a.raw, 'w'), ensure_ascii=False)
    r = hantei(raw, sen_yomu())
    if a.out: json.dump(r, open(a.out, 'w'), ensure_ascii=False, indent=1)
    if a.sheet and r['赤の一覧']: narabe(a.mp4, r['赤の一覧'], a.sheet)
    print('見やすさ：字の出 %d（テロップ %d）・赤の出 %d %s' % (r['字の出'], r['テロップの出'], r['赤の出'], json.dumps(r['内訳'], ensure_ascii=False)))
    for x in r['赤の一覧']: print('  %s〜%s  %s  「%s」 c=%.2f 色相差=%.0f h=%.0f くっきり=%.0f' % (mmss(x['t0']), mmss(x['t1']), ' / '.join(x['naze']), x['text'][:30], x['c_min'], x['hue_d'], x['h_med'], x['sharp']))
    if a.mon:   # 門：字1つの止まり（真っ赤・似た色）は0件、率（小さい・重なり・差3未満）は手本15本の最大まで（zettai/miyasusa-sen.json）
        SJ = json.load(open(SEN_PATH)) if os.path.exists(SEN_PATH) else {'ritsu': {}, 'keikoku': {}}
        mn = r['コマ'] / r['fps'] / 60; T = [x for x in r['全部'] if x['telop']]
        lo = sum(1 for x in T if x['c_min'] < 3) / max(1, len(T))
        ng = []
        if r['内訳']['真っ赤']: ng.append('明るさの差が無い字 %d' % r['内訳']['真っ赤'])
        if r['内訳']['似た色']: ng.append('似た色の字 %d' % r['内訳']['似た色'])
        for k, v in (('小さい/分', r['内訳']['小さい'] / mn), ('重なり/分', r['内訳']['重なり'] / mn), ('差3未満の割合', lo)):
            if k in SJ['ritsu'] and v > SJ['ritsu'][k]: ng.append('%s %.3f ＞ 手本の最大 %s' % (k, v, SJ['ritsu'][k]))
        if lo > SJ['keikoku'].get('差3未満の割合', 9): print('🟡 警告：明るさの差3未満の割合 %.3f ＞ 手本の中央値 %s' % (lo, SJ['keikoku']['差3未満の割合']))
        print('見やすさの門：' + ('合格' if not ng else '不合格（' + '・'.join(ng) + '）') + '（小さい/分 %.2f・重なり/分 %.2f・差3未満 %.3f）' % (r['内訳']['小さい'] / mn, r['内訳']['重なり'] / mn, lo))
        sys.exit(1 if ng else 0)
