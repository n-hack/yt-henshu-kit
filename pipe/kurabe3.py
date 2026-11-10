#!/usr/bin/env python3
# 手本・自分の版を同じ式で測る（yt-henshu-pipe 2026-10-20・依頼主「手本の作者さんと全然違う」への調べ）
#   python3 kurabe3.py <出力.json> <名前>=<動画> [...] [--t1 171]
#   1本ずつ、頭 0〜t1 秒を測る：
#     sekisho の5つ（絵の差・埋まり方・大きな切り替わり/分・動く要素/分・色の種類）
#     場面の長さ   10fps で画面全体の差が 25 を超えたコマ＝場面が替わった所（0.3秒以内の続きは1回）→ 回数/分・場面の長さの中央値（秒）
#     背景         1秒1コマ・画面の外周（幅の8%）の一番多い色（各色を3ビット）→ 外周がその色1つで埋まる割合（無地の度合い）・出た背景の色の数（1割以上のコマ・3%以上）・背景が替わった回数/分
#     絵の密度     1秒1コマ・灰色の縦横の差の和が 60 を超える画素の割合（線・字・模様の多さ）
#     字           1秒1コマ・1280x720 を ocr で読む。下 20%（字幕帯）は字幕、それより上を画面の字として
#                  画面の字の数/コマ・字のあるコマの割合・一番大きい字の高さ（画面の高さ比・中央値）・字の位置（上/中/下の割合）・字幕のあるコマの割合
import os, sys, json, subprocess, tempfile, statistics as st
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu'))
import sekisho as SK
OCR = os.path.expanduser('~/rin6/tools/yt-henshu/ocr')

def basho(a):   # 10fps・320x180
    g = a.astype(np.float32).mean(axis=3); d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2)); cut = []
    for i, x in enumerate(d):
        if x > 25 and (not cut or i - cut[-1] > 3): cut.append(i)
    sec = len(a) / 10.0; edges = [0] + [c + 1 for c in cut] + [len(a)]
    L = [(edges[k + 1] - edges[k]) / 10.0 for k in range(len(edges) - 1) if edges[k + 1] > edges[k]]
    return {'cut_pm': round(len(cut) / (sec / 60), 2), 'shot_med_s': round(st.median(L), 2) if L else None}

def haikei(a):
    s = a[::10]; Hh, Ww = s.shape[1:3]; b = max(2, int(Ww * 0.08))
    mask = np.zeros((Hh, Ww), bool); mask[:b] = mask[-b:] = True; mask[:, :b] = mask[:, -b:] = True
    flat, modes = [], []
    for f in s:
        px = (f[mask] >> 5).astype(np.int32); key = px[:, 0] * 64 + px[:, 1] * 8 + px[:, 2]
        cnt = np.bincount(key, minlength=512); m = int(cnt.argmax()); flat.append(cnt[m] / len(key)); modes.append(m if cnt[m] / len(key) > 0.4 else -1)
    u = [m for m in modes if m >= 0]; kinds = sum(1 for m in set(u) if u.count(m) >= max(1, 0.03 * len(modes)))
    ch = sum(1 for i in range(1, len(modes)) if modes[i] != modes[i - 1])
    g = s.astype(np.float32).mean(axis=3); e = (np.abs(np.diff(g, axis=1))[:, :, :-1] + np.abs(np.diff(g, axis=2))[:, :-1, :]) > 60
    px_ = s.astype(np.float32)[:, mask]; mx_ = px_.max(axis=2); mn_ = px_.min(axis=2); bsat = float(np.median(((mx_ - mn_) / np.maximum(mx_, 1)).mean(axis=1)))   # 背景（外周）の色の濃さ
    sf = s.astype(np.float32); iro = float((((sf.max(axis=3) - sf.min(axis=3)) / np.maximum(sf.max(axis=3), 1)) > 0.25).mean())   # 画面の色のある所の割合
    return {'iro_wariai': round(iro, 3), 'bg_sat': round(bsat, 3), 'bg_flat': round(float(np.median(flat)), 3), 'bg_kinds': kinds, 'bg_change_pm': round(ch / (len(modes) / 60), 2), 'mitsudo': round(float(e.mean()), 4)}

def ji(f, t1):
    d = tempfile.mkdtemp(prefix='k3ocr-')
    subprocess.run(['ffmpeg', '-v', 'error', '-t', str(t1), '-i', f, '-vf', 'fps=1,scale=1280:720', os.path.join(d, '%04d.png')], check=True)
    ps = sorted(os.path.join(d, x) for x in os.listdir(d))
    def run(ch): return subprocess.run([OCR] + ch, capture_output=True, text=True).stdout.splitlines()
    rows = []
    with ThreadPoolExecutor(6) as ex:
        for out in ex.map(run, [ps[i:i + 20] for i in range(0, len(ps), 20)]): rows += [json.loads(l) for l in out if l.strip()]
    n = len(rows); kazu, takasa, ue, naka, shita, ari, jimaku, haba = [], [], 0, 0, 0, 0, 0, []
    for r in rows:
        bx = [b for b in (r.get('r') or []) if b[5] >= 0.3 and len(b[0].strip()) >= 1]
        scr = [b for b in bx if b[2] + b[4] / 2 < 0.80]; sub = [b for b in bx if b[2] + b[4] / 2 >= 0.80]
        if sub: jimaku += 1
        kazu.append(sum(len(b[0].replace(' ', '')) for b in scr))
        if scr:
            ari += 1; big = max(scr, key=lambda b: b[4]); takasa.append(big[4]); cy = big[2] + big[4] / 2
            haba.append(max(b[3] for b in scr))   # 1行の字の幅（画面の横幅の割合・一番横に長い行）
            if cy < 0.33: ue += 1
            elif cy < 0.6: naka += 1
            else: shita += 1
    subprocess.run(['rm', '-rf', d])
    return {'ji_kazu': round(st.mean(kazu), 1) if kazu else 0, 'ji_ari': round(ari / max(1, n), 3), 'ji_takasa': round(st.median(takasa), 3) if takasa else None,
            'ji_ue': round(ue / max(1, ari), 2), 'ji_naka': round(naka / max(1, ari), 2), 'ji_shita': round(shita / max(1, ari), 2), 'jimaku_ari': round(jimaku / max(1, n), 3), 'ji_haba': round(st.median(haba), 3) if haba else None}

def hakaru(f, t1):
    a = SK.frames(f, 0, t1); r = SK.measure(a); r.update(basho(a)); r.update(haikei(a)); r.update(ji(f, t1)); return r

if __name__ == '__main__':
    args = [x for x in sys.argv[2:] if not x.startswith('--')]; t1 = 171.0
    if '--t1' in sys.argv: t1 = float(sys.argv[sys.argv.index('--t1') + 1]); args = [x for x in args if x != sys.argv[sys.argv.index('--t1') + 1]]
    out = sys.argv[1]; res = json.load(open(out)) if os.path.exists(out) else {}
    for a in args:
        nm, f = a.split('=', 1)
        if nm in res: continue
        res[nm] = hakaru(f, t1); res[nm]['file'] = f; print(nm, json.dumps(res[nm], ensure_ascii=False), flush=True)
        json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)
