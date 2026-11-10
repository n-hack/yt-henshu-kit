#!/usr/bin/env python3
# 見本のBGMを書き出す：曲ごとに、効果音の無い4秒の塊が続く「きれいな区間」を動画の中から探し、長い順に取る。
# 足りなければ別の動画の同じ曲から「前の区間の終わりと音が一致する所」を探してつなぐ（0.4秒の重ね）→ sozai/bgm/<役割>.wav・index.tsv
import json, os, wave, numpy as np
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/bgm_blocks.npz'), allow_pickle=True); M = json.loads(str(Z['meta']))
SG = json.load(open(os.path.join(BASE, 'sozai/work/bgm_songs.json')))
SR = 44100
ROLE = {  # 役割: (曲番号, 説明, 目標の長さ秒)
    'kokuchi':      (0, '重大告知・勉強会の告知（暗い紺・赤の地）。告知と締めで使う', 120),
    'kokuchi_b':    (5, '告知「無料でプレゼントを配布」の暗い地', 90),
    'kokuchi_date': (11, '告知の日付・限定（暗い地）', 60),
    'opening':      (14, '映画風の冒頭・告知（暗い地・炎）', 60),
    'shime':        (12, '締めの暗い地「正直一つ言わせてほしいのが」', 60),
    'honpen_gray':  (13, '本編（youtube.tehon の薄い灰の地）', 120),
    'honpen_gray_b':(9, '本編（youtube.tehon の薄い灰の地）その2', 120),
    'honpen_cream': (6, '本編（sns.tehon・instagram_tehon のクリーム／灰の地）', 120),
    'honpen_insta': (7, '本編（instagram_tehon・youtube.tehon）', 120),
    'endcard':      (3, '最後の「ご視聴ありがとうございました」の画面', 30),
}
def rd(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
def chroma(y, hop=2205):
    n = 4096; fr = np.fft.rfftfreq(n, 1 / SR); ok = (fr > 80) & (fr < 4000); pc = np.round(69 + 12 * np.log2(fr[ok] / 440)).astype(int) % 12
    fs = np.lib.stride_tricks.sliding_window_view(np.pad(y, (0, n)), n)[::hop] * np.hanning(n)
    S = np.abs(np.fft.rfft(fs, axis=1)) ** 2
    C = np.stack([S[:, ok][:, pc == k].sum(1) for k in range(12)], 1); C = np.log1p(C * 1e3)
    E = np.log10(S.sum(1) + 1e-12)[:, None]
    X = np.concatenate([C, E], 1); X = X - X.mean(1, keepdims=True); return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
def runs(song):
    by = {}
    for i in SG[song]['members']: by.setdefault((M[i]['vid'], M[i]['win']), []).append(i)
    out = []
    for (vid, win), ms in by.items():
        ms.sort(key=lambda i: M[i]['a']); cur = []
        for i in ms:
            if M[i]['on'] == 0 and (not cur or abs(M[i]['a'] - M[cur[-1]]['a'] - 4) < 0.1): cur.append(i)
            else:
                if len(cur) >= 2: out.append(cur)
                cur = [i] if M[i]['on'] == 0 else []
        if len(cur) >= 2: out.append(cur)
    # 声が小さい区間を優先（声を抜いた跡が少ない）
    out.sort(key=lambda r: -(len(r) * 4 - 0.15 * max(0, np.mean([M[i]['voice'] for i in r]) + 40)))
    return out
def cut(r):
    m0 = M[r[0]]; a = m0['a'] + 0.2; b = M[r[-1]]['a'] + 4 - 0.2
    bg = rd(os.path.join(BASE, 'kata/raw', m0['vid'], 'w' + m0['win'], 'bg.wav'))
    return bg[int(a * SR):int(b * SR)].copy(), (m0['vid'], m0['ch'], round(m0['t'] + 0.2, 1), round(b - a, 1))
def splice(A, B):
    # A の最後3秒と同じ所を B の中から探す
    ca = chroma(A[-3 * SR:]); cb = chroma(B); L = len(ca); best = (-1, 0)
    for k in range(0, len(cb) - L - 20):
        s = float((cb[k:k + L] * ca).sum() / L)
        if s > best[0]: best = (s, k)
    s, k = best
    j = (k + L) * 2205; x = int(0.4 * SR)
    if s < 0.80 or j + x >= len(B): return None, s
    w = np.linspace(0, 1, x)
    return np.concatenate([A[:-x], A[-x:] * (1 - w) + B[j:j + x] * w, B[j + x:]]), s
os.makedirs(os.path.join(BASE, 'sozai/bgm'), exist_ok=True)
rows = ['役割\tファイル\t説明\t長さ秒\tつないだ数\t出どころ（動画・チャンネル・秒・長さ）\tつなぎ目の一致度']
for role, (song, desc, goal) in ROLE.items():
    rs = runs(song)
    if not rs: print(role, 'きれいな区間なし'); continue
    y, src = cut(rs[0]); srcs = [src]; sims = []
    for r in rs[1:]:
        if len(y) >= goal * SR: break
        B, src = cut(r)
        z, s = splice(y, B)
        if z is not None and len(z) > len(y) + 2 * SR: y = z; srcs.append(src); sims.append(round(s, 2))
    pk = np.abs(y).max(); y = y / (pk + 1e-9) * 0.7
    f = int(1.5 * SR); y[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR)); y[-f:] *= np.linspace(1, 0, f)
    p = os.path.join(BASE, 'sozai/bgm', role + '.wav')
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
    rows.append('\t'.join([role, role + '.wav', desc + '（曲#%d・%d本で使用）' % (song, SG[song]['videos']), '%.1f' % (len(y) / SR), str(len(srcs)),
                           ' / '.join('%s %s %.1f秒〜%.1f秒' % (v, c, t, l) for v, c, t, l in srcs), ','.join(map(str, sims))]))
    print(rows[-1])
open(os.path.join(BASE, 'sozai/bgm/index.tsv'), 'w').write('\n'.join(rows) + '\n')
