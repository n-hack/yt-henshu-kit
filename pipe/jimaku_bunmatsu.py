#!/usr/bin/env python3
# 字幕の1枚が文の切れ目をまたいでいないかを数える（作業AI 10/20：r14「僕含め思ったと思います優秀な相談相手が」）
#   作る側（jimaku_ji.py・ki1.build_jimaku）とは別の見方で数える：
#   ① 台本の文の終わり（。！？・行の終わり）の前4字＋後2字が、1枚の字幕の中に続けて入っている
#   ② 話した字の文の終わり（〜です／ます／ました／でした／ません のすぐ後に、続きの字でない字）が1枚の中にある
#   python3 jimaku_bunmatsu.py <作業フォルダ>   → 件数を出し、1件でもあれば 1 で終わる。中身は work/bunmatsu.tsv
import os, sys, re, json, unicodedata
P = sys.argv[1]
F = json.load(open(os.path.join(P, 'work', 'fuda.json')))
DP = os.path.join(P, 'input', 'daihon.txt')
PUNCT = r'[、。「」『』！？!?,.\s・…（）()【】%％]'
pairs = set()
if os.path.exists(DP):
    flat, ends = '', []
    for line in open(DP, encoding='utf-8-sig').read().splitlines():
        t = unicodedata.normalize('NFKC', line)
        if not re.sub(PUNCT, '', t).strip(): continue
        for ch in t:
            if ch in '。！？!?': ends.append(len(flat))
            elif not re.match(PUNCT, ch): flat += ch.lower()
        tt = re.sub(PUNCT, '', t)
        if re.search(r'[。！？!?]\s*$', t) or re.search(r'(?:です|ます|ました|でした|ません|笑)$', tt): ends.append(len(flat))   # 行の終わりは、文の終わりの形の行だけ（見出し・箇条書きの行の終わりは文の切れ目にしない）
    for e in set(ends):
        if 4 <= e <= len(flat) - 2: pairs.add((flat[e - 4:e], flat[e:e + 2]))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from bunmatsu_re import OWARI
rows = []
for n, s in enumerate(F):
    t = unicodedata.normalize('NFKC', s).lower(); t = re.sub(PUNCT, '', t)
    for k in range(4, len(t) - 1):
        if (t[k - 4:k], t[k:k + 2]) in pairs and not re.match(r'(など|って|とい|との|と言)', t[k:]) and not re.fullmatch(r'(step\d+|第\d+段階|\d+つ目)', t[:k]): rows.append((n, '台本の文の終わり', s, t[:k] + '｜' + t[k:])); break
    else:
        m = OWARI.search(t)
        if m and m.end() < len(t): rows.append((n, '話した字の文の終わり', s, t[:m.end()] + '｜' + t[m.end():]))
open(os.path.join(P, 'work', 'bunmatsu.tsv'), 'w').write('札\t見方\t字幕\t切れ目\n' + ''.join('%d\t%s\t%s\t%s\n' % r for r in rows))
print('字幕 %d 枚・文の切れ目をまたぐ %d 枚（台本の文の終わり %d・話した字の文の終わり %d）' % (len(F), len(rows), sum(1 for r in rows if r[1] == '台本の文の終わり'), sum(1 for r in rows if r[1] != '台本の文の終わり')))
for r in rows[:30]: print('  #%d %s：%s' % (r[0], r[1], r[3]))
sys.exit(1 if rows else 0)
