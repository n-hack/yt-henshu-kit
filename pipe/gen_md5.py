#!/usr/bin/env python3
# 書き出す前に組んだ絵（元絵）の md5 を1コマずつ出す・2つの版を比べる（yt-henshu-pipe 2026-10-20）
#   GPU の書き出しは混み具合で同じ元絵でも数コマだけ違う決め方をする（r22→r23 の 700〜702・最大差11/255）。
#   版どうしの「変わった・変わらない」は書き出した動画ではなく、この元絵の md5 で見る（作業AI 10/20 案1）
#     作る    PIPE_EDL=1 python3 gen_md5.py <proj> <出力.txt> [--jobs 8]
#     比べる  python3 gen_md5.py --kurabe <前.txt> <後.txt> [<proj>]   ← proj を渡すと変わったコマを場面の番号で出す
import os, sys, json, hashlib, argparse, multiprocessing as mp
sys.path.insert(0, os.path.expanduser('~/rin6/tools/yt-henshu/lib'))
_S = None
def _kukan(rng):
    import anim
    return [(n, hashlib.md5(_S.frame_at(n / anim.FPS).convert('RGB').tobytes()).hexdigest()) for n in rng]
def tsukuru(proj, out, jobs):
    global _S
    import render, anim
    _S = render.load_story(proj)
    n = int(round(_S.END * anim.FPS)) if hasattr(_S, 'END') else None
    if n is None:
        import json as _j; n = _j.load(open(os.path.join(proj, 'out', 'tmp', 'parts.json')))['f1']
    step = 300; ch = [range(a, min(n, a + step)) for a in range(0, n, step)]
    with mp.get_context('fork').Pool(jobs) as p: res = p.map(_kukan, ch)
    rows = sorted(x for r in res for x in r)
    with open(out, 'w') as f: f.write(''.join(h + '\n' for _, h in rows))
    print('元絵 %d コマ → %s' % (len(rows), out))
def bamen_of(proj):
    d = json.load(open(os.path.join(proj, 'intent.json'))); return sorted((s['t'], s['role'].replace('EDL ', '')) for s in d if str(s.get('role', '')).startswith('EDL '))
def kurabe(a, b, proj=None):
    x = [l.strip() for l in open(a) if l.strip()]; y = [l.strip() for l in open(b) if l.strip()]
    rng = []
    for i in range(min(len(x), len(y))):
        if x[i] != y[i]:
            if rng and i == rng[-1][1] + 1: rng[-1][1] = i
            else: rng.append([i, i])
    print('コマ数 %d／%d・違う区間 %d・違うコマ %d' % (len(x), len(y), len(rng), sum(b_ - a_ + 1 for a_, b_ in rng)))
    bm = bamen_of(proj) if proj else []
    import bisect, render, anim
    for a_, b_ in rng:
        nm = ''
        if bm:
            ts = [t for t, _ in bm]; i0 = max(0, bisect.bisect_right(ts, a_ / anim.FPS) - 1); i1 = max(0, bisect.bisect_right(ts, b_ / anim.FPS) - 1)
            nm = '・'.join(sorted({bm[i][1] for i in range(i0, i1 + 1)}))
        print('  %d〜%d %s' % (a_, b_, nm))
    return rng
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--kurabe':
        kurabe(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None); sys.exit(0)
    ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('out'); ap.add_argument('--jobs', type=int, default=8)
    a = ap.parse_args(); os.environ.setdefault('PIPE_EDL', '1'); tsukuru(a.proj, a.out, a.jobs)
