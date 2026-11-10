#!/usr/bin/env python3
# 見本の効果音が、素材サイト（効果音ラボ）のどの音と同じ（または近い）かを調べる。
#   python3 build/sfx_match.py <声を抜いた音 bg.wav> <開始秒> <終わり秒> <出力.json> [--t 秒,秒,...]
# やり方: bg.wav の立ち上がり（効果音の候補）ごとに 0.8 秒を切り出し、ライブラリ全部と
#   ① 波形の正規化相互相関（同じ音ならほぼ 0.8 以上）② 音色（帯域の形）の近さ を測り、上位を出す。
import sys, os, json, glob, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
SR = 22050

def load(p, sr_to=SR):
    w = wave.open(p); sr = w.getframerate(); ch = w.getnchannels(); n = w.getnframes()
    a = np.frombuffer(w.readframes(n), np.int16).reshape(-1, ch).astype(np.float32).mean(1) / 32768
    if sr != sr_to:
        x = np.arange(0, len(a), sr / sr_to); a = np.interp(x, np.arange(len(a)), a)
    return a.astype(np.float32)

def bands(x):
    n = 2048; fr = np.fft.rfftfreq(n, 1 / SR); edges = np.geomspace(80, 10000, 33)
    seg = x[:n * 8] if len(x) >= n else np.pad(x, (0, n - len(x)))
    frames = [seg[i:i + n] * np.hanning(n) for i in range(0, max(1, len(seg) - n + 1), n // 2)][:12]
    S = np.array([np.abs(np.fft.rfft(f)) ** 2 for f in frames]).mean(0)
    v = np.array([S[(fr >= edges[j]) & (fr < edges[j + 1])].sum() for j in range(32)])
    v = np.log10(v + 1e-10); return (v - v.mean()) / (v.std() + 1e-9)

def ncc_max(q, r):
    # q（短い見本）を r（ライブラリの頭 1.5 秒）に対してずらし、最大の正規化相関
    L = len(q); r = r[:int(SR * 1.5) + L]
    if len(r) < L: r = np.pad(r, (0, L - len(r)))
    nfft = 1 << int(np.ceil(np.log2(len(r) + L)))
    c = np.fft.irfft(np.fft.rfft(r, nfft) * np.conj(np.fft.rfft(q, nfft)), nfft)[:len(r) - L + 1]
    en = np.convolve(r ** 2, np.ones(L), 'valid'); en = np.maximum(en, 0.05 * en.max() + 1e-9)  # 無音の所で割り算が暴れないように
    e = np.sqrt(en) * np.sqrt((q ** 2).sum()) + 1e-9
    return float((c / e).max())

def load_lib():
    cache = os.path.join(BASE, 'assets', 'sfxlib_cache.npz')
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True); return {n: (x, b) for n, x, b in zip(z['names'], z['xs'], z['bs'])}
    lib = {}
    for p in sorted(glob.glob(os.path.join(BASE, 'assets', 'sfxlib_wav', '*.wav'))):
        x = load(p)[:int(SR * 2.5)]; lib[os.path.basename(p)[:-4]] = (x, bands(x))
    names = list(lib); xs = np.empty(len(names), object); bs = np.empty(len(names), object)
    for i, n in enumerate(names): xs[i], bs[i] = lib[n]
    np.savez(cache, names=np.array(names), xs=xs, bs=bs); return lib

def main():
    src, t0, t1, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    a = load(src)
    if '--t' in sys.argv:
        ts = [float(x) for x in sys.argv[sys.argv.index('--t') + 1].split(',')]
    else:
        sys.path.insert(0, HERE); import kata_extract as K
        w = wave.open(src); sr = w.getframerate(); ch = w.getnchannels()
        full = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch).astype(np.float32).mean(1) / 32768
        seg = full[int(t0 * sr):int(t1 * sr)]
        pk, _, _ = K.onsets(seg, sr)
        ts = [p['t'] + t0 for p in pk if p['over_local_db'] >= 8 and not (p['on_beat'] and p['over_local_db'] < 12)]
    lib = load_lib()
    names = list(lib); L = int(SR * 0.6); NR = int(SR * 1.5) + L; NF = 1 << int(np.ceil(np.log2(NR + L)))
    Rm = np.zeros((len(names), NR), np.float32)
    for k, n in enumerate(names):
        x = lib[n][0][:NR]; Rm[k, :len(x)] = x
    RF = np.fft.rfft(Rm, NF, axis=1).astype(np.complex64)
    cs = np.cumsum(np.pad(Rm.astype(np.float64) ** 2, ((0, 0), (1, 0))), axis=1)
    EN = cs[:, L:] - cs[:, :-L]; EN = np.maximum(EN, 0.05 * EN.max(axis=1, keepdims=True) + 1e-9)
    XB = np.array([lib[n][1] for n in names])
    res = []
    for t in ts:
        i = int((t - 0.03) * SR); q = a[i:i + L]
        if len(q) < L or np.abs(q).max() < 1e-3: continue
        qb = bands(q)
        c = np.fft.irfft(RF * np.conj(np.fft.rfft(q, NF))[None, :], NF, axis=1)[:, :NR - L + 1]
        ncc = (c / (np.sqrt(EN) * np.sqrt((q ** 2).sum()) + 1e-9)).max(axis=1)
        tim = XB @ qb / 32
        sc = sorted(zip(ncc.tolist(), tim.tolist(), names), reverse=True)
        res.append({'t': round(t, 2), 'top': [{'name': n, 'ncc': round(c, 3), 'timbre': round(b, 3)} for c, b, n in sc[:5]]})
        print(round(t, 2), ' | '.join('%s %.2f/%.2f' % (n, c, b) for c, b, n in sc[:3]), flush=True)
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
