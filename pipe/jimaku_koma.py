# 写し元：state/yt-evervsl-1019/v12/jimaku_koma.py（yt-henshu-pipe が書き出しの後に毎回走らせる）
# 字幕1枚ずつ、①動画で字幕帯が切り替わったコマ ②予定のコマ（言葉の頭＝強制合わせの言葉の表）③別の耳（whisper の言葉の頭）を並べ、ずれをコマで出す
#   使い方: python3 jimaku_koma.py <作業フォルダ> <mp4> <出力.tsv>
import os, sys, json, subprocess, numpy as np, bisect
P, MP4, OUT = sys.argv[1:4]; sys.path.insert(0, P); sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib')); os.environ['PROJ'] = P
import ki1
FPS = ki1.FPS
END = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(P, 'work', 'vocals.wav')], capture_output=True, text=True).stdout) - 0.02
J = ki1.build_jimaku(os.path.join(P, 'work', 'timing_fa.json'), round(END, 2))
J = [j for j in J if j[0] < END - 1.0 / FPS]   # 頭3分のように声を途中で切った作業フォルダでは、時刻表（timing_fa）が全編のまま残る → 動画の外の札は数えない（r5 で空の区間で止まった原因・10/19）
# 字幕帯（下の 150 画素）を 384x30 の灰色で全部のコマ読む
# 字幕帯の中だけ（まん中 280×60・どの札でも帯が覆う所）を見る。帯の外を入れると場面の切り替わりを拾う（初回の測りで 7 枚が場面の切り替わりを拾った）
SW, SH = 140, 30
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', MP4, '-an', '-vf', 'crop=280:60:820:995,scale=%d:%d,format=gray' % (SW, SH), '-f', 'rawvideo', '-'], capture_output=True).stdout
V = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW).astype(np.int16)
D = np.concatenate([[0], np.abs(V[1:] - V[:-1]).mean(axis=(1, 2))])   # D[k]＝コマ k で前のコマから変わった量
W = [w for w in json.load(open(os.path.join(P, 'work', 'whisper_words.json')))]
ws = [w['s'] for w in W]
rows, z = [], []
for k, (a, b, s) in enumerate(J):
    fe = int(round(a * FPS))
    lo = fe - 6; hi = fe + 6
    if k > 0: lo = max(lo, (int(round(J[k - 1][0] * FPS)) + fe) // 2 + 1)
    if k + 1 < len(J): hi = min(hi, (int(round(J[k + 1][0] * FPS)) + fe) // 2)
    lo = max(1, lo); hi = min(len(D) - 1, hi)
    if lo > hi:   # 次の札が同じコマ近く（間が1コマ以下）・または動画の終わりの外：予定のコマだけを見る（r5 で空の区間で止まった・10/19）
        lo = hi = min(max(1, fe), len(D) - 1)
    seg = D[lo:hi + 1]; fm = lo + int(np.argmax(seg)); peak = float(seg.max())
    # 別の耳：予定の時刻にいちばん近い whisper の言葉の頭
    i = bisect.bisect_left(ws, a); cand = [j for j in (i - 1, i) if 0 <= j < len(ws)]
    j = min(cand, key=lambda j: abs(ws[j] - a)); fw = int(round(ws[j] * FPS))
    d1 = fm - fe; d2 = fe - fw
    z.append((d1, d2, peak))
    rows.append('%d\t%.3f\t%d\t%d\t%d\t%.1f\t%d\t%s\t%s' % (k, a, fe, fm, d1, peak, d2, W[j]['w'], s))
open(OUT, 'w').write('枚\t予定の秒\t予定のコマ\t動画で変わったコマ\tずれ(動画−予定)\t変わった量\t予定−別の耳(whisper)\t別の耳の言葉\t字幕\n' + '\n'.join(rows) + '\n')
d1 = np.array([x[0] for x in z]); d2 = np.array([x[1] for x in z]); pk = np.array([x[2] for x in z])
print('枚', len(J), '／ 動画で変わったコマ−予定のコマ：0コマ', int((d1 == 0).sum()), '・±1', int((abs(d1) == 1).sum()), '・1コマ超', int((abs(d1) > 1).sum()), '・最大', int(abs(d1).max()), '／ 変わった量が小さい(<2)', int((pk < 2).sum()))
print('   予定−別の耳：中央値 %.1f コマ・±1以内 %d・±3以内 %d・3コマ超 %d' % (np.median(d2), int((abs(d2) <= 1).sum()), int((abs(d2) <= 3).sum()), int((abs(d2) > 3).sum())))
