#!/usr/bin/env python3
# 見本動画の「型」を取り出すための素材づくり（作業AI 2026-10-14）
#   .venv/bin/python build/kata_extract.py <id or mp4> ...     （channels/dl/*/<id>.mp4 を探す）
#   .venv/bin/python build/kata_extract.py --all                （hantei.tsv の非実写を全部）
# 出力 kata/raw/<id>/
#   overview.jpg        全体を30コマ（どの型の動画か）
#   w<窓>_sheet<k>.jpg   窓ごと：画面が変わった直後のコマ（時刻つき・20コマ/枚）
#   w<窓>_audio.png      窓ごと：声を抜いた音（BGM＋効果音）の帯域図＋画面の変化（赤）＋音の立ち上がり（水色）
#   data.json            画面の変化・音の立ち上がりと特徴・BGMの大きさ・文字起こし（言葉の時刻つき）
# 窓 = hook（0〜90秒）・mid（真ん中60秒）・end（最後45秒）
import sys, os, json, subprocess, glob, wave, time
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE)
OUT = os.path.join(BASE, 'kata', 'raw')
FONT = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'

def sh(cmd, **k): return subprocess.run(cmd, check=True, capture_output=True, **k)
def dur_of(v): return float(sh(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', v]).stdout)
def fmt(t): return '%d:%04.1f' % (t // 60, t % 60)

def windows(d):
    if d < 240: return [('all', 0.0, d)]
    return [('hook', 0.0, 90.0), ('mid', round(d * 0.5 - 30, 1), round(d * 0.5 + 30, 1)), ('end', round(d - 45, 1), round(d - 0.3, 1))]

def changes(v, t0, t1, fps=10, w=160, h=90):
    raw = sh(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', v, '-t', str(t1 - t0), '-vf', f'fps={fps},scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-']).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    ev = []; i = 0
    while i < len(d):
        if d[i] > 0.6:
            j = i
            while j + 1 < len(d) and d[j + 1] > 0.6: j += 1
            ev.append({'t': round(t0 + (i + 1) / fps, 2), 'dur': round((j - i + 1) / fps, 2), 'peak': round(float(d[i:j + 1].max()), 1), 'sum': round(float(d[i:j + 1].sum()), 1)})
            i = j + 1
        else: i += 1
    for e in ev: e['kind'] = 'scene' if e['sum'] > 25 else 'elem'
    return ev, [round(float(x), 2) for x in d]

def grab(v, ts, size=(384, 216)):
    def one(t):
        r = sh(['ffmpeg', '-v', 'error', '-ss', '%.2f' % t, '-i', v, '-frames:v', '1', '-vf', 'scale=%d:%d' % size, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
        return Image.frombytes('RGB', size, r.stdout)
    with ThreadPoolExecutor(8) as ex: return list(ex.map(one, ts))

def sheet(ims, labels, path, cols=5):
    w, h = ims[0].size; rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (w * cols, h * rows), 'black'); d = ImageDraw.Draw(S); f = ImageFont.truetype(FONT, 20)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * w, (i // cols) * h; S.paste(im, (x, y))
        tw = d.textlength(lab, font=f); d.rectangle([x, y, x + tw + 8, y + 26], fill='black'); d.text((x + 4, y + 2), lab, fill='yellow', font=f)
    S.save(path, quality=88)

def key_times(ev, t0, t1):
    ts = [t0 + 0.3]
    for e in ev:
        t = e['t'] + e['dur'] + 0.35
        if t < t1 - 0.1: ts.append(t)
    ts = sorted(ts); out = []
    for t in ts:  # 2.5秒より空いたら間を足す・0.5秒以内は1つに
        while out and t - out[-1] > 2.6: out.append(out[-1] + 2.5)
        if not out or t - out[-1] > 0.5: out.append(t)
    return out

def read_wav(p):
    w = wave.open(p); sr = w.getframerate(); n = w.getnframes(); ch = w.getnchannels(); sw = w.getsampwidth()
    dt = np.int16 if sw == 2 else np.int32
    a = np.frombuffer(w.readframes(n), dt).reshape(-1, ch).astype(np.float32).mean(1) / (32768 if sw == 2 else 2 ** 31)
    return a, sr

def rms_db(a, sr, hop=0.1):
    n = int(sr * hop); m = len(a) // n
    r = np.sqrt((a[:m * n].reshape(m, n) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(r)

def onsets(a, sr):
    hop = sr // 100; win = 2048; fr = np.fft.rfftfreq(win, 1 / sr); hann = np.hanning(win)
    frames = np.lib.stride_tricks.sliding_window_view(a, win)[::hop] * hann
    S = np.abs(np.fft.rfft(frames, axis=1))
    E = np.log1p(S * 50)
    flux = np.concatenate([[0], np.maximum(E[1:] - E[:-1], 0).sum(1)])
    k = 200; pad = np.pad(flux, k // 2, mode='edge')
    med = np.array([np.median(pad[i:i + k]) for i in range(len(flux))])
    sc = flux / (med + 1e-6)
    tot = 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-9)
    floor = float(np.percentile(tot, 20))
    pk = []
    for i in range(1, len(sc) - 1):
        if sc[i] > 3.5 and sc[i] >= sc[i - 1] and sc[i] >= sc[i + 1] and (not pk or i * 0.01 - pk[-1]['t'] > 0.15):
            seg = S[i:i + 30]; pw = (seg ** 2).sum(0) + 1e-12
            cen = float((fr * pw).sum() / pw.sum())
            low = float(pw[fr < 300].sum() / pw.sum())
            lvl = tot[i:i + 40]; peak = float(lvl[:10].max())
            dec = int(np.argmax(lvl < peak - 12)) if (lvl < peak - 12).any() else len(lvl)
            # 声を抜いた音の中で、まわり（BGM）より大きく立ち上がったものだけが効果音の候補
            loc = float(np.median(tot[max(0, i - 150):i + 150]))
            pk.append({'t': round(i * 0.01 + win / 2 / sr, 2), 'score': round(float(sc[i]), 1), 'over_floor_db': round(peak - floor, 1),
                       'over_local_db': round(peak - loc, 1), 'centroid_hz': int(cen), 'low_ratio': round(low, 2), 'decay_s': round(dec * 0.01, 2)})
    # BGMの拍（ドラム）を効果音と取り違えないよう、拍の格子を推定して印を付ける
    beat = None
    f = flux - flux.mean()
    if len(f) > 400:
        ac = np.correlate(f, f, 'full')[len(f) - 1:]; lo, hi = 30, 100  # 0.3〜1.0秒
        lag = lo + int(np.argmax(ac[lo:hi])); strength = float(ac[lag] / (ac[0] + 1e-9))
        if strength > 0.12:
            ph = max(range(lag), key=lambda q: f[q::lag].sum()); beat = {'period_s': lag / 100, 'phase_s': ph / 100, 'strength': round(strength, 2)}
    for p in pk:
        p['on_beat'] = False
        if beat:
            x = ((p['t'] - win / 2 / sr) - beat['phase_s']) / beat['period_s']
            p['on_beat'] = abs(x - round(x)) * beat['period_s'] < 0.04
    return pk, floor, beat

def sfx_guess(p):
    if p['over_local_db'] < 6 or p['over_floor_db'] < 8: return None
    if p['on_beat'] and p['over_local_db'] < 12: return None
    if p['low_ratio'] > 0.45: return 'ドン（低い衝撃）'
    if p['centroid_hz'] > 4500 and p['decay_s'] <= 0.12: return 'カチッ/ポン（短い高音）'
    if p['centroid_hz'] > 2500 and p['decay_s'] >= 0.3: return 'キラーン/シャラン（高音・余韻）'
    if p['decay_s'] >= 0.2: return 'シュッ/ヒュン（風切り・余韻）'
    return 'ポン/ピコ（短い中音）'

def novelty(a, sr, step=0.5, L=8):
    # BGMの切り替わり候補：0.5秒ごとの音色の並びの変わり目
    n = int(sr * step); m = len(a) // n
    if m < 2 * L + 2: return []
    fr = np.fft.rfftfreq(n, 1 / sr); bands = np.geomspace(60, 12000, 25)
    X = []
    for i in range(m):
        sp = np.abs(np.fft.rfft(a[i * n:(i + 1) * n] * np.hanning(n))) ** 2
        X.append([np.log10(sp[(fr >= bands[j]) & (fr < bands[j + 1])].sum() + 1e-9) for j in range(24)])
    X = np.array(X); X = (X - X.mean(0)) / (X.std(0) + 1e-6)
    nov = np.array([np.linalg.norm(X[i - L:i].mean(0) - X[i:i + L].mean(0)) if L <= i < m - L else 0 for i in range(m)])
    thr = nov.mean() + 2.2 * nov.std(); out = []
    for i in range(1, m - 1):
        if nov[i] > thr and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1] and (not out or i * step - out[-1]['t'] > 6):
            out.append({'t': round(i * step, 1), 'score': round(float(nov[i]), 2)})
    return out

def audio_strip(bg, voc, sr, t0, ev, pk, path, title):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    plt.rcParams['font.family'] = 'Hiragino Sans'
    L = len(bg) / sr
    fig, ax = plt.subplots(2, 1, figsize=(max(12, L / 3.2), 5.2), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    ax[0].specgram(bg, NFFT=2048, Fs=sr, noverlap=1536, cmap='magma', vmin=-120, vmax=-20)
    ax[0].set_ylim(0, 10000); ax[0].set_ylabel('BGM+効果音 Hz')
    for e in ev: ax[0].axvline(e['t'] - t0, color='red' if e['kind'] == 'scene' else 'orange', lw=1.4 if e['kind'] == 'scene' else 0.7, alpha=0.8)
    for p in pk:
        if p.get('guess'): ax[0].plot(p['t'], 9500, 'v', color='cyan', ms=7)
    vb = rms_db(voc, sr); bb = rms_db(bg, sr); tt = np.arange(len(vb)) * 0.1
    ax[1].plot(tt, vb, color='#4af', lw=0.8, label='声'); ax[1].plot(tt, bb, color='#f80', lw=0.8, label='BGM+効果音')
    ax[1].set_ylim(-70, 0); ax[1].legend(loc='upper right', fontsize=7); ax[1].set_xlabel('秒（窓の頭から・+%.1f で動画の秒）' % t0)
    ax[1].set_xticks(np.arange(0, L, 5))
    fig.suptitle(title + '  赤=場面転換 橙=要素の出入り ▼=効果音候補', fontsize=9); fig.tight_layout(); fig.savefig(path, dpi=80); plt.close(fig)

_sep = None; _wh = None
def separate(wav, outdir):
    global _sep
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    if _sep is None:
        _sep = get_model('htdemucs'); _sep.to('mps'); _sep.eval()
    a, sr = read_wav(wav)
    w = wave.open(wav); ch = w.getnchannels(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, ch).T.astype(np.float32) / 32768
    t = torch.from_numpy(x.copy())
    ref = t.mean(0); t = (t - ref.mean()) / (ref.std() + 1e-8)
    with torch.no_grad():
        out = apply_model(_sep, t[None].to('mps'), device='mps', shifts=0, split=True, overlap=0.25, progress=False)[0].cpu()
    out = out * (ref.std() + 1e-8) + ref.mean()
    names = _sep.sources; vi = names.index('vocals')
    voc = out[vi].mean(0).numpy(); bg = (out.sum(0) - out[vi]).mean(0).numpy()
    for nm, y in (('vocals', voc), ('bg', bg)):
        with wave.open(os.path.join(outdir, nm + '.wav'), 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    return bg, voc, sr

def transcribe(p):
    import mlx_whisper
    r = mlx_whisper.transcribe(p, path_or_hf_repo='mlx-community/whisper-large-v3-turbo', language='ja', word_timestamps=True, condition_on_previous_text=False)
    segs = [{'s': round(s['start'], 2), 'e': round(s['end'], 2), 'text': s['text'],
             'words': [[round(w['start'], 2), round(w['end'], 2), w['word']] for w in s.get('words', [])]} for s in r['segments']]
    return segs

def find(vid):
    if vid.endswith('.mp4') and os.path.exists(vid): return vid
    g = glob.glob(os.path.join(BASE, 'channels', 'dl', '*', vid + '.mp4'))
    return g[0] if g else None

def run(vid):
    v = find(vid); vid = os.path.basename(v)[:-4]; od = os.path.join(OUT, vid); os.makedirs(od, exist_ok=True)
    if os.path.exists(os.path.join(od, 'data.json')): return 'skip'
    d = dur_of(v); st = time.time()
    n = 30; ts = [d * (i + 0.5) / n for i in range(n)]
    sheet(grab(v, ts, (320, 180)), [fmt(t) for t in ts], os.path.join(od, 'overview.jpg'), cols=6)
    data = {'id': vid, 'channel': v.split('/')[-2], 'duration': round(d, 1), 'windows': []}
    for name, t0, t1 in windows(d):
        ev, diff = changes(v, t0, t1)
        kt = key_times(ev, t0, t1)
        for k in range(0, len(kt), 20):
            part = kt[k:k + 20]
            sheet(grab(v, part), [fmt(t) for t in part], os.path.join(od, 'w%s_sheet%d.jpg' % (name, k // 20)))
        wd = os.path.join(od, 'w' + name); os.makedirs(wd, exist_ok=True)
        wav = os.path.join(wd, 'mix.wav')
        sh(['ffmpeg', '-v', 'error', '-y', '-ss', str(t0), '-t', str(t1 - t0), '-i', v, '-vn', '-ac', '2', '-ar', '44100', '-c:a', 'pcm_s16le', wav])
        bg, voc, sr = separate(wav, wd)
        pk, floor, beat = onsets(bg, sr)
        for p in pk:
            p['t'] = round(p['t'] + t0, 2); p['guess'] = sfx_guess(p)
            near = [e for e in ev if -0.35 <= p['t'] - e['t'] <= 0.5]
            p['near_change'] = near[0]['kind'] if near else None
        vdb = rms_db(voc, sr); bdb = rms_db(bg, sr)
        speech = vdb > np.percentile(vdb, 60) - 6
        bgm = {'bg_floor_db': round(float(np.percentile(bdb, 20)), 1), 'bg_median_db': round(float(np.median(bdb)), 1),
               'voice_median_db': round(float(np.median(vdb[speech])), 1) if speech.any() else None,
               'bg_in_pause_db': round(float(np.median(bdb[~speech])), 1) if (~speech).any() else None}
        bgm['voice_minus_bg_db'] = round(bgm['voice_median_db'] - bgm['bg_median_db'], 1) if bgm['voice_median_db'] else None
        nov = novelty(bg, sr)
        for x in nov: x['t'] = round(x['t'] + t0, 1)
        audio_strip(bg, voc, sr, t0, ev, [dict(p, t=p['t'] - t0) for p in pk], os.path.join(od, 'w%s_audio.png' % name), '%s %s %s〜%s' % (vid, name, fmt(t0), fmt(t1)))
        segs = transcribe(os.path.join(wd, 'vocals.wav'))
        for s in segs:
            s['s'] += t0; s['e'] += t0; s['s'] = round(s['s'], 2); s['e'] = round(s['e'], 2)
            s['words'] = [[round(a + t0, 2), round(b + t0, 2), w] for a, b, w in s['words']]
        os.remove(wav)
        data['windows'].append({'name': name, 't0': t0, 't1': t1, 'changes': ev, 'sheet_times': [round(t, 2) for t in kt],
                                'onsets': pk, 'bgm_beat': beat, 'bgm': bgm, 'bgm_switch_candidates': nov, 'transcript': segs})
    json.dump(data, open(os.path.join(od, 'data.json'), 'w'), ensure_ascii=False, indent=1)
    return '%.0fs' % (time.time() - st)

if __name__ == '__main__':
    ids = sys.argv[1:]
    if ids == ['--all']:
        import csv
        rows = [r for r in csv.reader(open(os.path.join(BASE, 'channels', 'hantei.tsv')), delimiter='\t')][1:]
        ids = [r[1] for r in rows if r[4] == '非実写']
    for i, vid in enumerate(ids):
        try: print(i, vid, run(vid), flush=True)
        except Exception as e: print(i, vid, 'ERR', repr(e)[:300], flush=True)
