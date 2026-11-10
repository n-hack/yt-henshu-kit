#!/usr/bin/env python3
# 編集の「質」を数で測る共通の道具（見本も作業AIの動画も同じ式で測る）
#   changes(video, t0, t1)        30fps の画面の差 → 変化の瞬間・動いているコマの割合
#   voice_onsets(y, sr)           声の立ち上がり（0.15秒以上の無音のあと）
#   pauses(y, sr)                 声の無音の長さ（0.08秒以上）
#   window_metrics(...)           1区間ぶんの数字（切替/分・最長の止まった画面・動きの割合・無音の分布・テロップのずれ・効果音のずれ）
import subprocess, numpy as np
FPS = 30000 / 1001
def changes(v, t0, t1, w=192, h=108, thr=0.5):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t0), '-i', v, '-t', str(t1 - t0), '-vf', 'scale=%d:%d' % (w, h), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(a, axis=0)).mean(axis=(1, 2))
    ev = [t0 + (i + 1) / FPS for i in range(1, len(d)) if d[i] > thr and d[i - 1] <= thr]
    return np.array(ev), d
def _env(y, sr, hop=0.005, win=0.02):
    h, w = int(sr * hop), int(sr * win)
    n = max(0, (len(y) - w) // h)
    idx = np.arange(n)[:, None] * h + np.arange(w)[None, :]
    e = np.sqrt((y[idx] ** 2).mean(1)); return 20 * np.log10(e + 1e-9)
def voiced_mask(y, sr):
    db = _env(y, sr); return db > (np.percentile(db, 95) - 30)
def voice_onsets(y, sr, gap=0.15):
    v = voiced_mask(y, sr); g = int(gap / 0.005); out = []
    for j in range(g, len(v) - 8):
        if v[j] and not v[j - g:j].any() and v[j:j + 8].mean() > 0.7: out.append(j * 0.005)
    return np.array(out)
def pauses(y, sr, mn=0.08):
    v = voiced_mask(y, sr); out = []; c = 0; started = False
    for x in v:
        if x:
            if started and c * 0.005 >= mn: out.append(c * 0.005)
            c = 0; started = True
        else: c += 1
    return np.array(out)
def window_metrics(video, t0, t1, voc=None, sr=None, voc_t0=0.0, sfx_times=None):
    ev, d = changes(video, t0, t1); dur = t1 - t0
    m = {'dur': round(dur, 1), 'changes_pm': round(len(ev) / dur * 60, 1)}
    edges = np.concatenate([[t0], ev, [t1]]); m['longest_static'] = round(float(np.diff(edges).max()), 2)
    m['motion_share'] = round(float(np.mean((d > 0.05) & (d <= 0.5))), 3)   # ゆっくり動いている（寄り・揺れ・流れる）コマの割合
    if voc is not None:
        on = voice_onsets(voc, sr) + voc_t0; on = on[(on >= t0) & (on < t1)]
        tv = [float(ev[np.argmin(abs(ev - o))] - o) for o in on if len(ev) and abs(ev[np.argmin(abs(ev - o))] - o) <= 0.5]
        m['telop_offsets'] = [round(x, 3) for x in tv]
        p = pauses(voc[int(max(0, t0 - voc_t0) * sr):int((t1 - voc_t0) * sr)], sr); m['pauses'] = [round(float(x), 3) for x in p]
    if sfx_times is not None:
        st = np.array([s for s in sfx_times if t0 <= s < t1])
        m['sfx_pm'] = round(len(st) / dur * 60, 1)
        m['sfx_offsets'] = [round(float(s - ev[np.argmin(abs(ev - s))]), 3) for s in st if len(ev) and abs(s - ev[np.argmin(abs(ev - s))]) <= 0.3]
    return m
