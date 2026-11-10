#!/usr/bin/env python3
# ナレーションの下ごしらえ：台本を読む → 強制アライメント（字ごとの時刻）→ ジャンプカット（無音を見本の長さに詰める）→ 声の立ち上がりに時刻を吸着
#   出力 work/vocals.wav（詰めた声）・work/timing.json（台本の字ごとの話し始め・行の情報）
#   無音の決まり（見本 60本の実測 kijun.json の pause）：
#     ・行の切れ目（台本の1行＝1つの言い切り）… 見本の無音の中央〜90%（既定 0.14 秒）
#     ・行の中の読点・息継ぎ … 0.05 秒（見本は 0.08 秒より短い無音が大半＝話し続けている）
#     ・台本に【間】と書いた所 … 0.6 秒（強調の前だけ。見本も山場の前だけ間を残す）
import os, re, json, subprocess, wave, numpy as np
import paths
SR = 48000
N = lambda s: re.sub(r'[、。「」『』！？!?,.\s・…（）()【】]', '', s.replace('【間】', ''))

def read_script(p):
    """script.md（| # | 区間 | 台本 | 訴求 | の表）か script.txt（1行1文・行頭に [区間] を書ける）"""
    L = []
    for raw in open(p, encoding='utf-8'):
        s = raw.rstrip('\n')
        m = re.match(r'\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|', s)
        if m:
            L.append({'n': int(m.group(1)), 'sec': m.group(2).strip(), 'text': m.group(3).strip(), 'intent': m.group(4).strip()}); continue
        if p.endswith('.txt') and s.strip() and not s.startswith('#'):
            m2 = re.match(r'\[([^\]]+)\]\s*(.*)', s.strip()); sec, t = (m2.group(1), m2.group(2)) if m2 else ((L[-1]['sec'] if L else '本編'), s.strip())
            L.append({'n': len(L) + 1, 'sec': sec, 'text': t, 'intent': ''})
    if not L: raise SystemExit('台本の行が読めません: ' + p)
    return L

def load(p, sr=SR):
    return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-threads', '4', '-i', p, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True, check=True).stdout,
                         np.float32).copy()

def save(p, y, sr=SR):
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())

def forced_align(audio, text, cache):
    if os.path.exists(cache):
        d = json.load(open(cache))
        if d.get('_text') == text: return d['characters']
    mp3 = cache + '.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-threads', '4', '-y', '-i', audio, '-ac', '1', '-ar', '44100', '-b:a', '128k', mp3], check=True)
    for i in range(3):
        out = subprocess.run(['curl', '-s', '-X', 'POST', 'https://api.elevenlabs.io/v1/forced-alignment', '-H', 'xi-api-key: ' + paths.env('ELEVENLABS_API_KEY'),
                              '-F', 'file=@' + mp3, '-F', 'text=' + text], capture_output=True, text=True).stdout
        try:
            d = json.loads(out); d['_text'] = text; json.dump(d, open(cache, 'w'), ensure_ascii=False); os.remove(mp3); return d['characters']
        except Exception:
            if i == 2: raise SystemExit('強制アライメントが失敗: ' + out[:300])

def env_db(y, sr=SR, hop=0.005, win=0.02):
    h, w = int(sr * hop), int(sr * win); n = max(0, (len(y) - w) // h)
    return 20 * np.log10(np.sqrt((y[np.arange(n)[:, None] * h + np.arange(w)[None]] ** 2).mean(1)) + 1e-9)

def silences(y, sr=SR, mn=0.04):
    db = env_db(y, sr); v = db > (np.percentile(db, 95) - 30); out = []; j = 0
    while j < len(v):
        if not v[j]:
            k = j
            while k < len(v) and not v[k]: k += 1
            if (k - j) * 0.005 >= mn and j > 0 and k < len(v): out.append((j * 0.005, k * 0.005))
            j = k
        else: j += 1
    return out

def onsets(y, sr=SR, after_silence_only=False):
    db = env_db(y, sr); v = db > (np.percentile(db, 95) - 30); on = []
    for j in range(12, len(db) - 4):
        if v[j] and not v[j - 20:j].any(): on.append(j * 0.005)
        elif after_silence_only: continue
        elif v[j] and db[j] - db[j - 4] > 6 and db[j] >= db[j + 1] - 1: on.append(j * 0.005)
    return np.array(sorted(set(on)))

def prep(proj, kijun, keep_line=None, keep_inner=0.05, keep_ma=0.6, lead=0.25, tail=0.6):
    W = os.path.join(proj, 'work'); os.makedirs(W, exist_ok=True)
    inp = [os.path.join(proj, 'input', f) for f in sorted(os.listdir(os.path.join(proj, 'input'))) if f.startswith('narration')][0]
    sp = [os.path.join(proj, 'input', f) for f in ('script.md', 'script.txt') if os.path.exists(os.path.join(proj, 'input', f))][0]
    L = read_script(sp)
    pz = kijun['pause']
    keep_line = keep_line or pz['line_keep']
    y = load(inp)
    text = ' '.join(x['text'].replace('【間】', '') for x in L)
    ch = forced_align(inp, text, os.path.join(W, 'fa_raw.json'))
    FA = [(c['text'], c['start'], c['end']) for c in ch if N(c['text'])]
    REF = ''; LINE0 = {}; MA = set()
    for x in L:
        LINE0[x['n']] = len(REF)
        parts = x['text'].split('【間】')
        for k, prt in enumerate(parts):
            REF += N(prt)
            if k < len(parts) - 1: MA.add(len(REF) - 1)     # この字の後ろに【間】
    assert REF == ''.join(c for c, _, _ in FA), '強制アライメントの字と台本が一致しません'
    line_end = {LINE0[n] - 1 for n in LINE0 if LINE0[n] > 0}
    # 無音ごとに「何の後ろか」を決めて長さを決める
    ends = np.array([e for _, _, e in FA])
    cuts = []   # (始め, 終わり, 残す長さ)
    for a, b in silences(y):
        i = int(np.searchsorted(ends, a + 0.06)) - 1   # この無音の直前に終わった字
        if i in MA: keep = keep_ma
        elif i in line_end: keep = keep_line
        else: keep = keep_inner
        if b - a > keep + 0.01: cuts.append((a, b, keep))
    # 頭と終わり
    first = FA[0][1]; out = []; tmap = []; pos = max(0.0, first - lead); src0 = pos; acc = 0.0
    segs = []; cur = pos
    for a, b, keep in cuts:
        if b <= cur: continue
        segs.append((cur, a + keep / 2)); cur = b - keep / 2
    segs.append((cur, min(len(y) / SR, FA[-1][2] + tail)))
    xf = int(0.005 * SR); res = []; T0 = 0.0
    for a, b in segs:
        s = y[int(a * SR):int(b * SR)].copy()
        if len(s) > 2 * xf: s[:xf] *= np.linspace(0, 1, xf); s[-xf:] *= np.linspace(1, 0, xf)
        res.append(s); tmap.append((a, b, T0)); T0 += len(s) / SR
    v = np.concatenate(res); save(os.path.join(W, 'vocals.wav'), v)
    def M(t):
        for a, b, o in tmap:
            if a <= t <= b: return o + (t - a)
        for a, b, o in tmap:
            if t < a: return o
        return T0
    # 立ち上がりに吸着（FA の遅れは行頭の実測から決める）
    on = onsets(v); on_s = onsets(v, after_silence_only=True)
    starts = [M(s) for _, s, _ in FA]
    lb = []
    for n, i in LINE0.items():
        k = np.searchsorted(on_s, starts[i]); c = [on_s[j] for j in (k - 1, k) if 0 <= j < len(on_s) and abs(on_s[j] - starts[i]) <= 0.3]
        if c: lb.append(starts[i] - min(c, key=lambda u: abs(u - starts[i])))
    bias = float(np.median(lb)) if lb else 0.1
    def snap(t, win=0.08):
        k = np.searchsorted(on, t); c = [on[j] for j in (k - 1, k) if 0 <= j < len(on) and abs(on[j] - t) <= win]
        return float(min(c, key=lambda u: abs(u - t))) if c else float(t)
    T = [max(0.0, snap(s - bias)) for s in starts]
    for n, i in LINE0.items():
        k = np.searchsorted(on_s, starts[i] - bias); c = [on_s[j] for j in (k - 1, k) if 0 <= j < len(on_s) and abs(on_s[j] - (starts[i] - bias)) <= 0.15]
        if c: T[i] = float(min(c, key=lambda u: abs(u - (starts[i] - bias))))
    E = [M(e) - bias for _, _, e in FA]
    for x in L: x['start'] = round(T[LINE0[x['n']]], 3)
    J = {'lines': L, 'ref': REF, 'line0': LINE0, 'starts': [round(t, 3) for t in T], 'ends': [round(t, 3) for t in E], 'fa_bias': round(bias, 3),
         'duration': round(len(v) / SR, 3), 'cuts': len(cuts), 'source': inp, 'script': sp}
    json.dump(J, open(os.path.join(W, 'timing.json'), 'w'), ensure_ascii=False)
    return J
