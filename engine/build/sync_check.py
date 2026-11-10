#!/usr/bin/env python3
# 話した言葉と、画面に文字が出た時刻のずれを測る。
# 言葉の話し始め（whisper）の前後で、30fps・1/4サイズのコマを「話し始め0.8秒前のコマ」と比べ、
# 変化が出始めたコマ（平均差 > 0.25）を「出た時刻」とする。元の動画も同じ式で測る。
import sys, json, subprocess, numpy as np
BASE = sys.argv[1]
W = json.load(open(BASE + '/tr/words.json'))
def wt(word, near):
    c = [(abs(a - near), a) for a, b, w in W if word in w and abs(a - near) < 2.5]
    return min(c)[1] if c else None
def frames(v, t0, dur):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '%.3f' % t0, '-i', v, '-t', '%.3f' % dur, '-vf', 'scale=480:270',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 270, 480).astype(np.float32)
def appear(v, s, region=None):
    t0 = s - 0.8; fr = frames(v, t0, 2.6)
    base = fr[0]
    for i in range(1, len(fr)):
        d = np.abs(fr[i] - base)
        if region: x0, y0, x1, y1 = region; d = d[y0 // 4:y1 // 4, x0 // 4:x1 // 4]
        if d.mean() > 0.25: return round(t0 + i / (30000 / 1001), 2)
    return None
P = json.load(open(sys.argv[2]))
rows = []
for p in P:
    s = wt(p['w'], p['near'])
    m = appear(BASE + '/shisaku-3min.mp4', s, p.get('mr')); o = appear(BASE + '/src/orig.mp4', s, p.get('or'))
    rows.append(dict(label=p['label'], spoken=round(s, 2), mine=m, orig=o, mine_diff=None if m is None else round(m - s, 2), orig_diff=None if o is None else round(o - s, 2)))
    print('%-12s 話した%7.2f  試作%7s (%+.2f)  元%7s (%s)' % (p['label'], s, m, (m - s) if m else 0, o, None if o is None else '%+.2f' % (o - s)))
json.dump(rows, open(BASE + '/check/sync.json', 'w'), ensure_ascii=False, indent=1)
md = [abs(r['mine_diff']) for r in rows if r['mine_diff'] is not None]
print('試作のずれ 平均 %.2fs 最大 %.2fs（%d点）' % (np.mean(md), np.max(md), len(md)))
