#!/usr/bin/env python3
# 起こした声（work/whisper_words.json）を台本（input/daihon.txt）の文の切れ目で行に分け、work/timing.json を作る（yt-henshu-pipe・10/19）
#   面談前VSL v12 では行の頭の言葉を作業AIが手で並べていた（loomzen/gyou.py の HEAD 70個）。ここでは台本の文の終わり（。！？・改行）を
#   話した字に引き当てて切る。台本と話した字が違う所（言い回し・聞き違い）は前後の一致した字から位置を決め、Whisper の言葉の頭に寄せる。
#   1行が長すぎる（60字超）ときは、行の中のいちばん長い間（0.2秒以上）で割る。2字以下の行は前の行につなぐ。
#   python3 gyou_auto.py <作業フォルダ>
import os, sys, json, re, difflib, unicodedata, subprocess
P = sys.argv[1]
W = json.load(open(os.path.join(P, 'work', 'whisper_words.json')))
DAI = open(os.path.join(P, 'input', 'daihon.txt'), encoding='utf-8-sig').read()
PUNCT = r'[、。「」『』！？!?,.\s・…（）()【】%％]'
N = lambda s: re.sub(PUNCT, '', s)
# 話した字（小文字・句読点なし）と字ごとの時刻・言葉の番号
S = ''; T = []; E = []; EW = []
for i, w in enumerate(W):
    n = len(w['w'])
    for j, ch in enumerate(w['w']):
        if not re.sub(PUNCT, '', ch): continue
        S += ch.lower(); T.append(w['s'] + (w['e'] - w['s']) * j / max(1, n)); E.append(w['e']); EW.append(i)
# 2回目（--fa）：強制合わせ（work/timing_fa.json）の字ごとの頭と、声の大きさから測った「その字の前の静かな長さ」で切り直す
#   Whisper の言葉の時刻は隙間なく並ぶので間が測れない（10/19：「撮っています｜この動画」の間が0秒に見えた）
FA = '--fa' in sys.argv
if FA:
    import numpy as np
    J0 = json.load(open(os.path.join(P, 'work', 'timing_fa.json')))
    assert J0['ref'] == S, '強制合わせの字と起こした字が違う（gyou_auto.py を先に1回）'
    T = J0['starts']
    x = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(P, 'work', 'vocals.wav'), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True).stdout
    x = np.frombuffer(x, np.int16).astype(np.float32) / 32768; n10 = len(x) // 160
    DBV = 20 * np.log10(np.sqrt((x[:n10 * 160].reshape(n10, 160) ** 2).mean(1)) + 1e-9)
    def quiet_before(t):
        i = int(t * 100) - 1; k = 0
        while i - k >= 0 and k < 200 and DBV[i - k] < -38: k += 1
        return k / 100
# 台本の字（同じ正規化）と、文の終わりの位置
D = ''; DB = set(); DC = set()   # DC：台本の読点（、）の位置（長い行を割るときの候補）
for line in DAI.splitlines():
    if not N(line).strip(): continue
    if re.match(r'^\s*[（(].*[)）]\s*$', line): continue          # 「（特典内容確定したら追記）」のような編集メモは読まない
    for ch in unicodedata.normalize('NFKC', line):
        if re.sub(PUNCT, '', ch): D += ch.lower()
        elif ch in '。！？!?' and D: DB.add(len(D))
        elif ch in '、,' and D: DC.add(len(D))
    # 短い行（8字以下）が句点も文の終わりの形も無く終わるとき（「才能／努力の量／運」の並べ書き）は、行の終わりを切れ目にしない（10/20 ⑤「才能｜・努力の量」・作業AI）
    _ln = N(unicodedata.normalize('NFKC', line))
    if D and len(_ln) <= 8 and not re.search(r'[。！？!?]\s*$', line) and not re.search(r'(ます|です|ください|ません|ました|でした|ですか|ますか|しょう)$', _ln): continue
    if D: DB.add(len(D))
# 台本の位置 → 話した字の位置
mp = [None] * (len(D) + 1)
for a, b, n in difflib.SequenceMatcher(None, D, S, autojunk=False).get_matching_blocks():
    for d in range(n): mp[a + d] = b + d
    if n: mp[a + n] = b + n
def to_s(k):
    # 前後で一番近い一致した字から引く（言い回し違いの中なら、前の一致の直後）
    for d in range(0, 40):
        if k - d >= 0 and mp[k - d] is not None: return mp[k - d] + d if d == 0 else mp[k - d]
    return None
def word_head(c):
    """c を Whisper の言葉の頭へ寄せる（言葉の途中で切らない）"""
    if c <= 0 or c >= len(S): return c
    if EW[c] != EW[c - 1]: return c
    l = c; r = c
    while l > 0 and EW[l] == EW[l - 1]: l -= 1
    while r < len(S) and EW[r] == EW[c]: r += 1
    return l if c - l <= r - c else r
def gap(c):
    if not (0 < c < len(S)): return 0
    return quiet_before(T[c]) if FA else T[c] - E[c - 1]
def snap(c):
    """台本の文の切れ目を引き当てた所 c の前後6字で、いちばん長い間（0.12秒以上）のある言葉の頭へ寄せる。無ければ言葉の頭"""
    cs = [x for x in range(max(1, c - 6), min(len(S), c + 7)) if EW[x] != EW[x - 1]]
    best = max(cs, key=lambda x: (gap(x), -abs(x - c)), default=None)
    return best if best is not None and gap(best) >= 0.12 else word_head(c)
cut = {0, len(S)}
DBCUT = set()   # 台本の行・文の終わりから決めた切れ目（10/20 ⑤：後の文節の直しが「なる人｜売上」を「なる｜人売上」に動かした → この切れ目は動かさない）
for k in sorted(DB):
    s = to_s(k)
    if s is not None: c_ = snap(s); cut.add(c_); DBCUT.add(c_)
TENS = set(x for x in (to_s(k) for k in DC) if x is not None)   # 台本の読点の位置（話した字）
# 台本に無い言い足し（文の切れ目を引き当てられない所）は、0.45秒以上の間で切る（前後とも10字以上）
cs = sorted(cut)
for c in range(1, len(S)):
    if EW[c] != EW[c - 1] and gap(c) >= 0.45:
        prv = max(x for x in cs if x <= c); nxt = min(x for x in cs if x >= c)
        if c - prv >= 10 and nxt - c >= 10: cut.add(c); cs = sorted(cut)
cut = sorted(cut)
# 長すぎる行は行の中のいちばん長い間で割る
out = [cut[0]]
for a, b in zip(cut, cut[1:]):
    segs = [(a, b)]
    while any(y - x > 60 for x, y in segs):
        nx = []
        for x, y in segs:
            if y - x <= 60: nx.append((x, y)); continue
            cs = [c for c in range(x + 12, y - 12) if EW[c] != EW[c - 1]]
            # 用言の連体形（〜る・〜た・〜な）のすぐ後に名詞が続く所では割らない（10/20 ⑤「稼げる｜額を」・作業AI）。候補が無くなるときは元の候補のまま
            _cs2 = [c for c in cs if not (S[c - 1:c] in ('る', 'た', 'な') and re.match(r'[一-龥ァ-ヴa-z0-9]', S[c:c + 1]))]
            cs = _cs2 or cs
            if not cs: nx.append((x, y)); continue
            c = max(cs, key=lambda c: (gap(c) >= 0.2, gap(c), -abs(c - (x + y) / 2)))   # 10/20 読点を先に選ぶ形を試したが、9版目で「いろんな｜パターン」と悪くなったので入れない
            nx += [(x, c), (c, y)]
        if nx == segs: break
        segs = nx
    out += [y for x, y in segs]
cut = sorted(set(out))
# 話した字の文の終わり（「ください｜この動画は」のように台本に無い言い足しの中の文の切れ目）：文の終わりの形の後に 0.3秒以上の間があれば切る
BR = re.compile(r'(ます|です|ください|ません|ました|でした|ですね|ますね|よね|んです|ですか|ますか|しょう|ですよ|ません)$')
SBR = [c for c in range(1, len(S)) if EW[c] != EW[c - 1] and gap(c) >= 0.3 and BR.search(S[max(0, c - 6):c])]   # 話した字の文の終わり（字幕の札をまたがせない）
for c in SBR:
    if True:
        prv = max(x for x in cut if x <= c); nxt = min(x for x in cut if x >= c)
        if c - prv >= 5 and nxt - c >= 5: cut = sorted(set(cut) | {c})
# 短い行（8字未満）が文の終わりで終わらず、次の行との間が 0.3秒未満なら次の行とつなぐ（「この動画は｜面談確定者の…」）
k = 1
while k < len(cut) - 1:
    a_, c = cut[k - 1], cut[k]
    if c - a_ < 8 and not BR.search(S[a_:c]) and gap(c) < 0.3: cut.pop(k); continue
    k += 1
# 言葉の途中・助詞の前で切らない（「思｜っております」「よ｜って」）：文節の頭でない切れ目は、前後8字の文節の頭（間の長い方）へ動かす。無ければ切らない
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from kire_bunseki import bunsetsu_heads
except ImportError: bunsetsu_heads = None   # 形態素の道具が無い環境（pipe/.venv で走らせる）
if bunsetsu_heads:
    new = [cut[0]]
    for i, c in enumerate(cut[1:-1], 1):
        a_, b_ = cut[i - 1], cut[i + 1]
        w0 = max(a_, c - 14); s_ = S[w0:min(b_, c + 14)]
        hs = {w0 + h for h in bunsetsu_heads(s_)[0]}
        # 台本の切れ目で、前後とも漢字・カナ・英数字（名詞と名詞の間）なら動かさない。句読点の無い話した字では、形態素の道具が「人売上」「研究ai」を1語につないで切れ目を見失う（10/20 ⑤）
        #   前がひらがな（「いろんな｜パターン」）・次が助詞（「2億円｜を出した」）なら、これまでどおり文節の頭へ動かす
        _NM = r'[一-龥ァ-ヴーa-z0-9]'
        if c in hs or (c in DBCUT and re.match(_NM, S[c - 1:c]) and re.match(_NM, S[c:c + 1])): new.append(c); continue
        cs = [h for h in hs if abs(h - c) <= 8 and h - new[-1] >= 3 and b_ - h >= 3]
        if cs: new.append(max(cs, key=lambda h: (gap(h), -abs(h - c))))
    new.append(cut[-1]); cut = sorted(set(new))
# 2字以下の行は前の行につなぐ
cut2 = [cut[0]]
for c in cut[1:]:
    if c - cut2[-1] <= 2 and c != len(S): continue
    cut2.append(c)
if len(cut2) > 2 and cut2[-1] - cut2[-2] <= 2: cut2.pop(-2)
cut = cut2
L = []; L0 = {}
for i in range(len(cut) - 1):
    a, b = cut[i], cut[i + 1]; n = i + 1; L0[n] = a
    L.append({'n': n, 'sec': '本編', 'text': S[a:b], 'start': round(T[a], 3), 'end': round(E[b - 1], 3)})
d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(P, 'work', 'vocals.wav')], capture_output=True, text=True).stdout)
if FA:   # 行だけを入れ替える（字ごとの時刻はそのまま）
    for nm in ('timing.json', 'timing_fa.json'):
        fp = os.path.join(P, 'work', nm); J1 = json.load(open(fp))
        J1['lines'] = L; J1['line0'] = L0; J1['sent_breaks'] = SBR; J1['gyou'] = 'pipe/gyou_auto.py --fa（台本の文の切れ目・強制合わせの頭と静かな長さ）'
        json.dump(J1, open(fp, 'w'), ensure_ascii=False)
    open(os.path.join(P, 'work', 'gyou.txt'), 'w').write('\n'.join('%d\t%.2f\t%s' % (x['n'], x['start'], x['text']) for x in L) + '\n')
    print('（強制合わせで切り直し）行 %d ／ 1行の長さ 中央 %d 最大 %d' % (len(L), sorted(len(x['text']) for x in L)[len(L) // 2], max(len(x['text']) for x in L))); sys.exit(0)
json.dump({'lines': L, 'ref': S, 'line0': L0, 'starts': [round(t, 3) for t in T], 'ends': [round(e, 3) for e in E], 'fa_bias': 0.0, 'duration': round(d, 3), 'speed': 1.0,
           'source': 'input/narration（依頼主から受け取った声・編集なし）', 'gyou': 'pipe/gyou_auto.py（台本の文の切れ目）'}, open(os.path.join(P, 'work', 'timing.json'), 'w'), ensure_ascii=False)
open(os.path.join(P, 'work', 'gyou.txt'), 'w').write('\n'.join('%d\t%.2f\t%s' % (x['n'], x['start'], x['text']) for x in L) + '\n')
print('行 %d ／ 字 %d ／ 台本の文の切れ目 %d ／ 1行の長さ 中央 %d 最大 %d' % (len(L), len(S), len(DB), sorted(len(x['text']) for x in L)[len(L) // 2], max(len(x['text']) for x in L)))
