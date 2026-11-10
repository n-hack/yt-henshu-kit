#!/usr/bin/env python3
# 空の画面の見張り（team-lead 10/21：MJrC edl-j で 25.0〜26.3秒が「字幕と左上の札だけ」になり、門が数えず合格になった）
#   python3 kara_gamen.py <動画.mp4> [--t1 秒] [--sen 0.5]
#   上の札の帯（上 11%）と下の字幕帯（下 15%）を除いた所で、線（輪郭）があるかを 10コマ/秒で見る。
#   輪郭の画素の割合が SEN_HEN 未満のコマ＝部品が何もないコマ。それが sen 秒以上続いたら「出た」。
#   輪郭で見るので、無地・ぼかし・グラデーションの地は空に数え、写真・映像・図・字は空に数えない。
import subprocess, json, argparse, numpy as np
W, H, FPS = 320, 180, 10
UE, SHITA = 0.11, 0.85      # 上の札の帯・下の字幕帯を除く
SEN_HEN = 0.004             # 輪郭の画素の割合の線（手本15本・MJrC edl-j で決めた・kara_gamen 10/21）

def hen_wariai(fr):
    a = fr[int(H * UE):int(H * SHITA), :].astype(np.float32)
    gx = np.abs(np.diff(a, axis=1))[:-1, :]; gy = np.abs(np.diff(a, axis=0))[:, :-1]
    return float(((gx + gy) > 8).mean())   # 線は 8（40 だとぼけた写真・薄い線画を空と数えた：手本9か所）

def kara_check(mp4, t1=None, sen=0.5):
    cmd = ['ffmpeg', '-v', 'error', '-i', mp4] + (['-t', str(t1)] if t1 else []) + ['-vf', 'fps=%d,scale=%d:%d,format=gray' % (FPS, W, H), '-f', 'rawvideo', '-']
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE); vals = []
    while True:
        b = pr.stdout.read(W * H)
        if len(b) < W * H: break
        vals.append(hen_wariai(np.frombuffer(b, np.uint8).reshape(H, W)))
    pr.wait()
    runs, s = [], None
    for i, v in enumerate(vals + [1.0]):
        if v < SEN_HEN and s is None: s = i
        elif v >= SEN_HEN and s is not None:
            if (i - s) / FPS >= sen: runs.append((round(s / FPS, 1), round(i / FPS, 1)))
            s = None
    saicho = 0.0; s = None
    for i, v in enumerate(vals + [1.0]):
        if v < SEN_HEN and s is None: s = i
        elif v >= SEN_HEN and s is not None: saicho = max(saicho, (i - s) / FPS); s = None
    return {'koma': len(vals), 'sen_byou': sen, 'sen_hen': SEN_HEN, 'deta': runs, 'saicho_byou': round(saicho, 1), 'hen_min': round(min(vals), 4) if vals else None}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mp4'); ap.add_argument('--t1', type=float); ap.add_argument('--sen', type=float, default=0.5)
    a = ap.parse_args(); r = kara_check(a.mp4, a.t1, a.sen); print(json.dumps(r, ensure_ascii=False))
    raise SystemExit(1 if r['deta'] else 0)
