#!/usr/bin/env python3
# 字幕（場面表の JIMAKU＝聞き違いを直した後の字）を台本の正本と字ごとに突き合わせる（10/19 v10 の直し・作業員）
#   写し元：state/yt-evervsl-1019/e/jimaku-taishou.py（yt-henshu-pipe が書き出しの後に毎回走らせる）
#   使い方: PROJ=<作業フォルダ> python3 jimaku-taishou.py <出力.tsv>
#   1枚ごとに：台本と一致した字の割合・対応する台本の字・食い違い（字幕→台本）を出す。一致率の低い順に並べる
import os, sys, json, re, difflib, unicodedata
P = os.environ['PROJ']; sys.path.insert(0, P)
import ki1
J = ki1.build_jimaku(os.path.join(P, 'work', 'timing_fa.json'), 99999)
def N(s):
    s = unicodedata.normalize('NFKC', s).lower()
    return re.sub(r'[\s、。，．,.！!？?「」『』（）()・…\-―ー~〜:：;；"\'“”‘’＿_*＊/／\[\]【】→×%％]', '', s)
# 字幕：1枚ごとの字を並べ、字ごとにどの1枚かを覚える
js, owner = '', []
for k, (a, b, s) in enumerate(J):
    n = N(s); js += n; owner += [k] * len(n)
raw = open(next(f for f in (os.path.join(P, 'input', 'daihon-seihon.txt'), os.path.join(P, 'input', 'daihon.txt')) if os.path.exists(f)), encoding='utf-8-sig').read()   # yt-henshu-pipe は input/daihon.txt
ss, spos = '', []
for i, ch in enumerate(raw):
    n = N(ch)
    for c in n: ss += c; spos.append(i)
sm = difflib.SequenceMatcher(None, js, ss, autojunk=False)
match = [None] * len(js)
for a, b, size in sm.get_matching_blocks():
    for d in range(size): match[a + d] = b + d
diffs = {}
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal': continue
    k = owner[min(i1, len(owner) - 1)] if i1 < len(owner) else owner[-1]
    diffs.setdefault(k, []).append((js[i1:i2], ss[j1:j2]))
rows = []
for k, (a, b, s) in enumerate(J):
    idx = [i for i, o in enumerate(owner) if o == k]
    m = [match[i] for i in idx if match[i] is not None]
    rate = len(m) / max(1, len(idx))
    if m:
        lo, hi = spos[min(m)], spos[max(m)]
        dai = raw[max(0, lo - 4):hi + 5].replace('\n', '⏎')
    else: dai = ''
    df = ' ／ '.join('%s→%s' % (x or '∅', y or '∅') for x, y in diffs.get(k, []) if len(x) + len(y) <= 24)
    rows.append((rate, k, a, s, dai, df))
with open(sys.argv[1], 'w') as fp:
    fp.write('一致率\t枚\t秒\t字幕\t台本（前後4字）\t食い違い（字幕→台本）\n')
    for r in sorted(rows, key=lambda r: (r[0], r[2])):
        fp.write('%.2f\t%d\t%.2f\t%s\t%s\t%s\n' % (r[0], r[1], r[2], r[3], r[4], r[5]))
print('字幕 %d 枚・全体の一致 %.3f・一致率0.6未満 %d 枚' % (len(J), sm.ratio(), sum(1 for r in rows if r[0] < 0.6)))
