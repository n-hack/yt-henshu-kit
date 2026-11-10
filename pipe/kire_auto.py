# 字幕の切れ目の表（work/jimaku_kire.json）を作る（pipe/.venv の fugashi・unidic-lite）
#   写し元：state/yt-evervsl-1019/v12/kire_heads.py（面談前VSL v12 で手で作った切れ目の表）。yt-henshu-pipe では字幕に出す字（work/jimaku_disp.json）から毎回作る
#   python kire_auto.py <作業フォルダ>
#   tsunagu … 行の終わりが言葉の途中（「応｜じて」「AIエージ｜ェント」）なら、次の行とつないで1つの字として切る。その行の n
#   heads   … 字（「｜」で分けた1つずつ）ごとの、切ってよい位置＝文節の頭
#   yowai   … 名詞と名詞の間（「市場調査｜競合調査」）。文節の頭が長さの中に無いときだけ使う
import sys, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__))); from bunmatsu_re import owari_de_owaru
sys.path.insert(0, sys.path[0]); from kire_bunseki import bunsetsu_heads, tg
def yowai_heads(s):
    out, p = [], 0; prev = None
    for w in tg(s):
        k = s.find(w.surface, p); k = p if k < 0 else k
        if prev is not None and w.feature.pos1 == '名詞' and prev.feature.pos1 == '名詞' and len(w.surface) >= 2 and len(prev.surface) >= 2 and w.feature.pos2 != '数詞' and prev.feature.pos2 != '数詞':
            out.append(k)
        prev = w; p = k + len(w.surface)
    return out
import re as _re
SETSUZOKU = ('でも', 'けど', 'けれど', 'けれども', 'だから', 'なので', 'じゃあ', 'では')
def tsunagu_ka(sa, sb):
    """行の終わり sa と次の行の頭 sb の間で切ると言葉が割れるか。
    ① 形態素の途中（「応｜じて」「詳｜しく」「作｜って」）② 次の行が助詞・助動詞で始まる（「んです｜が」「ありません｜か」）。ただし「でも」などの接続の言葉は文の頭なので切ってよい
    ③ カタカナ・英字の名詞の続き（「AI｜エージェント」）"""
    if owari_de_owaru(sa): return False   # 行の終わりが文の終わりならつながない（「すごいです」＋「本当に」を1枚にしない・作業AI 10/20）
    s = sa + sb; j = len(sa); p = 0; toks = []
    for w in tg(s):
        k = s.find(w.surface, p); k = p if k < 0 else k; toks.append((k, k + len(w.surface), w)); p = k + len(w.surface)
    for k0, k1, w in toks:
        if k0 < j < k1: return True
    nx = [t for t in toks if t[0] == j]; pv = [t for t in toks if t[1] == j]
    if not nx or not pv: return True
    w, v = nx[0][2], pv[0][2]
    if any(sb.startswith(x) for x in SETSUZOKU): return False
    if w.feature.pos1 in ('助詞', '助動詞', '接尾辞'): return True
    if w.feature.pos1 == '名詞' and v.feature.pos1 == '名詞' and _re.match(r'[ァ-ヴーA-Za-z]', sb) and _re.search(r'[ァ-ヴーA-Za-z]$', sa): return True
    return False
def wareru(s, j):
    """s の j で切ると言葉が割れるか（形態素の途中・助詞／助動詞／接尾辞で始まる）。割れる所の印だけ外す（台本の切れ目を話した字に当てたずれ：「使えないん｜でしょ」）"""
    p = 0
    for w in tg(s):
        k = s.find(w.surface, p); k = p if k < 0 else k
        if k < j < k + len(w.surface): return True
        if k == j: return w.feature.pos1 in ('助詞', '助動詞', '接尾辞') and not any(s[j:].startswith(x) for x in SETSUZOKU + ('なんで',))
        p = k + len(w.surface)
    return False
import os
P = sys.argv[1]
DJ = json.load(open(os.path.join(P, 'work', 'jimaku_disp.json')))
# 文の切れ目の印「｜」の後ろが文節の頭でなければ印を外す（台本の切れ目を話した字へ当てたときのずれ：「使えないん｜でしょ」）
nodrop = 0
for n, v in DJ.items():
    d, ix = v['disp'], v['idx']
    while '｜' in d:
        flat = d.replace('｜', ''); hs = set(bunsetsu_heads(flat)[0]); out, oi, p, changed = '', [], 0, False
        for c, i in zip(d, ix):
            if c == '｜' and p not in hs and p > 0 and not owari_de_owaru(out.replace('｜', '')) and wareru(flat, p): changed = True; continue   # 文の終わりの後の印は残す（「違います｜だから」）・言葉が割れない所の印も残す（「売上はある｜でも」「第2段階｜AIエージェント」）
            out += c; oi.append(i)
            if c != '｜': p += 1
        if not changed: break
        nodrop += 1; d, ix = out, oi
    v['disp'], v['idx'] = d, ix
json.dump(DJ, open(os.path.join(P, 'work', 'jimaku_disp.json'), 'w'), ensure_ascii=False, indent=0)
G = [{'n': int(n), 'txt': v['disp']} for n, v in sorted(DJ.items(), key=lambda kv: int(kv[0])) if v['disp']]
tsunagu = []
for a, b in zip(G, G[1:]):
    sa = a['txt'].split('｜')[-1]; sb = b['txt'].split('｜')[0]
    if not sa or not sb: continue
    if tsunagu_ka(sa, sb): tsunagu.append(a['n'])
# 行をつないだ字を作り、「｜」で分けて表にする
groups, cur = [], ''
for g in G:
    cur += g['txt']
    if g['n'] not in tsunagu: groups.append(cur); cur = ''
if cur: groups.append(cur)
H, Y = {}, {}
for t in groups:
    for seg in t.split('｜'):
        if seg and seg not in H: H[seg] = bunsetsu_heads(seg)[0]; Y[seg] = yowai_heads(seg)
json.dump({'doc': '字幕の切れ目の表。pipe/kire_auto.py が fugashi(unidic-lite) で作った。ki1.py の build_jimaku／_kiru2 が使う', 'tsunagu': tsunagu, 'heads': H, 'yowai': Y}, open(os.path.join(P, 'work', 'jimaku_kire.json'), 'w'), ensure_ascii=False, indent=0)
print('つなぐ行', len(tsunagu), tsunagu, '字', len(H), '外した文の切れ目の印の行', nodrop)
