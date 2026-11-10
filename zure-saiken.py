# 写し元：state/yt-evervsl-1019/loomzen/zure-saiken.py（10/19 v12 で手で走らせていた見直し）。門 zettai-mon.py のルール5が、zure-kensa の1コマ超を本当のずれか確かめるのに使う
# zure-kensa で1コマ超になった部品だけ、言葉の頭のコマの前後（-2〜+2）でその範囲の画素が変わったかを見直す
#   前の部品が同じ範囲に先に出ていると、zure-kensa は「その部品が早く出た」と数えてしまう（重なりの取り違え）。言葉の頭のコマで変化があれば合っている
import sys, json, subprocess, numpy as np
P, MP4, TSV = sys.argv[1:4]
FPS = 30000 / 1001; SW, SH = 480, 270; K = SW / 1920
D = json.load(open(P + '/work/zure-plan.json'))
# 10/20 r8：zure.tsv の行は zure-plan.json の elems と同じ順（zure-kensa が1部品1行で出す）→ 行の順で部品を引く。
#   前はコマ番号で引いていて、同じコマに部品が2〜3個あると最後の1個の範囲で見ていた（4564 の人物3つ）。基準の位置も cc 以外を左上として見ていた（人物は cb）
rows = open(TSV).read().splitlines()[1:-1]
assert len(rows) == len(D['elems']), '行の数 %d と部品の数 %d が合わない' % (len(rows), len(D['elems']))
bad = [(l.split('\t'), D['elems'][i]) for i, l in enumerate(rows) if l.split('\t')[4] not in ('', 'None') and abs(int(l.split('\t')[4])) > 1]
def box(e):   # zure-kensa.py の box と同じ
    w, h = e['w'] * K, e['h'] * K; x, y = e['x'] * K, e['y'] * K; a = (e.get('anchor') or 'lt') + 't'
    l = x - w / 2 if a[0] == 'c' else (x - w if a[0] == 'r' else x)
    t = y - h / 2 if a[1] == 'c' else (y - h if a[1] == 'b' else y)
    return l, t, w, h
from concurrent.futures import ThreadPoolExecutor
def one(re_):
    r, e = re_
    f = int(r[2]); l, t, w, h = box(e)
    x0, y0, x1, y1 = max(0, int(l)), max(0, int(t)), min(SW, int(l + w)), min(SH, int(t + h))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.4f' % (max(0, f - 4) / FPS), '-i', MP4, '-an', '-frames:v', '8', '-vf', 'scale=%d:%d,format=gray' % (SW, SH), '-f', 'rawvideo', '-'], capture_output=True).stdout
    V = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW).astype(np.int16)
    if f < 4:   # 10/20 ⑤：動画の頭（コマ0〜3）は前のコマが無く、差分では「出た」が測れない → そのコマ（か次）に部品が見えているかで見る
        def mieru0(i):
            m = np.median(V[i]); return float((np.abs(V[i, y0:y1, x0:x1] - m) > 40).mean()) > 0.02
        ok = mieru0(f) or mieru0(f + 1)
        return ok, '%s\t言葉の頭 %d\t動画の頭\t見えるか %s\t%s' % (r[0], f, ok, '合っている（動画の頭で前のコマが無い）' if ok else '🔴 ずれ')
    d = [round(float(np.abs(V[k, y0:y1, x0:x1] - V[k - 1, y0:y1, x0:x1]).mean()), 2) for k in range(1, len(V))]
    g = [round(float(np.abs(V[k] - V[k - 1]).mean()), 2) for k in range(1, len(V))]   # 画面全体の変化（切り替え・白抜けはここも大きい）
    # d[i] は コマ f-3+i の変化。f-1 までは止まっていて、f〜f+1 で変わるなら合っている
    pre = d[1:3]; at = d[3:5]   # pre＝コマ f−2・f−1 ／ at＝コマ f・f+1
    # 10/20 r8：範囲を正しくしたら、白抜けの切り替え（1141 s009・部品が見えるのは +4〜+7）が「f+2 で範囲が変わった」で合っているに入った。
    #   → 合っているとするのは、言葉の頭のコマか次のコマ（f・f+1）で範囲が変わり、その変化が画面全体の変化より目立つ（部品そのものが出た）ときだけ
    k_ = 3 + max(range(2), key=lambda j: d[3 + j])   # d[3]＝コマ f・d[4]＝コマ f+1（d[i] はコマ f−3+i … ではなく f−4+i+1 の変化。1コマ目の読みが f−4 から）
    # 前のコマ（f−2・f−1）の変化は、画面全体と同じだけ変わった分（切り替え）を引いて見る。r9 は切り替えを場面の頭の前に終えるので、前のコマが切り替えで動く
    pre_x = max(max(0.0, d[j] - g[j]) for j in (1, 2))
    ok = (d[k_] > 1.5 and d[k_] > 3 * max(pre_x, 0.5) and d[k_] > 1.5 * g[k_])
    # 10/20 vhm8 地替え：言葉の頭で画面ごと切り替わる（g が大きい）と、部品の範囲も画面と同じだけ変わり「画面より目立つ」が成り立たない。
    #   切り替えのときだけ、頭のコマか次のコマで、その範囲に地の色（そのコマの中央値）と違う画素が出ているか（部品が見えているか）で見る
    if not ok and g[k_] > 20:
        def mieru(i):
            m = np.median(V[i]); return float((np.abs(V[i, y0:y1, x0:x1] - m) > 40).mean()) > 0.02
        ok = mieru(4) or mieru(5)   # V[4]＝コマ f・V[5]＝コマ f+1（読みは f−4 から）
    return ok, '%s\t言葉の頭 %d\t前2コマ %s\t頭の前後 %s\t%s' % (r[0], f, pre, at, '合っている（前の部品の取り違え）' if ok else '🔴 ずれ')
ng = 0
with ThreadPoolExecutor(12) as ex:   # 部品ごとの読み（ffmpeg）を同時に・出す順は元のまま
    for ok, line in ex.map(one, bad):
        ng += not ok; print(line)
print('見直し %d 件 ／ 本当のずれ %d 件' % (len(bad), ng)); sys.exit(1 if ng else 0)
