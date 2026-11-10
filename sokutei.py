#!/usr/bin/env python3
# 元動画を自分で測る部品（作業AI・2026-10-15）
#   saboranai.py（手抜きの門）と kanpi.py（完コピ練習の比べ）が同じ測り方を使うためのもの。
#   作業者の申告や作業者の道具は使わない。ここで元動画から独立に数える。
import os, re, json, subprocess, hashlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OCR_BIN = os.path.join(HERE, 'ocr')

# ---- 測り方の決まり（数字を変えたら README と saboranai の報告にも出る） ----
DIFF_W, DIFF_H = 480, 270      # 1コマずつの差は 480x270 の輝度で比べる（area 縮小・文字1つ＝約10x10画素）
VIS_PIX = 8                    # 「目に見える差」＝ 輝度の差が 8 より大きい画素
VIS_MIN_PX = 5                 # そういう画素が 5 個以上あれば「変化のあるコマ」（1920x1080 で約 80画素分）
CUT_FRAC = 0.30                # 画面の 30% 以上の画素が 24 より大きく変わったら「場面転換（カット）」
CUT_PIX = 24
CUT_GAP_FRAMES = 6             # カットは 6コマ（約0.2秒）以内に続いたら 1回と数える（フェード・フラッシュ）
DE_HIT = 12.0                  # 色差（CIE76 ΔE）が 12 以内の画素があれば「その色が画面にある」
DE_MIN_PX = 12                 # 480x270 のうち 12 画素以上（文字の細い線でも拾える数）
THRESHOLDS = dict(DIFF_W=DIFF_W, DIFF_H=DIFF_H, VIS_PIX=VIS_PIX, VIS_MIN_PX=VIS_MIN_PX, CUT_FRAC=CUT_FRAC, CUT_PIX=CUT_PIX,
                  CUT_GAP_FRAMES=CUT_GAP_FRAMES, DE_HIT=DE_HIT, DE_MIN_PX=DE_MIN_PX)


def probe(mp4):
    """ffprobe で fps・長さ・実フレーム数（パケットを全部数える）"""
    o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                        'stream=r_frame_rate,avg_frame_rate,nb_read_packets,nb_frames:format=duration', '-of', 'json', mp4],
                       capture_output=True, text=True).stdout
    d = json.loads(o or '{}'); s = (d.get('streams') or [{}])[0]
    num, den = (s.get('avg_frame_rate') or s.get('r_frame_rate') or '30/1').split('/')
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    return {'fps': fps, 'duration': float(d.get('format', {}).get('duration') or 0),
            'packets': int(s.get('nb_read_packets') or 0), 'nb_frames_header': int(s.get('nb_frames') or 0)}


def framediff(mp4, cache=None, t0=None, dur=None):
    """全コマ（元の fps・間引かない）で前のコマとの差を数える。cache(.npz) があれば使う。
    返すもの：same（画素が完全に同じ）・vis（目に見える差の画素数）・cutfrac（大きく変わった画素の割合）・n（デコードしたコマ数）"""
    if cache and os.path.exists(cache):
        z = np.load(cache)
        return {k: z[k] for k in z.files}
    W, H = DIFF_W, DIFF_H; fs = W * H
    cut = (['-ss', '%.3f' % t0] if t0 is not None else []) + ['-i', mp4] + (['-t', '%.3f' % dur] if dur is not None else [])
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-hwaccel', 'videotoolbox'] + cut + ['-map', '0:v:0', '-fps_mode', 'passthrough',
                          '-vf', f'scale={W}:{H}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         stdout=subprocess.PIPE, bufsize=fs * 8)
    prev = None; same, vis, cutf = [], [], []
    while True:
        b = p.stdout.read(fs)
        if len(b) < fs: break
        a = np.frombuffer(b, np.uint8).reshape(H, W).astype(np.int16)
        if prev is None:
            same.append(False); vis.append(fs); cutf.append(1.0)
        else:
            d = np.abs(a - prev)
            same.append(not d.any()); vis.append(int((d > VIS_PIX).sum())); cutf.append(float((d > CUT_PIX).mean()))
        prev = a
    p.wait()
    r = {'same': np.array(same, bool), 'vis': np.array(vis, np.int32), 'cutfrac': np.array(cutf, np.float32), 'n': np.array(len(same))}
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez_compressed(cache, **r)
    return r


# ---- 追記3 の見方（32x32区画の最大差）。framediff とは別の控え（THRESHOLDS を変えずに足した） ----
BLK_PX = 32                    # 1920 幅に換算して 32x32 の区画
YURAGI_MAX = 12                # 区画の最大差が 12段以下しか無いコマ＝「ゆらぎのみ」
RUN_ALL_MAX = 60               # 動きの続き（ラン）が 60コマ以下なら全コマを見る
RUN_HEAD = RUN_TAIL = 10       # 61コマ以上は頭10・終わり10を全部
RUN_STEP = 5                   # 間は 5コマおき
BLK_TH = dict(BLK_PX=BLK_PX, YURAGI_MAX=YURAGI_MAX, RUN_ALL_MAX=RUN_ALL_MAX, RUN_HEAD=RUN_HEAD, RUN_TAIL=RUN_TAIL, RUN_STEP=RUN_STEP)


def blockdiff(mp4, cache=None):
    """全コマ（元の fps・元の大きさ）で前のコマとの差を 32x32 区画ごとの最大差で。
    返すもの：same（完全一致）・bmax（区画の最大差の最大）・nb（12段を超えた区画の数）・NB（区画の総数）・n"""
    if cache and os.path.exists(cache):
        z = np.load(cache)
        if json.loads(str(z['th'])) == BLK_TH:
            return {k: z[k] for k in z.files}
    o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', mp4],
                       capture_output=True, text=True).stdout
    s = json.loads(o)['streams'][0]; W, H = int(s['width']), int(s['height'])
    B = max(8, round(BLK_PX * W / 1920))
    Hp, Wp = -(-H // B) * B, -(-W // B) * B; NB = (Hp // B) * (Wp // B); fs = W * H
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-hwaccel', 'videotoolbox', '-i', mp4, '-map', '0:v:0', '-fps_mode', 'passthrough',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE, bufsize=fs * 8)
    try:
        import cv2
        absdiff = lambda x, y, out: cv2.absdiff(x, y, dst=out)
    except ImportError:
        absdiff = lambda x, y, out: np.subtract(np.maximum(x, y), np.minimum(x, y), out=out)
    pad = np.zeros((Hp, Wp), np.uint8)
    prev = None; same, bmax, nb = [], [], []
    while True:
        b = p.stdout.read(fs)
        if len(b) < fs: break
        a = np.frombuffer(b, np.uint8).reshape(H, W)
        if prev is None:
            same.append(False); bmax.append(255); nb.append(NB)
        else:
            absdiff(a, prev, pad[:H, :W])
            m = pad.reshape(Hp // B, B, Wp).max(axis=1).reshape(Hp // B, Wp // B, B).max(axis=2)
            mx = int(m.max())
            same.append(mx == 0); bmax.append(mx); nb.append(int((m > YURAGI_MAX).sum()))
        prev = a
    p.wait()
    r = {'same': np.array(same, bool), 'bmax': np.array(bmax, np.int16), 'nb': np.array(nb, np.int32), 'NB': np.array(NB),
         'n': np.array(len(same)), 'th': np.array(json.dumps(BLK_TH, sort_keys=True))}
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        np.savez_compressed(cache, **r)
    return r


def must_see(bd, cutfrac=None):
    """追記3 の「見るべきコマ」を独立に選ぶ。返すもの：must（見るべきコマの番号）・数の内訳"""
    nb = bd['nb']; NB = int(bd['NB']); T = len(nb); mv = nb > 0
    runs = []; i = 0
    while i < T:
        if mv[i]:
            j = i
            while j + 1 < T and mv[j + 1]: j += 1
            runs.append((i, j)); i = j + 1
        else:
            i += 1
    must = {0}; mid_all = mid_grid = jumps = 0
    for a, b in runs:
        L = b - a + 1
        if L <= RUN_ALL_MAX:
            must.update(range(a, b + 1))
        else:
            ma, mb = a + RUN_HEAD, b - RUN_TAIL          # 間 = [ma, mb]
            must.update(range(a, ma)); must.update(range(mb + 1, b + 1))
            grid = set(range(ma, mb + 1, RUN_STEP))
            jp = set()
            for f in range(ma, mb + 1):
                # 差が跳ねたコマ：画面の35%以上が動いた・動いた区画が前後で2.5倍以上変わった・カット
                if nb[f] >= 0.35 * NB or nb[f] > 2.5 * max(nb[f - 1], 4) or nb[f - 1] > 2.5 * max(nb[f], 4) \
                        or (cutfrac is not None and f < len(cutfrac) and cutfrac[f] >= CUT_FRAC):
                    jp.add(f)
            must.update(grid | jp)
            mid_all += mb - ma + 1; mid_grid += len(grid); jumps += len(jp - grid)
        if b + 1 < T: must.add(b + 1)                      # 動きが止まった直後
    same = bd['same']
    return {'must': np.array(sorted(must), np.int64), 'n_must': len(must), 'identical': int(same.sum()),
            'yuragi': int((~same & ~mv).sum()), 'moving': int(mv.sum()), 'runs': len(runs),
            'runs_over60': sum(1 for a, b in runs if b - a + 1 > RUN_ALL_MAX),
            'run_mid_all': mid_all, 'run_mid_offgrid': mid_all - mid_grid, 'run_mid_unseen_ok': mid_all - mid_grid - jumps, 'jumps': jumps}


def cuts_from_diff(fd, fps):
    """場面転換の秒（CUT_FRAC 以上・CUT_GAP_FRAMES 以内は1回）"""
    idx = np.flatnonzero(fd['cutfrac'] >= CUT_FRAC)
    idx = idx[idx > 0]
    out = []
    for i in idx:
        if not out or i - out[-1] > CUT_GAP_FRAMES:
            out.append(int(i))
    return [i / fps for i in out]


def changes_from_diff(fd, fps):
    """要素の出入りも含む「変化の始まり」の秒（静か→動いた の立ち上がり）"""
    v = fd['vis'] >= VIS_MIN_PX
    st = np.flatnonzero(v[1:] & ~v[:-1]) + 1
    return [i / fps for i in st]


def grab(mp4, t, w=480, h=270):
    """t 秒のコマを RGB で（w x h）"""
    b = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % max(0, t), '-i', mp4, '-frames:v', '1', '-vf', f'scale={w}:{h}',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    if len(b) < w * h * 3: return None
    return np.frombuffer(b[:w * h * 3], np.uint8).reshape(h, w, 3)


def grab_png(mp4, t, out, w=1920, h=1080):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '%.3f' % max(0, t), '-i', mp4, '-frames:v', '1', '-vf', f'scale={w}:{h}', out])
    return os.path.exists(out)


def rgb2lab(a):
    a = a.astype(np.float32) / 255.0
    a = np.where(a > 0.04045, ((a + 0.055) / 1.055) ** 2.4, a / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]], np.float32)
    xyz = a @ M.T / np.array([0.95047, 1.0, 1.08883], np.float32)
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


HEX_RE = re.compile(r'#([0-9a-fA-F]{6})(?![0-9a-fA-F])')


def hexes(s):
    return ['#' + h.lower() for h in HEX_RE.findall(s or '')]


def color_presence(frames_lab, hx):
    """その色に ΔE<=DE_HIT の画素が、どれかのコマに DE_MIN_PX 以上あるか → (ある?, いちばん近いΔE)"""
    c = rgb2lab(np.array([[int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)]], np.uint8))[0]
    best = 1e9; hit = False
    for L in frames_lab:
        de = np.sqrt(((L - c) ** 2).sum(-1))
        best = min(best, float(de.min()))
        if int((de <= DE_HIT).sum()) >= DE_MIN_PX: hit = True
    return hit, best


def ocr(paths):
    """macOS Vision で文字を読む → {path: [文字列,...]}"""
    if not paths: return {}
    o = subprocess.run([OCR_BIN] + list(paths), capture_output=True, text=True).stdout
    r = {}
    for line in o.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        r[d['p']] = [x[0] for x in (d.get('r') or [])]
    return r


KEEP_RE = re.compile(r'[0-9A-Za-z぀-ヿ㐀-鿿０-９Ａ-ｚ]')


def norm_chars(s):
    import unicodedata
    s = unicodedata.normalize('NFKC', s or '')
    return [c.lower() for c in s if KEEP_RE.match(c)]


def strip_notes(s):
    """telop.shown から（注記）を除く：（上の帯）・(右下) など"""
    s = re.sub(r'[（(][^）)]{0,20}[）)]', ' ', s or '')
    return s


def text_hit(shown, ocr_texts):
    """書かれた文字のうち、画面で読めた文字の割合（多重集合で数える）"""
    from collections import Counter
    want = Counter(norm_chars(strip_notes(shown)))
    if sum(want.values()) == 0: return None
    have = Counter(norm_chars(' '.join(ocr_texts)))
    got = sum(min(n, have[c]) for c, n in want.items())
    return got / sum(want.values())


# ---- 音 ----
def audio(mp4, t0=None, dur=None, sr=16000):
    cmd = ['ffmpeg', '-v', 'error']
    if t0 is not None: cmd += ['-ss', '%.3f' % max(0, t0)]
    cmd += ['-i', mp4]
    if dur is not None: cmd += ['-t', '%.3f' % dur]
    cmd += ['-map', '0:a:0', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, np.float32)


def stft_mag(x, n=512, hop=128):
    if len(x) < n: x = np.pad(x, (0, n - len(x)))
    w = np.hanning(n).astype(np.float32)
    k = 1 + (len(x) - n) // hop
    fr = np.lib.stride_tricks.as_strided(x, (k, n), (x.strides[0] * hop, x.strides[0]))
    return np.abs(np.fft.rfft(fr * w, axis=1))


def onsets(x, sr=16000, hop=128, k=3.0):
    """スペクトルの立ち上がり（spectral flux）が局所の中央値＋k×MAD を超えた所の秒"""
    S = np.log1p(stft_mag(x, hop=hop))
    fl = np.maximum(S[1:] - S[:-1], 0).sum(1)
    fl = np.concatenate([[0], fl])
    win = int(1.0 * sr / hop)
    out = []; last = -1e9
    for i in range(1, len(fl) - 1):
        lo, hi = max(0, i - win), min(len(fl), i + win)
        seg = fl[lo:hi]; med = np.median(seg); mad = np.median(np.abs(seg - med)) + 1e-6
        if fl[i] > med + k * mad and fl[i] >= fl[i - 1] and fl[i] >= fl[i + 1]:
            t = i * hop / sr
            if t - last > 0.05:
                out.append(t); last = t
    return out


def spec_match(clip, seg, sr=16000):
    """短い音 clip が seg の中のどこかにあるか：対数スペクトルの相関の最大値と、その位置（秒）"""
    A = np.log1p(stft_mag(clip)); B = np.log1p(stft_mag(seg))
    if len(B) < len(A): return 0.0, 0.0
    A = A - A.mean(); na = np.linalg.norm(A) + 1e-9
    best, bi = -1.0, 0
    for i in range(0, len(B) - len(A) + 1):
        b = B[i:i + len(A)]; b = b - b.mean()
        c = float((A * b).sum() / (na * (np.linalg.norm(b) + 1e-9)))
        if c > best: best, bi = c, i
    return best, bi * 128 / sr


def match_events(a, b, tol):
    """2つの時刻の列を近い順に1対1で対応づける → [(a,b,b-a)], 対応しなかった a, b"""
    a = sorted(a); b = sorted(b); used = set(); pairs = []
    for x in a:
        cand = [(abs(y - x), j) for j, y in enumerate(b) if j not in used and abs(y - x) <= tol]
        if cand:
            _, j = min(cand); used.add(j); pairs.append((x, b[j], b[j] - x))
    ua = [x for x in a if x not in {p[0] for p in pairs}]
    ub = [y for j, y in enumerate(b) if j not in used]
    return pairs, ua, ub


def file_hash(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()
