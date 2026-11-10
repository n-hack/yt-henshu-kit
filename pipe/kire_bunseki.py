# 行の字を形態素で切り、字幕の切れ目が「言葉の途中」に落ちていないかを数える。切ってよい位置（文節の頭）も出す
#   写し元：state/yt-evervsl-1019/v12/kire_bunseki.py（面談前VSL v12・10/19）。yt-henshu-pipe の行づくり・字幕の切れ目・割れの数えで共通に使う
import sys, json, fugashi
tg = fugashi.Tagger()
FUZOKU = {'助詞', '助動詞', '接尾辞', '補助記号'}
def bunsetsu_heads(s):
    """文節の頭になる字の位置（0 と len は除く）"""
    ws = [w for w in tg(s)]
    pos, p = [], 0
    spans = []
    for w in ws:
        k = s.find(w.surface, p)
        if k < 0: k = p
        spans.append((k, k + len(w.surface), w)); p = k + len(w.surface)
    heads = set()
    for i, (a, b, w) in enumerate(spans):
        if i == 0: continue
        pa, pb, pw = spans[i - 1]
        f = w.feature; pf = pw.feature
        p1, p2 = f.pos1, f.pos2
        if p1 in FUZOKU: continue                       # 助詞・助動詞・接尾辞・記号は前につく
        if pf.pos1 == '接頭辞': continue                   # 「お｜仕事」
        if p1 == '名詞' and pf.pos1 == '名詞': continue     # 名詞の続き（営業｜管理・300｜万）
        if p1 == '名詞' and pf.pos1 == '名詞' and pf.pos2 == '数詞': continue
        if p2 == '非自立可能' and pf.pos1 in ('助詞',) and pw.surface in ('て', 'で'): continue   # 「して｜いる」
        if p1 == '動詞' and p2 == '非自立可能' and pf.pos1 == '動詞': continue                   # 「使い｜始める」
        if p1 == '形状詞' and pf.pos1 == '名詞': continue
        if w.surface in ('いう', 'いっ', '言う', 'いい') and pw.surface in ('と', 'って'): continue   # 「と｜いう話」
        if pf.pos1 in ('補助記号',) and pw.surface in ('「', '（', '('): continue
        heads.add(a)
    return sorted(heads), [(a, b, w.surface, w.feature.pos1) for a, b, w in spans]
if __name__ == '__main__':
    G = json.load(open(sys.argv[1])); out = []; nbad = ntot = 0
    for g in G:
        heads, toks = bunsetsu_heads(g['txt'])
        cut, p = [], 0
        for c in g['raw'][:-1]:
            p += len(c.replace('｜', '')) if False else len(c); cut.append(p)
        # raw には「｜」が含まれるので、txt（｜入り）上の位置で数える
        hs = set(heads)
        for c in cut:
            ntot += 1
            # ｜の直後・直前は文の切れ目扱い
            ok = c in hs or g['txt'][c - 1:c] == '｜' or g['txt'][c:c + 1] == '｜'
            if not ok:
                nbad += 1; out.append({'n': g['n'], 'mae': g['txt'][max(0, c - 8):c], 'ato': g['txt'][c:c + 8]})
        g['heads'] = heads
    json.dump(G, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
    print('切れ目', ntot, '言葉の途中', nbad)
    for o in out: print('  %d\t%s｜%s' % (o['n'], o['mae'], o['ato']))
